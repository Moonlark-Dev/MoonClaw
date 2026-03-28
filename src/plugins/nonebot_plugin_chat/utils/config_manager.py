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

import json
from datetime import datetime
from typing import Any, Dict

from nonebot import logger
from nonebot_plugin_orm import get_session

from ..models import MoonClawConfig


class ConfigManager:
    """配置管理器，支持持久化存储"""

    async def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置项的键
            default: 默认值，当配置不存在时返回

        Returns:
            配置值，如果不存在则返回默认值
        """
        async with get_session() as session:
            config = await session.get(MoonClawConfig, key)

            if config is None:
                return default

            try:
                return json.loads(config.data_json)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse config value for key '{key}': {e}")
                return default

    async def set(self, key: str, value: Any) -> bool:
        """
        设置配置值

        Args:
            key: 配置项的键
            value: 配置值

        Returns:
            是否设置成功
        """
        # 序列化数据
        try:
            data_json = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize config value for key '{key}': {e}")
            return False

        # 保存到数据库
        async with get_session() as session:
            config = await session.get(MoonClawConfig, key)

            if config is None:
                config = MoonClawConfig(
                    key=key,
                    data_json=data_json,
                    updated_time=datetime.now()
                )
                session.add(config)
            else:
                config.data_json = data_json
                config.updated_time = datetime.now()

            await session.commit()
            logger.debug(f"Updated config: {key}")
            return True

    async def delete(self, key: str) -> bool:
        """
        删除配置项

        Args:
            key: 配置项的键

        Returns:
            是否删除成功
        """
        async with get_session() as session:
            config = await session.get(MoonClawConfig, key)

            if config is None:
                return False

            await session.delete(config)
            await session.commit()
            logger.debug(f"Deleted config: {key}")
            return True

    async def exists(self, key: str) -> bool:
        """
        检查配置项是否存在

        Args:
            key: 配置项的键

        Returns:
            是否存在
        """
        async with get_session() as session:
            config = await session.get(MoonClawConfig, key)
            return config is not None

    async def get_all(self) -> Dict[str, Any]:
        """
        获取所有配置项

        Returns:
            所有配置项的字典
        """
        from sqlalchemy import select

        async with get_session() as session:
            result = await session.scalars(select(MoonClawConfig))
            configs = result.all()

            config_dict = {}
            for config in configs:
                try:
                    config_dict[config.key] = json.loads(config.data_json)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse config value for key '{config.key}': {e}")
                    continue

            return config_dict

    async def clear(self) -> bool:
        """
        清空所有配置项

        Returns:
            是否清空成功
        """
        from sqlalchemy import select

        async with get_session() as session:
            result = await session.scalars(select(MoonClawConfig))
            configs = result.all()

            for config in configs:
                await session.delete(config)

            await session.commit()
            logger.debug("Cleared all configs")
            return True

    async def update(self, updates: Dict[str, Any]) -> Dict[str, bool]:
        """
        批量更新配置项

        Args:
            updates: 配置项字典

        Returns:
            每个配置项的更新结果
        """
        results = {}
        for key, value in updates.items():
            results[key] = await self.set(key, value)
        return results

config_manager = ConfigManager()