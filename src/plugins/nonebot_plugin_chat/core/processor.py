from nonebot.adapters.onebot.v11 import Bot as OB11Bot
from nonebot_plugin_openai.types import Message as OpenAIMessage
from nonebot.log import logger
from nonebot_plugin_larkuser import get_user
from nonebot_plugin_openai import generate_message
from nonebot_plugin_openai.utils.chat import fetch_message
from nonebot_plugin_orm import get_session
from sqlalchemy import select

import asyncio
import json
import random
import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, AsyncGenerator, Literal, Optional

from .message import MessageQueue
from ..types import CachedMessage

from ..utils.message import generate_message_string
from ..utils import parse_message_to_string
from ..utils.ai_agent import AskAISession
from ..utils.emoji import QQ_EMOJI_MAP
from ..utils.image import query_image_content
from ..utils.note_manager import get_context_notes
from ..utils.tool_manager import ToolManager
from ..utils.timing_stats import timing_stats_manager

if TYPE_CHECKING:
    from nonebot_plugin_chat.core.session.base import BaseSession


class MessageProcessor:

    def __init__(self, session: "BaseSession"):
        self.openai_messages = MessageQueue(self, 50)
        self.session = session
        self.enabled = True
        self.tool_manager = ToolManager(self)
        self.ai_agent = AskAISession(self.session.lang_str, self.tool_manager)
        self.cold_until = datetime.now()
        self.blocked = False
        self._latest_reasioning_content_cache = ""
        self.functions = []
        self.loop_task = None

    async def query_image(self, image_id: str, query_prompt: str) -> str:
        return await query_image_content(image_id, query_prompt, self.session.lang_str)

    async def setup(self) -> None:
        self.functions = await self.tool_manager.select_tools("group")
        await self.ai_agent.setup()
        if not self.loop_task:
            self.loop_task = asyncio.create_task(self.loop())

    async def send_reaction(self, message_id: str, emoji_id: str, set: bool = True) -> Optional[str]:
        if isinstance(self.session.bot, OB11Bot) and self.session.is_napcat_bot():
            await self.session.bot.call_api("set_msg_emoji_like", message_id=message_id, emoji_id=emoji_id, set=set)
        else:
            return await self.session.text("message.reaction_failed")

    async def loop(self) -> None:
        await self.openai_messages.restore_from_db()
        while self.enabled:
            try:
                await self.get_message()
            except Exception as e:
                logger.exception(e)
                await asyncio.sleep(5)


    async def get_message(self) -> None:
        if not self.session.message_queue:
            await asyncio.sleep(3)
            return
        trigger_mode: Literal["none", "probability", "all"] = "none"

        item = self.session.message_queue.pop(0)

        if item[0] == "event":
            # 处理事件类型队列项
            event_prompt, trigger_mode = item[1]  # type: ignore
            content = await self.session.text(
                "prompt.event_template", datetime.now().strftime("%H:%M:%S"), event_prompt
            )
            self.openai_messages.append_user_message(content)

        elif item[0] == "message":
            # 处理消息类型队列项
            message, event, state, user_id, nickname, dt, mentioned, message_id = item[1]
            text = await parse_message_to_string(message, event, self.session.bot, state, self.session.lang_str)
            if not text:
                return
            if "@Moonlark" not in text and mentioned:
                text = f"@Moonlark {text}"
            msg_dict: CachedMessage = {
                "content": text,
                "nickname": nickname,
                "send_time": dt,
                "user_id": user_id,
                "self": False,
                "message_id": message_id,
            }
            await self.process_messages(msg_dict)
            self.session.cached_messages.append(msg_dict)
            await self.session.on_cache_posted()
            trigger_mode = "probability" if not mentioned else "all"
        if (
            trigger_mode == "all" or trigger_mode == "probability" and not self.session.message_queue
        ) and not self.blocked:
            asyncio.create_task(self.generate_reply(trigger_mode == "all"))

    async def handle_timer(self, description: str) -> None:
        await self.session.add_event(
            await self.session.text("prompt.timer_triggered", datetime.now().strftime("%H:%M:%S"), description), "all"
        )

    async def leave_for_a_while(self) -> None:
        await self.session.mute()

    async def generate_reply(self, important: bool = False) -> None:
        # 延迟导入以避免循环导入

        # 如果在冷却期或消息为空，直接返回
        if self.cold_until > datetime.now():
            return
        if len(self.openai_messages.messages) <= 0 or not self.openai_messages.is_last_message_from_user():
            return
        self.cold_until = datetime.now() + timedelta(seconds=3)


        if self.session.get_session_type() == "group":
            self.openai_messages.continuous_response = self.openai_messages.continuous_response or important

        logger.info(f"Generating reply ({important=})...")
        await self.openai_messages.fetch_reply()

    async def append_tool_call_history(self, call_string: str) -> None:
        self.session.tool_calls_history.append(
            await self.session.text("tools.template", datetime.now().strftime("%H:%M"), call_string)
        )
        self.session.tool_calls_history = self.session.tool_calls_history[-5:]

    async def send_function_call_feedback(
        self, call_id: str, name: str, param: dict[str, Any]
    ) -> tuple[str, str, dict[str, Any]]:
        # 汇报工具调用
        report_message = await self.tool_manager.report_tool_call(name, param)
        if report_message:
            await self.send_message(report_message)

        return call_id, name, param

    async def send_message(self, message_content: str, reply_message_id: str | None = None) -> None:
        # 增加连续发送消息计数
        self.session.last_activate = datetime.now()
        message = await self.session.format_message(message_content)
        if reply_message_id:
            message = message.reply(reply_message_id)
        await message.send(target=self.session.target, bot=self.session.bot)

        # 记录回应用时（使用 reply_message_id 查找对应的原消息）
        self._record_reply_timing(reply_message_id)


    def _record_reply_timing(self, reply_message_id: str | None = None) -> None:
        """记录回应用时（从 reply_message_id 对应的消息到发送回复的时间）"""
        # 如果提供了 reply_message_id，查找对应的消息
        if reply_message_id is not None:
            for msg in self.session.cached_messages:
                if msg.get("message_id") == reply_message_id and not msg.get("self", False):
                    send_time = msg.get("send_time")
                    if send_time is not None:
                        reply_time_ms = (datetime.now() - send_time).total_seconds() * 1000
                        timing_stats_manager.record_reply_time(self.session.session_id, reply_time_ms)
                    return

    def append_user_message(self, msg_str: str) -> None:
        self.openai_messages.append_user_message(msg_str)

    async def process_messages(self, msg_dict: CachedMessage) -> None:
        async with get_session() as session:
            # TODO Block Check
            self.blocked = False

            if not self.blocked:
                msg_str = generate_message_string(msg_dict)
                self.append_user_message(msg_str)
            if not self.blocked and not msg_dict["self"]:
                content = msg_dict.get("content", "")
                if isinstance(content, str) and content:
                    cleaned = re.sub(r"\[.*?\]", "", content)
                    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    def get_message_content_list(self) -> list[str]:
        l = []
        for msg in self.openai_messages.messages:
            if isinstance(msg, dict):
                if "content" in msg and msg["role"] == "user":
                    l.append(str(msg["content"]))
            elif hasattr(msg, "content"):
                l.append(str(msg.content))
        return l


    
    async def generate_system_prompt(self) -> OpenAIMessage:
        chat_history = "\n".join(self.get_message_content_list())
        # 获取相关笔记
        note_manager = await get_context_notes(self.session.session_id)
        notes, notes_from_other_group = await note_manager.filter_note(chat_history)

        async def format_note(note):
            created_time = datetime.fromtimestamp(note.created_time).strftime("%y-%m-%d")
            return await self.session.text("prompt.note.format", note.content, note.id, created_time)

        return generate_message(
            await self.session.text(
                "prompt_group.default",
                # 0：当前会话的笔记
                (
                    "\n".join([await format_note(note) for note in notes])
                    if notes
                    else await self.session.text("prompt.note.none")
                ),
                # 1：当前时间
                await self.session.text("prompt_group.time", datetime.now().isoformat()),
                # 2：当前会话的名称
                self.session.session_name,
                # 3：来自其他会话的笔记
                (
                    "\n".join([await format_note(note) for note in notes_from_other_group])
                    if notes_from_other_group
                    else await self.session.text("prompt.note.none")
                ),
                # 4：身份信息
                await self.session.text("prompt_group.identify"),
                # 5：绝对行为准则
                await self.session.text("prompt_group.rule"),
            ),
            "system",
        )

