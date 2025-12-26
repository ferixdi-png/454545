from __future__ import annotations

import hashlib
import logging
import os
from typing import Optional, Tuple, Dict, Any

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.utils.healthcheck import get_health_state

log = logging.getLogger("app.webhook")


def _default_secret(token: str) -> str:
    # Stable secret derived from bot token (do NOT log the token).
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]


def _detect_base_url() -> Optional[str]:
    # Prefer explicit config; fall back to common Render vars if present.
    for key in ("WEBHOOK_BASE_URL", "RENDER_EXTERNAL_URL", "PUBLIC_URL", "SERVICE_URL"):
        v = os.getenv(key, "").strip()
        if v:
            return v.rstrip("/")
    return None


async def start_webhook_server(
    dp: Dispatcher,
    bot: Bot,
    host: str,
    port: int,
) -> Tuple[web.AppRunner, Dict[str, Any]]:
    base_url = _detect_base_url()
    path = os.getenv("TELEGRAM_WEBHOOK_PATH", "/webhook").strip() or "/webhook"
    if not path.startswith("/"):
        path = "/" + path

    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET_TOKEN", "").strip() or _default_secret(bot.token)

    @web.middleware
    async def secret_guard(request: web.Request, handler):
        # Only guard webhook endpoint.
        if request.path == path:
            provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if provided != secret:
                return web.Response(status=403, text="forbidden")
        return await handler(request)

    app = web.Application(middlewares=[secret_guard])

    # Health endpoints
    async def health(request: web.Request) -> web.Response:
        return web.json_response(get_health_state())

    app.router.add_get("/", health)
    app.router.add_get("/healthz", health)

    # Telegram webhook endpoint (aiogram handler)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=path)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app, access_log=log)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()

    info: Dict[str, Any] = {
        "base_url": base_url,
        "path": path,
        "secret": secret,
        "webhook_url": (base_url.rstrip("/") + path) if base_url else None,
    }

    if base_url:
        try:
            await bot.set_webhook(
                url=info["webhook_url"],
                secret_token=secret,
                drop_pending_updates=False,
            )
            log.info("✅ Webhook configured: %s", info["webhook_url"])
        except Exception:
            log.exception("❌ Failed to set webhook (URL=%s)", info["webhook_url"])
            # We still keep server running so healthcheck works and you can debug.
    else:
        log.warning(
            "WEBHOOK_BASE_URL/RENDER_EXTERNAL_URL is not set. "
            "Webhook server is running, but Telegram won't deliver updates until base URL is configured."
        )

    return runner, info


async def stop_webhook_server(runner: Optional[web.AppRunner]) -> None:
    if not runner:
        return
    try:
        await runner.cleanup()
        log.info("Webhook server stopped")
    except Exception:
        log.exception("Failed to stop webhook server")
