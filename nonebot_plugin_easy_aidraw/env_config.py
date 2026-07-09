from pydantic import BaseModel, ConfigDict

from .backends import BACKEND_DEFAULTS, get_endpoint, resolve_edit_url


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
    draw_cache_ttl: int = 86400

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @property
    def model(self) -> str:
        return self.draw_model or BACKEND_DEFAULTS.get(self.draw_backend, {}).get("default_model", "flux")

    @property
    def api_url(self) -> str:
        return get_endpoint(self.draw_backend, self.draw_api_url, "txt2img")

    @property
    def api_url_edits(self) -> str:
        return resolve_edit_url(self.draw_backend, self.api_url, self.draw_api_url_edits)

    @property
    def headers(self) -> dict:
        hdrs = {"Content-Type": "application/json"}
        if self.draw_api_key:
            hdrs["Authorization"] = f"Bearer {self.draw_api_key}"
        return hdrs
