from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import date
from pathlib import Path
import time
import uuid

from nonebot.log import logger
from nonebot_plugin_localstore import get_plugin_cache_dir

from .config_loader import get_config

__all__ = ["b64_to_path", "cleanup_cache", "temp_b64_path"]

_CACHE_EXT = frozenset({".png", ".jpg", ".jpeg", ".webp", ".tmp"})


def _cache_root() -> Path:
    return get_plugin_cache_dir()


def _decode(b64: str) -> bytes:
    return base64.b64decode(b64)


@contextmanager
def temp_b64_path(b64: str):
    path = _cache_root() / f".tmp-{uuid.uuid4().hex}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_decode(b64))
    try:
        yield path
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError as e:
            logger.warning(f"[绘图] 临时文件清理失败 {path}: {e}")


def b64_to_path(b64: str) -> tuple[Path, bool]:
    cfg = get_config()
    root = _cache_root()
    if cfg.draw_cache_enabled:
        cache_dir = root / date.today().isoformat()
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = cache_dir / f"{uuid.uuid4().hex}.png"
        path.write_bytes(_decode(b64))
        logger.info(f"[绘图] 已保存缓存: {path}")
        return path, False
    path = root / f".tmp-{uuid.uuid4().hex}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_decode(b64))
    return path, True


def cleanup_cache(ttl: int | None = None) -> tuple[int, int]:
    cfg = get_config()
    cache_root = _cache_root()
    if not cache_root.exists():
        return 0, 0
    threshold = time.time() - (ttl if ttl is not None else cfg.draw_cache_ttl)
    deleted = remaining = 0
    for p in cache_root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in _CACHE_EXT:
            continue
        try:
            if p.stat().st_mtime < threshold:
                p.unlink()
                deleted += 1
            else:
                remaining += 1
        except OSError as e:
            logger.warning(f"[绘图] 清理失败 {p}: {e}")
    for d in sorted(cache_root.rglob("*"), reverse=True):
        if d.is_dir():
            try:
                d.rmdir()
            except OSError:
                pass
    logger.info(f"[绘图] 缓存清理: 删除={deleted}, 剩余={remaining}")
    return deleted, remaining
