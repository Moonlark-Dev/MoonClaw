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
系统命令执行工具模块

提供在本地系统执行命令的工具函数，支持异步执行。
"""

import asyncio
import os
import shlex
from typing import Optional
from nonebot.log import logger

from ...config import config
from ...types import GetTextFunc


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
    if config.exec_allowed_commands is not None:
        if main_command not in config.exec_allowed_commands:
            return False, f"命令 '{main_command}' 不在允许执行的命令白名单中"

    # 检查黑名单
    if main_command in config.exec_blocked_commands:
        return False, f"命令 '{main_command}' 被禁止执行"

    return True, None


async def exec_command(
    command: str,
    timeout: Optional[int],
    working_dir: Optional[str],
    get_text: GetTextFunc,
) -> str:
    """
    在本地系统执行命令

    Args:
        command: 要执行的命令字符串
        timeout: 超时时间（秒），None 表示使用配置的默认值
        working_dir: 命令执行的工作目录，None 表示使用当前目录
        get_text: 获取本地化文本的函数

    Returns:
        命令执行结果
    """
    # 检查工具是否启用
    if not config.exec_enabled:
        return await get_text("exec.disabled")

    # 检查命令是否允许执行
    allowed, reason = _is_command_allowed(command)
    if not allowed:
        return await get_text("exec.blocked", reason)

    # 获取实际使用的超时时间
    actual_timeout = timeout or config.exec_timeout

    # 准备工作目录
    cwd = working_dir if working_dir else None

    try:
        logger.info(f"执行命令: {command} (工作目录: {cwd or '当前目录'})")

        # 创建子进程
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        # 等待命令完成或超时
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=actual_timeout
            )
        except asyncio.TimeoutError:
            # 超时，终止进程
            try:
                process.kill()
                await process.wait()
            except Exception as e:
                logger.warning(f"终止超时进程失败: {e}")
            return await get_text("exec.timeout", actual_timeout)

        # 解码输出
        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")

        # 截断输出
        if len(stdout_text) <= config.exec_max_output_length:
            truncated_stdout, stdout_truncated = stdout_text, False
        else:
            truncated_stdout, stdout_truncated = stdout_text[-config.exec_max_output_length:], True

        if len(stderr_text) <= config.exec_max_output_length:
            truncated_stderr, stderr_truncated = stderr_text, False
        else:
            truncated_stderr, stderr_truncated = stderr_text[-config.exec_max_output_length:], True

        # 构建结果
        result_lines = [
            await get_text("exec.success_header"),
            await get_text("exec.command", command),
            await get_text("exec.exit_code", process.returncode),
        ]

        # 添加标准输出
        if truncated_stdout:
            result_lines.append("")
            result_lines.append(await get_text("exec.stdout_header"))
            result_lines.append(truncated_stdout)
            if stdout_truncated:
                result_lines.append("")
                result_lines.append(
                    await get_text("exec.output_truncated", config.exec_max_output_length)
                )

        # 添加标准错误
        if truncated_stderr:
            result_lines.append("")
            result_lines.append(await get_text("exec.stderr_header"))
            result_lines.append(truncated_stderr)
            if stderr_truncated:
                result_lines.append("")
                result_lines.append(
                    await get_text("exec.output_truncated", config.exec_max_output_length)
                )

        # 如果没有输出
        if not truncated_stdout and not truncated_stderr:
            result_lines.append("")
            result_lines.append(await get_text("exec.no_output"))

        return "\n".join(result_lines)

    except FileNotFoundError as e:
        logger.error(f"命令执行失败: {e}")
        return await get_text("exec.not_found", str(e))
    except PermissionError as e:
        logger.error(f"命令执行失败: {e}")
        return await get_text("exec.permission_denied", str(e))
    except Exception as e:
        logger.exception(e)
        return await get_text("exec.error", str(e))
