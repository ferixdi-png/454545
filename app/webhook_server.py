from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from typing import Optional, Tuple, Dict, Any

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.utils.healthcheck import get_health_state

log = logging.getLogger("webhook")


def _default_secret(token: str) -> str:
    # Stable secret derived from bot token (do NOT log the token).
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]


def mask_path(path: str) -> str:
    """Mask secret in path for logging (show first 4 and last 4 chars of secret part)."""
    if "/webhook/" in path:
        parts = path.split("/webhook/")
        if len(parts) > 1 and parts[1]:
            secret_part = parts[1].split("/")[0]  # Get secret before any additional path
            if len(secret_part) > 8:
                masked = secret_part[:4] + "****" + secret_part[-4:]
                return f"/webhook/{masked}"
    return path


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
    
    # Generate or use provided secret
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET_TOKEN", "").strip() or _default_secret(bot.token)
    
    # Webhook path: if not explicitly set, use secret path for security
    path_env = os.getenv("TELEGRAM_WEBHOOK_PATH", "").strip()
    if path_env:
        path = path_env if path_env.startswith("/") else "/" + path_env
    else:
        # Default: secret path (not /webhook, but /webhook/<secret>)
        path = f"/webhook/{secret}"
    
    if not path.startswith("/"):
        path = "/" + path

    @web.middleware
    async def request_logger(request: web.Request, handler):
        """Log all incoming requests with timing and safe details."""
        start_time = time.time()
        remote_ip = request.headers.get("X-Forwarded-For", request.remote)
        
        try:
            response = await handler(request)
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Log POST requests to webhook endpoints
            if request.method == "POST" and "/webhook" in request.path:
                content_length = request.headers.get("Content-Length", "?")
                log.info(
                    f"📨 Incoming webhook POST | "
                    f"path={mask_path(request.path)} "
                    f"status={response.status} "
                    f"size={content_length}b "
                    f"latency={latency_ms}ms "
                    f"ip={remote_ip}"
                )
            
            return response
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            log.error(
                f"❌ Request failed | "
                f"method={request.method} "
                f"path={mask_path(request.path)} "
                f"latency={latency_ms}ms "
                f"error={str(e)}"
            )
            raise

    @web.middleware
    async def secret_guard(request: web.Request, handler):
        """Dual security: secret path (primary) + header (fallback).
        
        Security model:
        1. If request path contains secret -> ALLOW (path-based auth)
        2. Else if request to /webhook and has valid header -> ALLOW (header-based auth)
        3. Else -> DENY (unauthorized)
        """
        # Only guard webhook endpoints
        if "/webhook" in request.path:
            # Check 1: Secret in path (primary security)
            if secret in request.path:
                # Valid secret path - allow
                return await handler(request)
            
            # Check 2: Legacy /webhook with valid header (fallback)
            provided_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if provided_header and provided_header == secret:
                # Valid header - allow
                return await handler(request)
            
            # Neither path nor header valid - deny
            client_ip = request.headers.get("X-Forwarded-For", request.remote)
            has_header = bool(request.headers.get("X-Telegram-Bot-Api-Secret-Token"))
            log.warning(
                f"🚫 Unauthorized webhook access | "
                f"ip={client_ip} "
                f"path={mask_path(request.path)} "
                f"has_header={has_header} "
                f"method={request.method}"
            )
            return web.Response(status=401, text="Unauthorized")
        
        return await handler(request)

    app = web.Application(middlewares=[request_logger, secret_guard])

    # Health endpoints
    async def healthz(request: web.Request) -> web.Response:
        """Liveness probe - always returns 200 OK (no DB check)."""
        return web.json_response({"status": "ok"}, status=200)

    async def readyz(request: web.Request) -> web.Response:
        """Readiness probe - returns 200 only if bot is fully ready."""
        state = get_health_state()
        mode = state.get("mode")
        ready = state.get("ready", False)
        
        # Ready only if: (a) bot is active, (b) storage/DB initialized, (c) webhook mode correct
        if mode == "active" and ready:
            return web.json_response(state, status=200)
        else:
            return web.json_response(state, status=503)

    async def health(request: web.Request) -> web.Response:
        """Legacy health endpoint - returns current state."""
        return web.json_response(get_health_state())
    
    async def metrics_endpoint(request: web.Request) -> web.Response:
        """Metrics endpoint for monitoring - returns system metrics."""
        try:
            from app.utils.metrics import get_system_metrics
            from app.database.service import db_service
            
            metrics = await get_system_metrics(db_service)
            return web.json_response(metrics, status=200)
        except Exception as e:
            log.error(f"Failed to get metrics: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    app.router.add_get("/", health)
    app.router.add_get("/healthz", healthz)
    app.router.add_get("/readyz", readyz)
    app.router.add_get("/metrics", metrics_endpoint)

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
        "secret": "***" if secret else None,  # Don't log secret
        "webhook_url": (base_url.rstrip("/") + path) if base_url else None,
    }

    # Webhook self-check logging
    log.info("🔍 Webhook Configuration:")
    log.info(f"  Host: {host}:{port}")
    log.info(f"  Path: {mask_path(path)}")
    log.info(f"  Base URL: {base_url or 'NOT SET'}")
    log.info(f"  Full webhook URL: {(base_url.rstrip('/') + mask_path(path)) if base_url else 'MISSING'}")
    log.info(f"  Secret token: {'configured ✅' if secret else 'NOT SET ⚠️'}")
    log.info(f"  Security: path-based + header fallback")

    if not base_url:
        log.warning("⚠️⚠️⚠️ WEBHOOK_BASE_URL NOT SET ⚠️⚠️⚠️")
        log.warning("⚠️ Telegram will NOT deliver updates to this bot!")
        log.warning("⚠️ Set WEBHOOK_BASE_URL env var (e.g., https://your-app.onrender.com)")

    if base_url:
        # Retry webhook registration with exponential backoff
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(1, max_retries + 1):
            try:
                await bot.set_webhook(
                    url=info["webhook_url"],
                    secret_token=secret,
                    drop_pending_updates=False,
                )
                log.info("✅ Webhook registered successfully: %s", info["webhook_url"])
                break
            except Exception as e:
                log.error(f"❌ Webhook registration failed (attempt {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    log.info(f"⏳ Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    log.critical("❌ Failed to register webhook after all retries")
                    # Keep server running for healthcheck and manual debugging
    else:
        log.warning(
            "⚠️ WEBHOOK_BASE_URL not set. Server running but Telegram won't deliver updates."
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
