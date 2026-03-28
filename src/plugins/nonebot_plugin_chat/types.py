from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional, Protocol, TypedDict

# from nonebot_plugin_chat.models import RuaAction



class CachedMessage(TypedDict):
    content: str
    nickname: str
    user_id: str
    send_time: datetime
    self: bool
    message_id: str


class GetTextFunc(Protocol):
    # 在这里精确模拟你的函数签名
    async def __call__(self, key: str, *args: Any, **kwargs: Any) -> str: ...




class AvailableNote(TypedDict):
    create: Literal[True]
    text: str
    expire_hours: float
    keywords: Optional[str]
    comment: str


class InvalidNote(TypedDict):
    create: Literal[False]
    comment: str


NoteCheckResult = AvailableNote | InvalidNote


class AdapterUserInfo(TypedDict):
    sex: Literal["male", "female", "unknown"]
    role: Literal["member", "admin", "owner", "user"]
    nickname: str
    join_time: int
    card: Optional[str]

