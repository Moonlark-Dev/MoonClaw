import re
import traceback
from typing import TYPE_CHECKING, Literal, Optional
from nonebot.compat import type_validate_python
from nonebot.log import logger

# from nonebot_plugin_chat.utils.emoji import QQ_EMOJI_MAP
from nonebot_plugin_chat.utils.role import get_role
from nonebot_plugin_chat.models import MessageQueueCache
from nonebot_plugin_chat.utils.enums import FetchStatus
from nonebot_plugin_openai import generate_message
from nonebot_plugin_openai.utils.chat import MessageFetcher
from nonebot_plugin_orm import get_session
from openai.types.chat import ChatCompletionMessage
from nonebot_plugin_openai.types import Message as OpenAIMessage

import asyncio
import copy
import json
from datetime import datetime

from ..utils.timing_stats import timing_stats_manager
from ..utils.config_manager import config_manager

if TYPE_CHECKING:
    from nonebot_plugin_chat.core.processor import MessageProcessor


class MessageQueue:

    def __init__(
        self,
        processor: "MessageProcessor",
        max_message_count: int = 50,
    ) -> None:
        self.processor = processor
        self.instant_memory_generator_lock = asyncio.Lock()
        self.max_message_count = max_message_count
        self.messages: list[OpenAIMessage] = []
        self.fetcher_lock = asyncio.Lock()
        self.continuous_response = False
        self.fetcher_task = None
        # 在初始化时从数据库恢复消息队列
        self.inserted_messages = []

    def _serialize_message(self, message: OpenAIMessage) -> dict:
        """将 OpenAIMessage 序列化为可 JSON 化的字典"""
        if isinstance(message, dict):
            return message  # type: ignore
        # 如果是 Pydantic 模型或其他对象，转换为字典
        if hasattr(message, "model_dump"):
            return message.model_dump()
        elif hasattr(message, "__dict__"):
            return dict(message.__dict__)
        else:
            return {"content": str(message), "role": "user"}

    def _serialize_messages(self) -> str:
        """将消息列表序列化为 JSON 字符串"""
        serialized = [self._serialize_message(msg) for msg in self.messages]
        return json.dumps(serialized, ensure_ascii=False)

    async def restore_from_db(self) -> None:
        """从数据库恢复消息队列"""
        try:
            group_id = self.processor.session.session_id
            async with get_session() as session:
                cache = await session.get(MessageQueueCache, {"group_id": group_id})
                if cache:
                    self.messages = json.loads(cache.messages_json)
                    logger.info(f"已从数据库恢复群 {group_id} 的消息队列，共 {len(self.messages)} 条消息")
        except Exception as e:
            logger.warning(f"从数据库恢复消息队列失败: {e}")

    async def save_to_db(self) -> None:
        """将消息队列保存到数据库"""
        try:
            async with self.fetcher_lock:
                group_id = self.processor.session.session_id
                async with get_session() as session:
                    cache = MessageQueueCache(
                        group_id=group_id,
                        messages_json=self._serialize_messages(),
                        updated_time=datetime.now().timestamp(),
                    )
                    await session.merge(cache)
                    await session.commit()
        except Exception as e:
            logger.exception(e)

    def clean_special_message(self) -> None:
        while True:
            role = get_role(self.messages[0])
            if role in ["user", "assistant"]:
                break
            self.messages.pop(0)

    async def get_messages(self) -> list[OpenAIMessage]:
        self.clean_special_message()
        self.messages = self.messages[-self.max_message_count :]
        messages = copy.deepcopy(self.messages)
        messages.insert(0, await self.processor.generate_system_prompt())
        return messages

    async def fetch_reply(self) -> None:
        if self.fetcher_lock.locked():
            return

        # 记录抓取开始时间
        session_id = self.processor.session.session_id
        timing_stats_manager.record_fetch_start(session_id)

        async with self.fetcher_lock:
            self.fetcher_task = asyncio.create_task(self._fetch_reply())
            status = await self.fetcher_task
            logger.info(f"Reply fetcher ended with status: {status.name}")

        if self.continuous_response and self.processor.session.get_session_type() == "group":
            self.continuous_response = False

        # 记录抓取结束时间
        timing_stats_manager.record_fetch_end(session_id)


    async def stop_fetcher(self) -> None:
        if self.fetcher_task:
            self.fetcher_task.cancel()

    async def retry_callback(self, retry_count: int, status: Literal["retrying", "failed"]) -> None:
        retry_feedback_level = await config_manager.get("retry_feedback_level", 1)
        if status == "retrying" and retry_feedback_level >= 2:
            message = f"⚠️ 请求失败，正在重试 ({retry_count})..."
        elif status == "failed" and retry_feedback_level >= 1:
            message = f"❌ 请求失败，已达到最大重试次数 ({retry_count})"
        else:
            return
        await self.processor.send_message(message)


    async def _fetch_reply(self) -> FetchStatus:
        state = FetchStatus.SUCCESS
        messages = await self.get_messages()
        if get_role(messages[-1]) == "assistant":
            return FetchStatus.SKIP
        self.messages.clear()
        self.inserted_messages.clear()

        max_retries = await config_manager.get("message_queue_max_retries", 5)


        fetcher = await MessageFetcher.create(
            messages,
            False,
            identify="Chat",
            reasoning_effort="medium",
            functions=await self.processor.tool_manager.select_tools("group"),
            pre_function_call=self.processor.send_function_call_feedback
        )
        for retry_count in range(max_retries):
            try:
                async for message in fetcher.fetch_message_stream():
                    if not message:
                        continue
                    if self.continuous_response:
                        fetcher.session.insert_messages(self.messages)
                        self.messages.clear()
                    await self.processor.send_message(message)
                self.messages = fetcher.get_messages() + self.messages
                break
            except Exception as e:
                retry_count += 1
                logger.exception(e)
                await self.retry_callback(retry_count, "failed" if retry_count == max_retries else "retrying")
        else:
            # 恢复 Message
            self.messages = messages + self.inserted_messages
            self.inserted_messages.clear()

                
                    
        return state

    def append_user_message(self, message: str) -> None:
        self.messages.append(generate_message(message, "user"))

    def is_last_message_from_user(self) -> bool:
        return get_role(self.messages[-1]) == "user"

    def get_status(self) -> str:
        """获取当前状态
        
        Returns:
            str: 当前状态，可能为 "已失败"、"请求中" 或 "待命"
        """
        if self.fetcher_task:
            if self.fetcher_task.done():
                if self.fetcher_task.cancelled():
                    return "已失败"
                try:
                    result = self.fetcher_task.result()
                    if result == FetchStatus.FAILED:
                        return "已失败"
                    elif result in (FetchStatus.SUCCESS, FetchStatus.SKIP):
                        return "待命"
                except Exception:
                    return "已失败"
            else:
                return "请求中"
        return "待命"

    def get_status_info(self) -> dict:
        """获取详细状态信息
        
        Returns:
            dict: 包含详细状态信息的字典
        """
        return {
            "status": self.get_status(),
            "message_count": len(self.messages),
            "max_message_count": self.max_message_count,
            "continuous_response": self.continuous_response,
            "fetcher_lock_locked": self.fetcher_lock.locked(),
            "fetcher_task_done": self.fetcher_task.done() if self.fetcher_task else None,
        }
