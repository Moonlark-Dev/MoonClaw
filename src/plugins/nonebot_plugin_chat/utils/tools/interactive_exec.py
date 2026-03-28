#  Moonlark - A new ChatBot
#  Copyright (C) 2025  Moonlark Development Team
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
# ##############################################################################

"""
交互式命令执行工具模块

提供在本地系统执行交互式命令的工具函数，支持会话管理和输入交互。
"""

import asyncio
import os
import shlex
import uuid
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field
from nonebot.log import logger
from nonebot_plugin_apscheduler import scheduler

from ...config import config
from ...types import GetTextFunc

# 输出截断长度限制
OUTPUT_MAX_LENGTH = 4000


@dataclass
class InteractiveExecSession:
    """交互式命令执行会话"""

    session_id: str
    command: str
    title: str
    process: asyncio.subprocess.Process
    status: str  # "running", "completed", "stopped", "failed"
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    output: str = ""
    exit_code: Optional[int] = None


# 全局会话存储
_sessions: dict[str, InteractiveExecSession] = {}
# 会话锁，用于并发控制
_session_lock = asyncio.Lock()


def _extract_command(command: str) -> str:
    """
    从命令字符串中提取主命令

    Args:
        command: 完整的命令字符串

    Returns:
        主命令名称
    """
    try:
        # 使用 shlex 分割命令，正确处理引号
        parts = shlex.split(command)
        if parts:
            # 获取第一个部分作为主命令
            main_command = parts[0]
            # 提取命令名称（处理路径）
            return os.path.basename(main_command)
    except Exception as e:
        logger.warning(f"解析命令失败: {e}")
    return ""


def _is_command_allowed(command: str) -> tuple[bool, Optional[str]]:
    """
    检查命令是否允许执行

    Args:
        command: 要执行的命令

    Returns:
        (是否允许, 拒绝原因)
    """
    main_command = _extract_command(command)

    # 检查白名单
    if config.interactive_exec_allowed_commands is not None:
        if main_command not in config.interactive_exec_allowed_commands:
            return False, f"命令 '{main_command}' 不在允许执行的命令白名单中"

    # 检查黑名单
    if main_command in config.interactive_exec_blocked_commands:
        return False, f"命令 '{main_command}' 被禁止执行"

    return True, None


def _truncate_output(output: str) -> tuple[str, bool]:
    """
    截断输出内容

    Args:
        output: 原始输出

    Returns:
        (截断后的输出, 是否发生截断)
    """
    if len(output) <= OUTPUT_MAX_LENGTH:
        return output, False
    return output[-OUTPUT_MAX_LENGTH:], True


def _format_datetime(dt: Optional[datetime]) -> str:
    """格式化日期时间"""
    if not dt:
        return "未知"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _get_status_emoji(status: str) -> str:
    """获取状态对应的 emoji"""
    status_emojis = {
        "running": "🔄",
        "completed": "✅",
        "stopped": "🛑",
        "failed": "❌",
    }
    return status_emojis.get(status, "❓")


async def _read_process_output(session: InteractiveExecSession) -> None:
    """
    异步读取进程输出

    Args:
        session: 会话对象
    """
    try:
        async for line in session.process.stdout:
            text = line.decode("utf-8", errors="replace")
            session.output += text

        async for line in session.process.stderr:
            text = line.decode("utf-8", errors="replace")
            session.output += text
    except Exception as e:
        logger.warning(f"读取进程输出失败: {e}")


async def _monitor_process(session: InteractiveExecSession, timeout: Optional[int]) -> None:
    """
    监控进程状态，处理超时和完成

    Args:
        session: 会话对象
        timeout: 超时时间（秒）
    """
    try:
        # 等待进程完成或超时
        if timeout:
            await asyncio.wait_for(session.process.wait(), timeout=timeout)
        else:
            await session.process.wait()

        # 进程正常完成
        session.status = "completed" if session.process.returncode == 0 else "failed"
        session.exit_code = session.process.returncode
        session.finished_at = datetime.now()
    except asyncio.TimeoutError:
        # 超时，终止进程
        try:
            session.process.kill()
            await session.process.wait()
            session.status = "stopped"
            session.finished_at = datetime.now()
            logger.info(f"会话 {session.session_id} 因超时被终止")
        except Exception as e:
            logger.warning(f"终止超时进程失败: {e}")
            session.status = "failed"
            session.finished_at = datetime.now()
    except Exception as e:
        logger.exception(e)
        session.status = "failed"
        session.finished_at = datetime.now()


