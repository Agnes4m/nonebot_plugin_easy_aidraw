"""nonebot_plugin_easy_aidraw"""

__version__ = "0.2.5"

from pydantic import BaseModel, ConfigDict


class EnvConfig(BaseModel):
    draw_api_url: str = ""
    draw_api_url_edits: str = ""
    draw_api_key: str = ""
    draw_model: str = ""
    draw_backend: str = ""
    draw_default_size: str = "1024x1024"
    draw_timeout: int = 120
    draw_proxy: str | None = None
    draw_nsfw_enabled: bool = False
    draw_nsfw_keywords: list[str] = []
    draw_whitelist_mode: bool = False
    draw_whitelist: list[str] = []
    draw_blacklist: list[str] = []
    draw_quality: str | None = None
    draw_n: int | None = None
    draw_user_cooldown: int = 60
    draw_concurrent: bool = False
    draw_cache_enabled: bool = False
    draw_cache_dir: str = "data/nonebot_plugin_easy_aidraw"
    draw_cache_ttl: int = 86400

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


from nonebot import require

require("nonebot_plugin_alconna")

from nonebot.plugin import PluginMetadata, inherit_supported_adapters

from .handler import clear_cache_command, draw_command

__plugin_meta__ = PluginMetadata(
    name="AI绘图",
    description="AI绘图插件，支持调用本地或远程的绘图API生成图片",
    usage=(
        "使用 /绘图 <提示词> 生成图片\n"
        "例如: /绘图 一只可爱的小猫\n"
        "可选参数: --model <模型> --size <尺寸> --n <数量>\n"
        "例如: /绘图 --model gpt-image-2 --size 1024x1792 风景\n"
        "超级用户: /清理绘图缓存 清理过期缓存"
    ),
    type="application",
    homepage="https://github.com/Agnes4m/nonebot_plugin_easy_aidraw",
    config=EnvConfig,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
    extra={"version": __version__, "author": "Agnes4m"},
)

__all__ = ["EnvConfig", "__plugin_meta__", "clear_cache_command", "draw_command"]
