from datetime import datetime

from nonebot import on_message
from nonebot.adapters.onebot.v11 import NoticeEvent
from nonebot.adapters.qq import Bot as BotQQ
from nonebot.typing import T_State
from nonebot_plugin_alconna import UniMessage, get_target
from nonebot.adapters.onebot.v11.event import FriendRecallNoticeEvent
from nonebot_plugin_chat.utils.message import parse_dict_message
from nonebot_plugin_larkuser import get_nickname
from nonebot_plugin_orm import get_session

from nonebot_plugin_larkuser import get_user
from nonebot import on_message, on_notice
from nonebot.adapters.onebot.v11 import Bot as OB11Bot
from nonebot.adapters import Event, Bot
from nonebot.adapters.onebot.v11.event import PokeNotifyEvent
from nonebot_plugin_larkutils import get_user_id, get_group_id
from nonebot_plugin_larkutils.subaccount import get_main_account
from nonebot_plugin_larkutils.user import private_message
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import GroupRecallNoticeEvent

from .session import create_group_session, create_private_session, get_session_directly

from ..utils.group import enabled_group, parse_message_to_string
from ..config import config
from ..models import PrivateChatSession


async def record_private_chat_session(user_id: str, bot_id: str) -> None:
    """记录用户私聊会话信息

    Args:
        user_id: 用户 ID
        bot_id: Bot ID
    """
    async with get_session() as session:
        chat_session = PrivateChatSession(
            user_id=user_id,
            bot_id=bot_id,
            last_message_time=datetime.now().timestamp(),
        )
        await session.merge(chat_session)
        await session.commit()


# @on_message(priority=50, rule=enabled_group, block=False).handle()
# async def _(
#     event: Event,
#     matcher: Matcher,
#     bot: Bot,
#     state: T_State,
#     user_id: str = get_user_id(),
#     session_id: str = get_group_id(),
# ) -> None:
#     if isinstance(bot, BotQQ):
#         await matcher.finish()
#     session = await create_group_session(session_id, get_target(event), bot)
#     if session.mute_until is not None:
#         await matcher.finish()
#     plaintext = event.get_plaintext().strip()
#     if any([plaintext.startswith(p) for p in config.command_start]):
#         await matcher.finish()
#     platform_message = event.get_message()
#     message = await UniMessage.of(message=platform_message, bot=bot).attach_reply(event, bot)
#     nickname = await get_nickname(user_id, bot, event)
#     await session.handle_message(message, user_id, event, state, nickname, event.is_tome())


@on_message(priority=50, rule=private_message, block=False).handle()
async def _(
    event: Event,
    matcher: Matcher,
    bot: Bot,
    state: T_State,
    user_id: str = get_user_id(),
) -> None:
    if isinstance(bot, BotQQ):
        await matcher.finish()

    # NOTE 用于测试
    if user_id != "1744793737":
        await matcher.finish()

    # 记录私聊会话信息（用于主动消息时获取正确的 bot）
    await record_private_chat_session(user_id, bot.self_id)

    session = await create_private_session(user_id, get_target(event), bot)
    if session.mute_until is not None:
        await matcher.finish()
    plaintext = event.get_plaintext().strip()
    if any([plaintext.startswith(p) for p in config.command_start]):
        # TODO 避免与 cave 冲突
        await matcher.finish()
    platform_message = event.get_message()
    message = await UniMessage.of(message=platform_message, bot=bot).attach_reply(event, bot)
    nickname = await get_nickname(user_id, bot, event)
    await session.handle_message(message, user_id, event, state, nickname, True)

