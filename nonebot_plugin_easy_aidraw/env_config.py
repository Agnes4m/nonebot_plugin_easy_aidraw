from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .backends import BACKEND_DEFAULTS, get_endpoint, resolve_edit_url

# pydantic v2 提供 ``model_validator``；v1 没有，提供的是 ``validator``。
try:
    from pydantic import model_validator as _model_validator

    _PYDANTIC_V2 = True
except ImportError:  # pragma: no cover - pydantic v1
    from pydantic import validator as _model_validator  # type: ignore[assignment]

    _PYDANTIC_V2 = False


def _materialize(instance) -> None:
    """派生字段物化逻辑 —— v1/v2 共用同一份实现。"""
    instance.model = instance.draw_model or BACKEND_DEFAULTS.get(instance.draw_backend, {}).get(
        "default_model", "flux"
    )
    instance.api_url = get_endpoint(instance.draw_backend, instance.draw_api_url, "txt2img")
    instance.api_url_edits = resolve_edit_url(
        instance.draw_backend, instance.api_url, instance.draw_api_url_edits
    )
    hdrs: Dict[str, str] = {"Content-Type": "application/json"}
    if instance.draw_api_key:
        hdrs["Authorization"] = f"Bearer {instance.draw_api_key}"
    instance.headers = hdrs


class EnvConfig(BaseModel):
    """绘图插件配置，初始化后派生字段一次性计算并缓存到实例属性。"""

    draw_api_url: str = ""
    draw_api_url_edits: str = ""
    draw_api_key: str = ""
    draw_model: str = ""
    draw_backend: str = ""
    draw_default_size: str = "1024x1024"
    draw_timeout: int = 120
    draw_proxy: Optional[str] = None
    draw_nsfw_enabled: bool = False
    draw_nsfw_keywords: List[str] = []
    draw_whitelist_mode: bool = False
    draw_whitelist: List[str] = []
    draw_blacklist: List[str] = []
    draw_quality: Optional[str] = None
    draw_n: Optional[int] = None
    draw_user_cooldown: int = 60
    draw_concurrent: bool = False
    draw_cache_enabled: bool = False
    draw_cache_ttl: int = 86400

    # 派生字段：启动时一次性计算，避免每次访问重复字符串拼接。
    model: str = ""
    api_url: str = ""
    api_url_edits: str = ""
    headers: Dict[str, str] = Field(default_factory=dict)

    def __init__(self, **data):  # type: ignore[override]
        super().__init__(**data)
        _materialize(self)


if _PYDANTIC_V2:
    EnvConfig._materialize = _model_validator(mode="after")(
        lambda self: (_materialize(self), self)[1]
    )
