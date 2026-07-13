from __future__ import annotations

from collections import Counter
from threading import Lock

from nonebot.log import logger

_lock = Lock()
_counters: Counter[str] = Counter()


def hit(event: str) -> None:
    with _lock:
        _counters[event] += 1


def dump() -> None:
    with _lock:
        if not _counters:
            return
        line = " | ".join(f"{k}={v}" for k, v in sorted(_counters.items()))
        logger.info(f"[绘图指标] {line}")
