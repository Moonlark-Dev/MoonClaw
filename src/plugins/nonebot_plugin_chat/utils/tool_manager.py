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

from typing import TYPE_CHECKING, Literal, Optional
from nonebot_plugin_openai.types import AsyncFunction, FunctionParameter, FunctionParameterWithEnum
from nonebot.adapters.onebot.v11 import Bot as OB11Bot
from nonebot_plugin_larkutils.jrrp import get_luck_value
from .tools import (
    browse_webpage,
    web_search,
    request_wolfram_alpha,
    search_abbreviation,
    describe_bilibili_video,
    resolve_b23_url,
    vm_create_task,
    vm_get_task_state,
    vm_send_input,
    vm_stop_task,
    is_vm_available,
    exec_command,
    read_file,
    interactive_exec_create_session,
    interactive_exec_get_session_state,
    interactive_exec_send_input,
    interactive_exec_stop_session,
)
from ..utils.emoji import QQ_EMOJI_MAP
from .note_manager import check_note, get_context_notes, get_note_poster
from .config_manager import config_manager

if TYPE_CHECKING:
    from ..core.processor import MessageProcessor


class ToolManager:
    def __init__(self, processor: "MessageProcessor"):
        self.processor = processor

    async def text(self, key: str, *args, **kwargs) -> str:
        return await self.processor.session.text(key, *args, **kwargs)

    async def report_tool_call(self, tool_name: str, params: dict) -> Optional[str]:
        """汇报工具调用

        Args:
            tool_name: 工具名称
            params: 工具参数

        Returns:
            汇报消息文本，如果不需要汇报则返回 None
        """
        # 从 config_manager 中读取配置，如果没有则使用默认值
        report_level = await config_manager.get("tool_call_report_level", "none")
        report_template = await config_manager.get("tool_call_report_template", "正在调用工具: {tool_name}{params}")
        excluded_tools = await config_manager.get("tool_call_report_excluded_tools", [])

        # 检查是否需要上报
        if report_level == "none":
            return None

        # 检查是否在排除列表中
        if tool_name in excluded_tools:
            return None

        # 根据汇报级别生成消息
        if report_level == "name":
            # name 模式：只替换 tool_name，不显示参数
            return report_template.format(tool_name=tool_name, params="")
        elif report_level == "full":
            # full 模式：显示工具名和完整参数
            params_str = ", ".join(f"{k}={v}" for k, v in params.items())
            return report_template.format(
                tool_name=tool_name,
                params=f" (参数: {params_str})" if params_str else ""
            )

        return None

    async def browse_webpage(self, url: str) -> str:
        return await browse_webpage(url, self.text)

    async def web_search(self, keyword: str) -> str:
        return await web_search(keyword, self.text)

    async def search_abbreviation(self, text: str) -> str:
        return await search_abbreviation(text, self.text)

    async def describe_bilibili_video(self, bv_id: str) -> str:
        return await describe_bilibili_video(bv_id, self.text)

    async def resolve_b23_url(self, b23_url: str) -> str:
        return await resolve_b23_url(b23_url, self.text)

    async def vm_create_task(self, command: str, title: str) -> str:
        return await vm_create_task(command, title, self.text)

    async def vm_get_task_state(self, task_id: str) -> str:
        return await vm_get_task_state(task_id, self.text)

    async def vm_send_input(self, task_id: str, input_text: str) -> str:
        return await vm_send_input(task_id, input_text, self.text)

    async def vm_stop_task(self, task_id: str) -> str:
        return await vm_stop_task(task_id, self.text)

    async def exec_command(self, command: str, timeout: Optional[int] = None, working_dir: Optional[str] = None) -> str:
        """执行系统命令

        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）
            working_dir: 工作目录

        Returns:
            命令执行结果
        """
        return await exec_command(command, timeout, working_dir, self.text)

    async def interactive_exec_create_session(self, command: str, title: str) -> str:
        """创建交互式命令执行会话

        Args:
            command: 要执行的命令
            title: 会话标题

        Returns:
            会话创建结果
        """
        return await interactive_exec_create_session(command, title, self.text)

    async def interactive_exec_get_session_state(self, session_id: str) -> str:
        """获取会话的状态和输出

        Args:
            session_id: 会话 ID

        Returns:
            会话状态信息
        """
        return await interactive_exec_get_session_state(session_id, self.text)

    async def interactive_exec_send_input(self, session_id: str, input_text: str) -> str:
        """向正在运行的会话发送输入

        Args:
            session_id: 会话 ID
            input_text: 要发送的输入内容

        Returns:
            发送结果
        """
        return await interactive_exec_send_input(session_id, input_text, self.text)

    async def interactive_exec_stop_session(self, session_id: str) -> str:
        """停止正在运行的会话

        Args:
            session_id: 会话 ID

        Returns:
            停止结果
        """
        return await interactive_exec_stop_session(session_id, self.text)

    async def read_file(
        self,
        file_path: str,
        encoding: Optional[str] = "utf-8",
        max_lines: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> str:
        """读取指定文件的内容

        Args:
            file_path: 文件路径
            encoding: 文件编码，默认 utf-8
            max_lines: 最大读取行数
            offset: 跳过的行数

        Returns:
            文件内容
        """
        return await read_file(file_path, self.text, encoding, max_lines, offset)

    async def calculate_luck_value(self, nickname: str) -> str:
        """计算用户的人品值

        Args:
            nickname: 用户的昵称

        Returns:
            人品值结果消息
        """
        users = await self.processor.session.get_users()
        if not (user_id := users.get(nickname)):
            return await self.text("tools_desc.calculate_luck_value.user_not_found", nickname)
        luck_value = await get_luck_value(user_id)
        return await self.text("tools_desc.calculate_luck_value.result", nickname, luck_value)

    async def select_tools(self, mode: Literal["group", "agent"]) -> list[AsyncFunction]:
        tools = []
        processor = self.processor

        # === 通用工具 ===

        # browse_webpage
        tools.append(
            AsyncFunction(
                func=self.browse_webpage,
                description=await self.text("tools_desc.browse_webpage.desc"),
                parameters={
                    "url": FunctionParameter(
                        type="string",
                        description=await self.text("tools_desc.browse_webpage.url"),
                        required=True,
                    )
                },
            )
        )

        # web_search
        tools.append(
            AsyncFunction(
                func=self.web_search,
                description=await self.text("tools_desc.web_search.desc"),
                parameters={
                    "keyword": FunctionParameter(
                        type="string",
                        description=await self.text("tools_desc.web_search.keyword"),
                        required=True,
                    )
                },
            )
        )

        # request_wolfram_alpha
        tools.append(
            AsyncFunction(
                func=request_wolfram_alpha,
                description=await self.text("tools_desc.request_wolfram_alpha.desc"),
                parameters={
                    "question": FunctionParameter(
                        type="string",
                        description=await self.text("tools_desc.request_wolfram_alpha.question"),
                        required=True,
                    )
                },
            )
        )

        # search_abbreviation
        tools.append(
            AsyncFunction(
                func=self.search_abbreviation,
                description=await self.text("tools_desc.search_abbreviation.desc"),
                parameters={
                    "text": FunctionParameter(
                        type="string",
                        description=await self.text("tools_desc.search_abbreviation.text_arg"),
                        required=True,
                    )
                },
            )
        )

        # describe_bilibili_video
        tools.append(
            AsyncFunction(
                func=self.describe_bilibili_video,
                description=await self.text("tools_desc.describe_bilibili_video.desc"),
                parameters={
                    "bv_id": FunctionParameter(
                        type="string",
                        description=await self.text("tools_desc.describe_bilibili_video.bv_id"),
                        required=True,
                    )
                },
            )
        )

        # resolve_b23_url
        tools.append(
            AsyncFunction(
                func=self.resolve_b23_url,
                description=await self.text("tools_desc.resolve_b23_url.desc"),
                parameters={
                    "b23_url": FunctionParameter(
                        type="string",
                        description=await self.text("tools_desc.resolve_b23_url.b23_url"),
                        required=True,
                    )
                },
            )
        )

        # read_file
        if mode == "group" and await config_manager.get("read_file_enabled", True):
            tools.append(
                AsyncFunction(
                    func=self.read_file,
                    description=await self.text("tools_desc.read_file.desc"),
                    parameters={
                        "file_path": FunctionParameter(
                            type="string",
                            description=await self.text("tools_desc.read_file.file_path"),
                            required=True,
                        ),
                        "encoding": FunctionParameter(
                            type="string",
                            description=await self.text("tools_desc.read_file.encoding"),
                            required=False,
                        ),
                        "max_lines": FunctionParameter(
                            type="integer",
                            description=await self.text("tools_desc.read_file.max_lines"),
                            required=False,
                        ),
                        "offset": FunctionParameter(
                            type="integer",
                            description=await self.text("tools_desc.read_file.offset"),
                            required=False,
                        ),
                    },
                )
            )

        # exec_command
        if mode == "group" and await config_manager.get("exec_enabled", True):
            tools.append(
                AsyncFunction(
                    func=self.exec_command,
                    description=await self.text("tools_desc.exec_command.desc"),
                    parameters={
                        "command": FunctionParameter(
                            type="string",
                            description=await self.text("tools_desc.exec_command.command"),
                            required=True,
                        ),
                        "timeout": FunctionParameter(
                            type="integer",
                            description=await self.text("tools_desc.exec_command.timeout"),
                            required=False,
                        ),
                        "working_dir": FunctionParameter(
                            type="string",
                            description=await self.text("tools_desc.exec_command.working_dir"),
                            required=False,
                        ),
                    },
                )
            )

        # interactive_exec 相关工具
        if mode == "group" and await config_manager.get("interactive_exec_enabled", True):
            # interactive_exec_create_session
            tools.append(
                AsyncFunction(
                    func=self.interactive_exec_create_session,
                    description=await self.text("tools_desc.interactive_exec_create_session.desc"),
                    parameters={
                        "command": FunctionParameter(
                            type="string",
                            description=await self.text("tools_desc.interactive_exec_create_session.command"),
                            required=True,
                        ),
                        "title": FunctionParameter(
                            type="string",
                            description=await self.text("tools_desc.interactive_exec_create_session.title"),
                            required=True,
                        ),
                    },
                )
            )

            # interactive_exec_get_session_state
            tools.append(
                AsyncFunction(
                    func=self.interactive_exec_get_session_state,
                    description=await self.text("tools_desc.interactive_exec_get_session_state.desc"),
                    parameters={
                        "session_id": FunctionParameter(
                            type="string",
                            description=await self.text("tools_desc.interactive_exec_get_session_state.session_id"),
                            required=True,
                        ),
                    },
                )
            )

            # interactive_exec_send_input
            tools.append(
                AsyncFunction(
                    func=self.interactive_exec_send_input,
                    description=await self.text("tools_desc.interactive_exec_send_input.desc"),
                    parameters={
                        "session_id": FunctionParameter(
                            type="string",
                            description=await self.text("tools_desc.interactive_exec_send_input.session_id"),
                            required=True,
                        ),
                        "input_text": FunctionParameter(
                            type="string",
                            description=await self.text("tools_desc.interactive_exec_send_input.input_text"),
                            required=True,
                        ),
                    },
                )
            )

            # interactive_exec_stop_session
            tools.append(
                AsyncFunction(
                    func=self.interactive_exec_stop_session,
                    description=await self.text("tools_desc.interactive_exec_stop_session.desc"),
                    parameters={
                        "session_id": FunctionParameter(
                            type="string",
                            description=await self.text("tools_desc.interactive_exec_stop_session.session_id"),
                            required=True,
                        ),
                    },
                )
            )

        if is_vm_available():
            # vm_create_task
            tools.append(
                AsyncFunction(
                    func=self.vm_create_task,
                    description=await self.text("tools_desc.vm_create_task.desc"),
                    parameters={
                        "command": FunctionParameter(
                            type="string",
                            description=await self.text("tools_desc.vm_create_task.command"),
                            required=True,
                        ),
                        "title": FunctionParameter(
                            type="string",
                            description=await self.text("tools_desc.vm_create_task.title"),
                            required=True,
                        ),
                    },
                )
            )

            # vm_get_task_state
            tools.append(
                AsyncFunction(
                    func=self.vm_get_task_state,
                    description=await self.text("tools_desc.vm_get_task_state.desc"),
                    parameters={
                        "task_id": FunctionParameter(
                            type="string",
                            description=await self.text("tools_desc.vm_get_task_state.task_id"),
                            required=True,
                        ),
                    },
                )
            )

            # vm_send_input
            tools.append(
                AsyncFunction(
                    func=self.vm_send_input,
                    description=await self.text("tools_desc.vm_send_input.desc"),
                    parameters={
                        "task_id": FunctionParameter(
                            type="string",
                            description=await self.text("tools_desc.vm_send_input.task_id"),
                            required=True,
                        ),
                        "input_text": FunctionParameter(
                            type="string",
                            description=await self.text("tools_desc.vm_send_input.input_text"),
                            required=True,
                        ),
                    },
                )
            )

            # vm_stop_task
            tools.append(
                AsyncFunction(
                    func=self.vm_stop_task,
                    description=await self.text("tools_desc.vm_stop_task.desc"),
                    parameters={
                        "task_id": FunctionParameter(
                            type="string",
                            description=await self.text("tools_desc.vm_stop_task.task_id"),
                            required=True,
                        ),
                    },
                )
            )

        if mode == "group":
            # get_note_poster
            tools.append(
                AsyncFunction(
                    func=self.push_note,
                    description=await self.text("tools_desc.get_note_poster.desc"),
                    parameters={
                        "text": FunctionParameter(
                            type="string",
                            description=await self.text("tools_desc.get_note_poster.text"),
                            required=True,
                        ),
                        "expire_hours": FunctionParameter(
                            type="integer",
                            description=await self.text("tools_desc.get_note_poster.expire_hours"),
                            required=False,
                        ),
                        "keywords": FunctionParameter(
                            type="string",
                            description=await self.text("tools_desc.get_note_poster.keywords"),
                            required=False,
                        )
                    },
                )
            )

            tools.append(
                AsyncFunction(
                    func=self.remove_note,
                    description=await self.text("tools_desc.get_note_remover.desc"),
                    parameters={
                        "note_id": FunctionParameter(
                            type="integer",
                            description=await self.text("tools_desc.get_note_remover.note_id"),
                            required=True,
                        ),
                    },
                )
            )

        return tools

    async def remove_note(self, note_id: int) -> Optional[str]:
        # Get the note manager for this context
        note_manager = await get_context_notes(self.processor.session.session_id)
        # Try to delete the note
        success = await note_manager.delete_note(note_id)
        if not success:
            return await self.text("note.remove_not_found", note_id)

    async def push_note(
        self, text: str, expire_hours: Optional[float] = None, keywords: Optional[str] = None
    ) -> Optional[str]:
        # Get the note manager for this context
        note_manager = await get_context_notes(self.processor.session.session_id)
        note_check_result = await check_note(self.processor.session, keywords, text, expire_hours)
        if note_check_result["create"] == False:
            return await self.text("note.not_create", note_check_result["comment"])
        text = note_check_result["text"]
        keywords = note_check_result["keywords"]
        expire_hours = note_check_result["expire_hours"]
        await note_manager.create_note(text, keywords or "", expire_hours)
        return await self.text("note.create_success")
