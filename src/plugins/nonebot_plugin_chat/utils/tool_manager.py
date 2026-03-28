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
)
from ..utils.emoji import QQ_EMOJI_MAP
from .note_manager import check_note, get_context_notes

if TYPE_CHECKING:
    from ..core.processor import MessageProcessor


class ToolManager:
    def __init__(self, processor: "MessageProcessor"):
        self.processor = processor

    async def text(self, key: str, *args, **kwargs) -> str:
        return await self.processor.session.text(key, *args, **kwargs)

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
        await note_manager.create_note(content=text, keywords=keywords or "", expire_hours=expire_hours or 87600)
