"""敏感词与文本归一化。"""

from __future__ import annotations

from functools import lru_cache

__all__ = ["match_nsfw", "normalize_text"]


@lru_cache(maxsize=1)
def _opencc_converter():
    try:
        from opencc import OpenCC  # type: ignore
    except Exception:
        return None
    try:
        return OpenCC("t2s")
    except Exception:
        return None


def normalize_text(text: str) -> str:
    cc = _opencc_converter()
    return (cc.convert(text) if cc else text).lower()


def match_nsfw(prompt: str, *, keywords: list[str], enabled: bool) -> tuple[bool, str | None]:
    if not enabled or not prompt:
        return False, None
    norm = normalize_text(prompt)
    for kw in keywords or ():
        if kw and kw.lower() in norm:
            return True, kw
    return False, None
