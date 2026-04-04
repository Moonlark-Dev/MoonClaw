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

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot_plugin_larkutils.superuser import is_user_superuser
from nonebot_plugin_larkutils import get_group_id, get_user_id
from nonebot.log import logger
from ..core.session import get_session_directly
from ..utils.timing_stats import timing_stats_manager
from datetime import datetime

state_matcher = on_command("state")

@state_matcher.handle()
async def handle_state(event: GroupMessageEvent | PrivateMessageEvent, is_superuser: bool = is_user_superuser(event)):
    # 检查用户是否为超级用户
    if not is_superuser:
        await state_matcher.finish("只有超级用户可以查看状态")

    try:
        if isinstance(event, GroupMessageEvent):
            session_id = await get_group_id()
            session_type = "群组"
        else:
            session_id = await get_user_id()
            session_type = "私聊"

        session = get_session_directly(session_id)
        status_info = session.processor.openai_messages.get_status_info()

        # 获取统计数据
        stats = timing_stats_manager.get_session_stats(session_id)
        global_stats = timing_stats_manager.get_global_stats()

        # 格式化状态信息
        status_text = f"【MessageQueue 状态】\n"
        status_text += f"会话类型: {session_type}\n"
        status_text += f"会话ID: {session_id}\n"
        status_text += f"当前状态: {status_info['status']}\n"
        status_text += f"消息数量: {status_info['message_count']}/{status_info['max_message_count']}\n"
        status_text += f"连续响应: {'是' if status_info['continuous_response'] else '否'}\n"
        status_text += f"请求锁定: {'是' if status_info['fetcher_lock_locked'] else '否'}\n"

        # 添加会话统计数据
        if stats:
            status_text += "\n【会话统计】\n"
            status_text += f"抓取次数: {stats.fetch_count}\n"
            status_text += f"平均抓取用时: {stats.avg_fetch_time_ms:.2f}ms\n" if stats.avg_fetch_time_ms else "平均抓取用时: N/A\n"
            status_text += f"回复次数: {stats.reply_count}\n"
            status_text += f"平均回应用时: {stats.avg_reply_time_ms:.2f}ms\n" if stats.avg_reply_time_ms else "平均回应用时: N/A\n"

        # 添加全局统计数据
        status_text += "\n【全局统计】\n"
        status_text += f"总抓取次数: {global_stats.fetch_count}\n"
        status_text += f"平均抓取用时: {global_stats.avg_fetch_time_ms:.2f}ms\n" if global_stats.avg_fetch_time_ms else "平均抓取用时: N/A\n"
        status_text += f"总回复次数: {global_stats.reply_count}\n"
        status_text += f"平均回应用时: {global_stats.avg_reply_time_ms:.2f}ms\n" if global_stats.avg_reply_time_ms else "平均回应用时: N/A\n"

        # 添加其他信息
        status_text += "\n【其他信息】\n"
        status_text += f"最后激活时间: {session.last_activate.strftime('%Y-%m-%d %H:%M:%S')}\n"
        status_text += f"冷却中: {'是' if session.processor.cold_until > datetime.now() else '否'}\n"
        status_text += f"已禁用: {'是' if not session.processor.enabled else '否'}\n"
        status_text += f"已阻塞: {'是' if session.processor.blocked else '否'}\n"

        await state_matcher.finish(status_text)
    except KeyError:
        await state_matcher.finish(f"会话不存在: {session_id}")
    except Exception as e:
        logger.exception(e)
        await state_matcher.finish(f"获取状态失败: {str(e)}")
