from nonebot import get_plugin_config
from pydantic import BaseModel
from nonebot_plugin_localstore import get_data_dir

class Config(BaseModel):
    """Plugin Config Here"""

    command_start: list[str] = ["/"]
    metaso_api_key: str = ""
    napcat_bot_ids: list[str] = []
    # VM 远程执行服务配置
    vm_api_url: str = ""  # VM 服务地址，如 http://localhost:8000
    vm_api_token: str = ""  # VM API 鉴权 Token
    moonlark_api_base: str = "http://localhost:8080"  # Moonlark API 基础地址
    # Skill 文件目录
    moonclaw_skill_dir: str = (get_data_dir("moonclaw") / "skills").as_posix()


config = get_plugin_config(Config)
