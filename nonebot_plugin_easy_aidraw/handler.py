from __future__ import annotations

import asyncio
import base64
from pathlib import Path
import time

from arclet.alconna import Alconna, Args, Arparma, CommandMeta, Option
import httpx
from nonebot import Bot, get_driver
from nonebot.adapters import Event
from nonebot.log import logger
from nonebot.permission import SUPERUSER
from nonebot_plugin_alconna import Image, UniMessage, UniMsg, on_alconna

from .api import (
    check_nsfw,
    check_whitelist_blacklist,
    cleanup_cache,
    edit_image,
    generate_image,
    get_config,
)
from .metrics import dump, hit

__all__ = ["clear_cache_command", "draw_command"]

_DOWNLOAD_TIMEOUT = 60

draw_alc = Alconna(
    "绘图",
    Args["prompt", str],
    Option("--model", Args["model", str], help_text="指定模型"),
    Option("--size", Args["size", str], help_text="指定图片尺寸，如 1024x1024"),
    Option("--n", Args["n", int], help_text="生成数量"),
    meta=CommandMeta(
        description="AI绘图命令",
        example="/绘图 一只可爱的小猫\n/绘图 --model gpt-image-1.5 --size 1024x1792 风景",
    ),
    separators=("", " "),
)
draw_command = on_alconna(
    draw_alc, auto_send_output=False, use_origin=False, skip_for_unmatch=False, response_self=True
)

clear_cache_alc = Alconna(
    "清理绘图缓存",
    meta=CommandMeta(description="清理过期绘图缓存（SUPERUSER）", example="/清理绘图缓存"),
)
clear_cache_command = on_alconna(clear_cache_alc, auto_send_output=False, permission=SUPERUSER)

_draw_lock = asyncio.Lock()
_pending = 0
_user_last_request: dict[str, float] = {}


def _to_data_uri(data: bytes) -> str:
    return f"base64://{base64.b64encode(data).decode()}"


async def _send_single(result: str | Path) -> None:
    if isinstance(result, Path):
        await UniMessage.image(url=_to_data_uri(result.read_bytes())).send()
        return
    try:
        await UniMessage.image(url=result).send()
    except Exception as e:
        logger.warning(f"[绘图] URL 发送失败，回退下载转 base64: {e}")
        async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT, trust_env=False) as client:
            data = (await client.get(result)).content
        await UniMessage.image(url=_to_data_uri(data)).send()


def _check_cooldown(user_id: str, cooldown_sec: int) -> tuple[bool, int]:
    if cooldown_sec <= 0 or (last := _user_last_request.get(user_id)) is None:
        return True, 0
    remain = cooldown_sec - int(time.time() - last)
    return (True, 0) if remain <= 0 else (False, remain)


def _find_image_segment(event: Event, unimsg: UniMsg):
    if event.reply:
        for seg in event.reply.message:
            if seg.type == "image":
                return seg
    for img in unimsg[Image]:
        return img
    return None


async def _download_bytes(url: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT, trust_env=False) as client:
            data = (await client.get(url)).content
        logger.debug(f"[绘图] URL 下载成功 url={url} size={len(data)}")
        return data
    except Exception as e:
        logger.warning(f"[绘图] URL 下载失败 ({url}): {type(e).__name__}: {e}")
        return None


async def _fetch_image_bytes(bot: Bot, seg) -> bytes | None:
    data = seg.data or {}
    logger.debug(
        f"[绘图] 垫图 segment.data keys={sorted(data.keys())} "
        f"has_base64={bool(data.get('base64'))} has_url={bool(data.get('url'))} has_file={bool(data.get('file'))}"
    )

    if data.get("base64"):
        try:
            decoded = base64.b64decode(data["base64"])
        except Exception as e:
            logger.warning(f"[绘图] base64 解码失败: {e}")
            return None
        logger.debug(f"[绘图] 走 base64 路径, decoded={len(decoded)} bytes")
        return decoded

    if url := data.get("url"):
        logger.debug(f"[绘图] 走 URL 路径: {url}")
        return await _download_bytes(url)

    file_ref = data.get("file")
    if not file_ref:
        logger.warning("[绘图] 未能获取垫图: segment 缺少 base64/url/file 任意字段")
        return None

    logger.debug(f"[绘图] 走 get_image 路径: file={file_ref}")
    try:
        resp = await bot.call_api("get_image", file=file_ref)
    except Exception as e:
        logger.debug(f"[绘图] get_image 不可用 ({file_ref}): {type(e).__name__}: {e}")
        return None
    if not isinstance(resp, dict):
        return None
    logger.debug(f"[绘图] get_image 返回 content_keys={sorted(resp.keys())}")
    if resp.get("base64"):
        return base64.b64decode(resp["base64"])
    if resp.get("url"):
        return await _download_bytes(resp["url"])
    return None


def _is_group(event: Event) -> bool:
    return event.get_session_id().startswith(("group_", "channel_"))


async def _finish_with(text: str):
    return await UniMessage.text(text).finish()


def _format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f} 毫秒"
    if seconds < 60:
        return f"{seconds:.1f} 秒"
    mins, secs = divmod(int(seconds), 60)
    return f"{mins}分{secs}秒"


def _format_token_usage(usage: dict) -> str:
    parts = []
    if usage.get("input_tokens"):
        parts.append(f"输入 {usage['input_tokens']}")
    if usage.get("output_tokens"):
        parts.append(f"输出 {usage['output_tokens']}")
    if usage.get("total_tokens") and not (usage.get("input_tokens") or usage.get("output_tokens")):
        parts.append(f"总计 {usage['total_tokens']}")
    return "、".join(parts) + " tokens" if parts else ""


