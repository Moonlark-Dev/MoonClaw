import asyncio
import json
import os
from pathlib import Path
from typing import Optional

import aiofiles
import frontmatter
from nonebot.log import logger

from ..lang import lang
from ..config import config


class Skill:
    def __init__(self, name: str, description: str, content: str, path: Path):
        self.name = name
        self.content = content
        self.path = path
        self.description = description
    
    @classmethod
    def from_text(cls, text: str, file: Path) -> "Skill":
        post = frontmatter.loads(text)
        name = str(post.metadata.get("name", file.stem))
        description = str(post.metadata.get("description", ""))
        return cls(name, description, post.content, file)

    def __str__(self) -> str:
        return self.content


class SkillManager:
    def __init__(self):
        self.skills: list[Skill] = []

    def get_skill_dir(self) -> Optional[Path]:
        if not config.moonclaw_skill_dir:
            return None
        return Path(config.moonclaw_skill_dir)

    async def load_skills(self) -> None:
        skill_dir = self.get_skill_dir()
        if not skill_dir or not skill_dir.exists():
            logger.warning(f"Skill directory not found: {skill_dir}")
            return

        for skill_dir in skill_dir.iterdir():
            try:
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    if skill_dir in [skill.path for skill in self.skills]:
                        continue
                    async with aiofiles.open(skill_dir / "SKILL.md", "r", encoding="utf-8") as f:
                        text = await f.read()
                        skill = Skill.from_text(text, skill_dir)
                    self.skills.append(skill)
                    logger.info(f"Loaded skill: {skill.name}")
            except Exception as e:
                logger.error(f"Failed to load skill {skill_dir.name}: {e}")


    async def get_skills_content(self, lang_str: str) -> str:
        await self.load_skills()
        return "\n".join([await lang.text("skill.item", lang_str, skill.name, skill.path.as_posix(), skill.description) for skill in self.skills])


skill_manager = SkillManager()