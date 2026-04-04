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
from nonebot_plugin_larkutils import get_user_id
from nonebot.log import logger
from ..core.session import create_private_session, reset_session

from ..lang import lang


@on_command("new").handle()
async def _(
    event: Event,
    user_id: str = get_user_id(),
    is_superuser: bool = is_user_superuser(),
) -> None:
    if not is_superuser:
        return

    logger.info(f"Resetting session for user {user_id}")
    await reset_session(user_id)
    
    await lang.send("new.completed", user_id)
