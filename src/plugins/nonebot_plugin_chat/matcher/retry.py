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

import asyncio

from nonebot.matcher import Matcher
from nonebot import on_command
from nonebot.adapters import Event, Bot
from nonebot.typing import T_State
from nonebot_plugin_alconna import get_target
from nonebot_plugin_larkutils.superuser import is_user_superuser
from nonebot_plugin_larkutils import get_group_id, get_user_id
from nonebot.log import logger
from ..core.session import create_private_session, get_session_directly

from ..lang import lang

@on_command("retry").handle()
async def _(
    event: Event,
    matcher: Matcher,
    bot: Bot,
    state: T_State,
    user_id: str = get_user_id(),
    is_superuser: bool = is_user_superuser(),
) -> None:
    # 检查用户是否为SUPERUSER
    if not is_superuser:
        await matcher.finish()


    session = await create_private_session(user_id, get_target(event), bot)
    if session.mute_until is not None:
        await matcher.finish()
    asyncio.create_task(session.processor.generate_reply(True))
    await lang.finish("retry.started", user_id)
