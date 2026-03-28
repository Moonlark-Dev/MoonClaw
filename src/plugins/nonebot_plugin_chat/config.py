from nonebot import get_plugin_config
from pydantic import BaseModel


class Config(BaseModel):
    """Plugin Config Here"""

    command_start: list[str] = ["/"]
    metaso_api_key: str = ""
    napcat_bot_ids: list[str] = []
    # VM 远程执行服务配置
    vm_api_url: str = ""  # VM 服务地址，如 http://localhost:8000
    vm_api_token: str = ""  # VM API 鉴权 Token
    moonlark_api_base: str = "http://localhost:8080"  # Moonlark API 基础地址
    # exec 工具配置
    exec_enabled: bool = True  # 是否启用 exec 工具
    exec_timeout: int = 30  # 命令执行超时时间（秒）
    exec_max_output_length: int = 4000  # 最大输出长度
    exec_allowed_commands: list[str] | None = None  # 允许执行的命令白名单
    exec_blocked_commands: list[str] = ["rm", "del", "format"]  # 禁止执行的命令黑名单


config = get_plugin_config(Config)