def _build_summary(used_model: str, duration_text: str, usage: dict, count: int, mode: str) -> str:
    mode_label = "文生图" if mode == "txt2img" else "图生图"
    parts = [f"⏱️ 耗时 {duration_text}", f"🎯 {mode_label}"]
    if token_text := _format_token_usage(usage):
        parts.append(f"📊 消耗 {token_text}")
    parts.append(f"🖼️ {count} 张")
    parts.append(f"🧠 {used_model}")
    return " | ".join(parts)


async def _do_generate(
    prompt: str, image_b64: str | None, *, size: str | None = None, n: int | None = None
) -> tuple[list[str | Path], dict]:
    if image_b64:
        return await edit_image(prompt, image_b64, size=size, n=n)
    return await generate_image(prompt, size=size, n=n)


@draw_command.handle()
async def handle_draw(bot: Bot, event: Event, arp: Arparma, unimsg: UniMsg):
    global _pending

    user_id = event.get_user_id()
    logger.debug(f"[绘图] handle_draw 入口 user={user_id} arp.main_args={arp.main_args}")

    if not (passed := check_whitelist_blacklist(event))[0]:
        hit("blacklist")
        return await _finish_with(f"❌ 访问被拒绝：{passed[1]}")

    prompt = (arp.main_args.get("prompt", "") or "").strip() or unimsg.extract_plain_text().strip()
    if not prompt:
        return await _finish_with("❌ 请提供绘图提示词\n例如: /绘图 一只可爱的小猫")
    logger.debug(f"[绘图] prompt={prompt!r} len={len(prompt)}")

    cfg = get_config()
    is_superuser = user_id in set(get_driver().config.superusers)
    logger.debug(f"[绘图] cfg.model={cfg.model} backend={cfg.draw_backend} super={is_superuser}")

    if not is_superuser:
        ok, remain = _check_cooldown(user_id, cfg.draw_user_cooldown)
        if not ok:
            hit("cooldown")
            mins, secs = divmod(remain, 60)
            return await _finish_with(f"⏳ 冷却中，还需等待 {mins}分{secs}秒")

    if _is_group(event) and (nsfw_hit := check_nsfw(prompt))[0]:
        hit("nsfw_blocked")
        return await _finish_with(f"❌ 检测到敏感词「{nsfw_hit[1]}」")

    image_b64: str | None = None
    seg = _find_image_segment(event, unimsg)
    if seg:
        image_bytes = await _fetch_image_bytes(bot, seg)
        if image_bytes is None:
            return await _finish_with("❌ 获取垫图失败，请重试或联系管理员")
        image_b64 = base64.b64encode(image_bytes).decode()
        logger.info(f"[绘图] 垫图就绪: {len(image_bytes)} bytes b64_len={len(image_b64)}")

    mode = "img2img" if image_b64 else "txt2img"
    hit(mode)

    used_model = (arp.options.get("model", {}) or {}).get("model") or cfg.model
    size_opt = (arp.options.get("size", {}) or {}).get("size")
    count_opt = (arp.options.get("n", {}) or {}).get("n")
    _pending += 1
    queue_hint = f"（前面还有 {_pending - 1} 个请求）..." if _pending > 1 else "..."
    mode_label = "文生图" if mode == "txt2img" else "图生图"
    await UniMessage.text(f"🎨 {mode_label} | 正在使用 {used_model} 生成中{queue_hint}").send()
    logger.info(f"[绘图] 请求: prompt={prompt!r}, model={used_model}, mode={mode}")

    start_ts = 0.0
    results: list[str | Path] = []
    usage_info: dict = {"model": used_model}
    error_msg = ""
    try:

        async def _call():
            nonlocal start_ts
            start_ts = time.perf_counter()
            _user_last_request[user_id] = time.time()
            return await _do_generate(prompt, image_b64, size=size_opt, n=count_opt)

        if cfg.draw_concurrent:
            results, usage_info = await _call()
        else:
            async with _draw_lock:
                results, usage_info = await _call()
    except Exception as e:
        logger.exception(f"[绘图] 生成失败: {e}")
        error_msg = str(e) or f"{type(e).__name__}"
        hit("failed")
    finally:
        _pending -= 1

    if error_msg:
        return await _finish_with(f"❌ 生成失败: {error_msg}")

    hit("success")
    duration = time.perf_counter() - start_ts
    duration_text = _format_duration(duration)

    try:
        for r in results:
            await _send_single(r)
        await UniMessage.text(_build_summary(used_model, duration_text, usage_info, len(results), mode)).send()
    except Exception as e:
        logger.exception(f"[绘图] 发送失败: {e}")
        await _finish_with(f"❌ 发送失败: {results}")
    finally:
        if not cfg.draw_cache_enabled:
            for r in results:
                if isinstance(r, Path):
                    try:
                        r.unlink(missing_ok=True)
                    except OSError:
                        pass

    dump()


@clear_cache_command.handle()
async def handle_clear_cache():
    if not get_config().draw_cache_enabled:
        return await _finish_with("ℹ️ 缓存功能未启用（draw_cache_enabled=False），无需清理")
    deleted, remaining = cleanup_cache()
    return await _finish_with(f"🧹 清理完成：删除 {deleted} 个，剩余 {remaining} 个")
