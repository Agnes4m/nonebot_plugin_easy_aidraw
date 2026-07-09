from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot import get_driver

from ..env_config import EnvConfig
from .filters import match_nsfw

if TYPE_CHECKING:
    from nonebot.adapters import Event

__all__ = ["check_nsfw", "check_whitelist_blacklist", "get_config", "reset_config_cache"]

_config: EnvConfig | None = None


def reset_config_cache() -> None:
    global _config
    _config = None


def get_config() -> EnvConfig:
    global _config
    if _config is not None:
        return _config
    _config = EnvConfig(**dict(get_driver().config))
    return _config


def check_whitelist_blacklist(event: Event) -> tuple[bool, str]:
    cfg = get_config()
    user_id = event.get_user_id()
    if cfg.draw_whitelist_mode:
        return (user_id in cfg.draw_whitelist, "不在白名单中")
    return (user_id not in cfg.draw_blacklist, "在黑名单中")


def check_nsfw(prompt: str) -> tuple[bool, str | None]:
    cfg = get_config()
    return match_nsfw(
        prompt,
        keywords=cfg.draw_nsfw_keywords,
        enabled=cfg.draw_nsfw_enabled,
    )
