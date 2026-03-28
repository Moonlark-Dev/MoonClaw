from datetime import datetime
from typing import Literal, Optional, TypedDict

from nonebot_plugin_orm import Model
from pydantic import BaseModel, Field
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, LargeBinary, String, Text, Float, Integer
from sqlalchemy.dialects.mysql import MEDIUMBLOB, MEDIUMTEXT

# 创建跨数据库兼容的大文本类型：MySQL 使用 MEDIUMTEXT (16MB)，其他数据库使用 Text
CompatibleMediumText = Text().with_variant(MEDIUMTEXT(), "mysql")



class Note(Model):
    """Note model for storing user-generated notes with optional expiration and keywords"""

    id: Mapped[int] = mapped_column(Integer(), primary_key=True, autoincrement=True)
    context_id: Mapped[str] = mapped_column(String(128), index=True)  # user_id for private, group_id for groups
    content: Mapped[str] = mapped_column(Text())
    keywords: Mapped[str] = mapped_column(String(length=256), default="")
    created_time: Mapped[float] = mapped_column(Float())
    expire_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)  # Optional expiration time

class MessageQueueCache(Model):
    """消息队列缓存，用于持久化 OpenAI 消息历史以便重启后恢复"""

    group_id: Mapped[str] = mapped_column(String(128), primary_key=True)  # 群组 ID，主键确保每个群组只有一条记录
    # MySQL 使用 MEDIUMTEXT (16MB)，SQLite 使用 Text（无大小限制）
    messages_json: Mapped[str] = mapped_column(CompatibleMediumText)  # JSON 序列化的消息列表
    updated_time: Mapped[float] = mapped_column(Float())  # 最后更新时间戳

class PrivateChatSession(Model):
    """记录用户私聊会话信息，用于主动消息时获取正确的 bot"""

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    bot_id: Mapped[str] = mapped_column(String(128))  # 用户最后使用的 bot ID
    last_message_time: Mapped[float] = mapped_column(Float())  # 最后消息时间戳
    last_proactive_message_time: Mapped[Optional[float]] = mapped_column(Float(), nullable=True)  # 最后主动消息时间戳



class MoonClawConfig(Model):
    """MainSession 数据持久化存储，用于保存 action_history"""
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    data_json: Mapped[str] = mapped_column(Text())
    updated_time: Mapped[datetime] = mapped_column(DateTime(), default=datetime.now)
