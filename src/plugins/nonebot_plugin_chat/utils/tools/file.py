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

"""
文件读取工具模块

提供读取本地文件内容的工具函数。
"""

import os
from typing import Optional
from nonebot.log import logger

from ..config_manager import config_manager
from ...types import GetTextFunc


async def read_file(
    file_path: str,
    get_text: GetTextFunc,
    encoding: Optional[str] = "utf-8",
    max_lines: Optional[int] = None,
    offset: Optional[int] = None,
) -> str:
    """
    读取指定文件的 contents

    Args:
        file_path: 要读取的文件路径
        encoding: 文件编码，默认 utf-8
        max_lines: 最大读取行数，默认 None 表示读取全部
        offset: 跳过的行数，默认 None 表示从开头开始
        get_text: 获取本地化文本的函数

    Returns:
        文件内容
    """
    if not await config_manager.get("read_file_enabled", True):
        return await get_text("read_file.disabled")

    if not os.path.exists(file_path):
        return await get_text("read_file.not_found", file_path)

    if not os.path.isfile(file_path):
        return await get_text("read_file.not_file", file_path)

    try:
        with open(file_path, "r", encoding=encoding) as f:
            if offset:
                for _ in range(offset):
                    if not f.readline():
                        break
            if max_lines:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line.rstrip("\n"))
                content = "\n".join(lines)
                offset_str = f" (从第 {offset + 1} 行开始)" if offset else ""
                return await get_text("read_file.success_with_limit", file_path, max_lines, offset_str, content)
            else:
                content = f.read()
                return await get_text("read_file.success", file_path, content)
    except UnicodeDecodeError:
        return await get_text("read_file.encoding_error", file_path)
    except PermissionError:
        return await get_text("read_file.permission_denied", file_path)
    except Exception as e:
        logger.exception(e)
        return await get_text("read_file.error", file_path, str(e))