async def interactive_exec_create_session(
    command: str,
    title: str,
    get_text: GetTextFunc,
) -> str:
    """
    创建一个新的交互式命令执行会话

    Args:
        command: 要执行的命令字符串
        title: 会话标题
        get_text: 获取本地化文本的函数

    Returns:
        会话创建结果
    """
    # 检查工具是否启用
    if not config.interactive_exec_enabled:
        return await get_text("interactive_exec.disabled")

    # 检查命令是否允许执行
    allowed, reason = _is_command_allowed(command)
    if not allowed:
        return await get_text("interactive_exec.blocked", reason)

    try:
        # 解析命令
        parts = shlex.split(command)
        if not parts:
            return await get_text("interactive_exec.invalid_command")

        # 生成会话 ID
        session_id = str(uuid.uuid4())[:8]

        # 创建子进程
        process = await asyncio.create_subprocess_exec(
            *parts,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # 创建会话对象
        session = InteractiveExecSession(
            session_id=session_id,
            command=command,
            title=title,
            process=process,
            status="running",
            created_at=datetime.now(),
            started_at=datetime.now(),
        )

        # 添加到会话存储
        async with _session_lock:
            _sessions[session_id] = session

        # 启动输出读取任务
        asyncio.create_task(_read_process_output(session))

        # 启动进程监控任务
        asyncio.create_task(_monitor_process(session, config.interactive_exec_timeout))

        logger.info(f"创建交互式命令执行会话: {session_id} - {command}")

        return await get_text(
            "interactive_exec.create_session.success",
            session_id,
            title,
            command
        )

    except FileNotFoundError as e:
        logger.error(f"命令执行失败: {e}")
        return await get_text("interactive_exec.not_found", str(e))
    except PermissionError as e:
        logger.error(f"命令执行失败: {e}")
        return await get_text("interactive_exec.permission_denied", str(e))
    except Exception as e:
        logger.exception(e)
        return await get_text("interactive_exec.error", str(e))


async def interactive_exec_get_session_state(
    session_id: str,
    get_text: GetTextFunc,
) -> str:
    """
    获取会话的状态和输出

    Args:
        session_id: 会话 ID
        get_text: 获取本地化文本的函数

    Returns:
        会话状态信息
    """
    async with _session_lock:
        session = _sessions.get(session_id)

    if not session:
        return await get_text("interactive_exec.get_session_state.not_found", session_id)

    status_emoji = _get_status_emoji(session.status)

    result_lines = [
        await get_text("interactive_exec.get_session_state.status_header"),
        await get_text("interactive_exec.get_session_state.session_id", session.session_id),
        await get_text("interactive_exec.get_session_state.title", session.title),
        await get_text("interactive_exec.get_session_state.status", session.status, status_emoji),
    ]

    if session.exit_code is not None:
        result_lines.append(await get_text("interactive_exec.get_session_state.exit_code", session.exit_code))

    result_lines.append(
        await get_text("interactive_exec.get_session_state.created_at", _format_datetime(session.created_at))
    )

    if session.started_at:
        result_lines.append(
            await get_text("interactive_exec.get_session_state.started_at", _format_datetime(session.started_at))
        )

    if session.finished_at:
        result_lines.append(
            await get_text("interactive_exec.get_session_state.finished_at", _format_datetime(session.finished_at))
        )

    # 处理输出
    if session.output:
        truncated_output, was_truncated = _truncate_output(session.output)
        result_lines.append("")
        result_lines.append(await get_text("interactive_exec.get_session_state.output_header"))
        result_lines.append(truncated_output)
        if was_truncated:
            result_lines.append("")
            result_lines.append(await get_text("interactive_exec.get_session_state.output_truncated", OUTPUT_MAX_LENGTH))
    else:
        result_lines.append("")
        result_lines.append(await get_text("interactive_exec.get_session_state.output_none"))

    return "\n".join(result_lines)


async def interactive_exec_send_input(
    session_id: str,
    input_text: str,
    get_text: GetTextFunc,
) -> str:
    """
    向正在运行的会话发送输入

    Args:
        session_id: 会话 ID
        input_text: 要发送的输入内容
        get_text: 获取本地化文本的函数

    Returns:
        发送结果
    """
    async with _session_lock:
        session = _sessions.get(session_id)

    if not session:
        return await get_text("interactive_exec.send_input.not_found", session_id)

    if session.status != "running":
        return await get_text("interactive_exec.send_input.not_running", session_id, session.status)

    try:
        # 发送输入到进程
        session.process.stdin.write(input_text.encode("utf-8"))
        await session.process.stdin.drain()

        # 截断显示的输入内容，避免太长
        display_input = input_text[:100] + "..." if len(input_text) > 100 else input_text
        display_input = display_input.replace("\n", "\\n")

        return await get_text("interactive_exec.send_input.success", session_id, display_input)

    except Exception as e:
        logger.exception(e)
        return await get_text("interactive_exec.send_input.error", str(e))


async def interactive_exec_stop_session(
    session_id: str,
    get_text: GetTextFunc,
) -> str:
    """
    停止正在运行的会话

    Args:
        session_id: 会话 ID
        get_text: 获取本地化文本的函数

    Returns:
        停止结果
    """
    async with _session_lock:
        session = _sessions.get(session_id)

    if not session:
        return await get_text("interactive_exec.stop_session.not_found", session_id)

    if session.status != "running":
        return await get_text("interactive_exec.stop_session.not_running", session_id, session.status)

    try:
        # 终止进程
        session.process.kill()
        await session.process.wait()

        # 更新会话状态
        session.status = "stopped"
        session.finished_at = datetime.now()

        logger.info(f"停止会话: {session_id}")

        return await get_text("interactive_exec.stop_session.success", session_id)

    except Exception as e:
        logger.exception(e)
        return await get_text("interactive_exec.stop_session.error", str(e))


async def _cleanup_old_sessions() -> None:
    """清理旧的已完成会话"""
    async with _session_lock:
        now = datetime.now()
        to_remove = []

        for session_id, session in _sessions.items():
            # 清理超过 1 小时的已完成会话
            if session.status != "running" and session.finished_at:
                if (now - session.finished_at).total_seconds() > 3600:
                    to_remove.append(session_id)

        for session_id in to_remove:
            del _sessions[session_id]
            logger.debug(f"清理旧会话: {session_id}")


# 注册定时任务清理旧会话
@scheduler.scheduled_job("interval", minutes=30, id="cleanup_old_sessions")
async def _scheduled_cleanup() -> None:
    """定时清理旧会话"""
    await _cleanup_old_sessions()
