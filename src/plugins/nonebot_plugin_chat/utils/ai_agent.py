from datetime import datetime
from nonebot_plugin_openai import MessageFetcher
from nonebot_plugin_openai.utils.message import generate_message

from ..lang import lang
from .tool_manager import ToolManager


class AskAISession:

    def __init__(self, user_id: str, tool_manager: ToolManager) -> None:
        self.user_id = user_id
        self.tool_manager = tool_manager
        self.functions = []

    async def setup(self) -> None:
        self.functions = await self.tool_manager.select_tools("agent")

    # async def report_tool_call(self, call_id: str, name: str, params: dict) -> tuple[str, str, dict]:
    #     """汇报工具调用（用于 pre_function_call 回调）"""
    #     # 调用 tool_manager 的 report_tool_call 方法
    #     await self.tool_manager.report_tool_call(name, params)
    #     return call_id, name, params

    async def ask_ai(self, query: str) -> str:
        if not self.functions:
            await self.setup()
        fetcher = await MessageFetcher.create(
            [
                generate_message(await lang.text("prompt_agent.system", self.user_id, datetime.now().isoformat())),
                generate_message(query, "user"),
            ],
            False,
            functions=self.functions,
            identify="Ask AI",
            # pre_function_call=self.report_tool_call,
        )
        return await fetcher.fetch_last_message()
