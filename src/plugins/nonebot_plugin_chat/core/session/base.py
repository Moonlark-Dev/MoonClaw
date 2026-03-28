from nonebot.adapters import Bot, Event
from nonebot.adapters.onebot.v11.event import PokeNotifyEvent
from nonebot.log import logger
from nonebot.typing import T_State
from nonebot_plugin_alconna import Target, UniMessage, get_message_id
from nonebot_plugin_chat.lang import lang
from nonebot_plugin_chat.types import AdapterUserInfo, CachedMessage
from nonebot_plugin_larkuser import get_nickname, get_user


import math
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Literal, Optional, TypeAlias

# 消息队列项类型定义
MessageQueueItem: TypeAlias = (
    tuple[Literal["message"], tuple[UniMessage, Event, T_State, str, str, datetime, bool, str]]
    | tuple[Literal["event"], tuple[str, Literal["probability", "none", "all"]]]
)

from ..processor import MessageProcessor


class BaseSession(ABC):
    @staticmethod
    @abstractmethod
    def get_session_type() -> Literal["private", "group"]: ...

    def __init__(self, session_id: str, bot: Bot, target: Target, lang_str: str = f"mlsid::--lang=zh_hans") -> None:
        self.session_id = session_id
        self.target = target
        self.bot = bot
        self.lang_str = lang_str
        self.tool_calls_history = []
        self.message_queue: list[MessageQueueItem] = []
        self.cached_messages: list[CachedMessage] = []
        self.message_cache_counter = 0
        self.last_activate = datetime.now()
        self.mute_until: Optional[datetime] = None
        self.group_users: dict[str, str] = {}
        self.session_name = "未命名会话"
        self.llm_timers = []  # 定时器列表
        self.processor = MessageProcessor(self)


    @abstractmethod
    async def setup(self) -> None:
        await self.processor.setup()

    @abstractmethod
    def is_napcat_bot(self) -> bool:
        pass

    def clean_cached_message(self) -> None:
        if len(self.cached_messages) > 50:
            self.cached_messages = self.cached_messages[-50:]

    async def on_cache_posted(self) -> None:
        self.message_cache_counter += 1
        self.clean_cached_message()
        if self.message_cache_counter % 50 == 0:
            await self.setup_session_name()
        self.last_activate = datetime.now()

    async def mute(self) -> None:
        self.mute_until = datetime.now() + timedelta(minutes=15)

    @abstractmethod
    async def setup_session_name(self) -> None:
        pass

    async def handle_message(
        self, message: UniMessage, user_id: str, event: Event, state: T_State, nickname: str, mentioned: bool = False
    ) -> None:
        message_id = get_message_id(event)
        self.message_queue.append(
            ("message", (message, event, state, user_id, nickname, datetime.now(), mentioned, message_id))
        )

    async def add_event(
        self, event_prompt: str, trigger_mode: Literal["probability", "none", "all"] = "probability"
    ) -> None:
        """向消息队列中添加一个事件

        Args:
            event_prompt: 事件的描述文本
            trigger_mode: 触发模式
                - "none": 不触发回复
                - "probability": 使用概率计算判断是否触发回复
                - "all": 强制触发回复
        """
        self.message_queue.append(("event", (event_prompt, trigger_mode)))

    @abstractmethod
    async def format_message(self, origin_message: str) -> UniMessage:
        pass

    async def _get_users_in_cached_message(self) -> dict[str, str]:
        users = {}
        for message in self.cached_messages:
            if not message["self"]:
                users[message["nickname"]] = message["user_id"]
        return users

    @abstractmethod
    async def get_users(self) -> dict[str, str]:
        pass

    @abstractmethod
    async def get_user_info(self, user_id: str) -> AdapterUserInfo:
        pass

    async def text(self, key: str, *args, **kwargs) -> str:
        return await lang.text(key, self.lang_str, *args, **kwargs)


    async def process_timer(self) -> None:
        dt = datetime.now()
        if self.mute_until and dt > self.mute_until:
            self.mute_until = None

        triggered_timers = []
        for timer in self.llm_timers:
            if dt >= timer["trigger_time"]:
                description = timer["description"]
                await self.processor.handle_timer(description)
                triggered_timers.append(timer)
        for timer in triggered_timers:
            self.llm_timers.remove(timer)

        await self.processor.openai_messages.save_to_db()

    async def get_cached_messages_string(self) -> str:
        messages = []
        for message in self.cached_messages:
            messages.append(
                f"[{message['send_time'].strftime('%H:%M:%S')}][{message['nickname']}]: {message['content']}"
            )
        return "\n".join(messages)

    
    async def set_timer(self, delay: int, description: str = ""):
        """
        设置定时器

        Args:
            delay: 延迟时间（分钟）
            description: 定时器描述
        """
        # 获取当前时间
        now = datetime.now()
        # 计算触发时间（将分钟转换为秒）
        trigger_time = now + timedelta(minutes=delay)

        # 生成定时器ID
        timer_id = f"{self.session_id}_{now.timestamp()}"

        # 存储定时器信息
        self.llm_timers.append({"id": timer_id, "trigger_time": trigger_time, "description": description})

    async def post_event(self, event_prompt: str, trigger_mode: Literal["none", "probability", "all"]) -> None:
        """
        向消息队列中添加一个事件的文本

        Args:
            event_prompt: 事件的描述文本
            trigger_mode: 触发模式
                - "none": 不触发回复
                - "probability": 使用概率计算判断是否触发回复
                - "all": 强制触发回复
        """
        await self.add_event(event_prompt, trigger_mode)
