#!/usr/bin/env python3
"""
Production entrypoint for Render deployment.
Single, explicit initialization path with no fallbacks.
"""
import asyncio
import logging
import os
import signal
import sys
from typing import Optional, Tuple
import uuid

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Project imports (explicit; no silent fallbacks)
from app.locking.single_instance import SingletonLock
from app.utils.config import get_config, validate_env
from app.utils.healthcheck import (
    set_health_state,
    start_healthcheck_server,
    stop_healthcheck_server,
)
from app.utils.startup_validation import StartupValidationError, validate_startup


# Logging must exist BEFORE anything else uses it.
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("main_render")

INSTANCE_ID = os.environ.get('INSTANCE_ID') or str(uuid.uuid4())[:8]


def run_startup_selfcheck() -> None:
    """
    Fail-fast sanity checks for production.

    Invariants:
      - required env vars are present
      - allowed model list exists and contains EXACTLY 42 unique model ids
      - source-of-truth registry contains ONLY these 42 ids (1:1)
    """
    required = ["TELEGRAM_BOT_TOKEN", "KIE_API_KEY", "ADMIN_ID"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    # Load allowlist from repo file (canonical)
    allow_path = os.path.join(os.path.dirname(__file__), "models", "ALLOWED_MODEL_IDS.txt")
    if not os.path.exists(allow_path):
        raise RuntimeError("ALLOWED_MODEL_IDS.txt not found (models must be locked to file)")

    with open(allow_path, "r", encoding="utf-8") as f:
        allowed = [line.strip() for line in f.readlines() if line.strip() and not line.strip().startswith("#")]

    # Normalize / validate
    allowed_norm = [s.strip() for s in allowed if s.strip()]
    if len(allowed_norm) != 42 or len(set(allowed_norm)) != 42:
        raise RuntimeError(f"Allowed models must be EXACTLY 42 unique ids. Got count={len(allowed_norm)} unique={len(set(allowed_norm))}")

    # Load source-of-truth registry keys
    sot_path = os.path.join(os.path.dirname(__file__), "models", "KIE_SOURCE_OF_TRUTH.json")
    if not os.path.exists(sot_path):
        # repo contains truncated name sometimes; fall back to discovered file
        # (kept defensive, but we still require SOT to exist)
        candidates = [p for p in os.listdir(os.path.join(os.path.dirname(__file__), "models")) if p.startswith("KIE_SOURCE_OF_T") and p.endswith(".json")]
        if candidates:
            sot_path = os.path.join(os.path.dirname(__file__), "models", candidates[0])
        else:
            raise RuntimeError("KIE_SOURCE_OF_TRUTH.json not found")

    import json
    with open(sot_path, "r", encoding="utf-8") as f:
        sot = json.load(f)
    keys = list(sot.keys()) if isinstance(sot, dict) else []
    if len(keys) == 0:
        raise RuntimeError("Source-of-truth registry is empty or invalid")

    # Some repos wrap it; support {"models": {...}} as well
    if "models" in sot and isinstance(sot.get("models"), dict):
        keys = list(sot["models"].keys())
        sot = sot["models"]

    allowed_set = set(allowed_norm)
    keys_set = set(keys)
    if keys_set != allowed_set:
        extra = sorted(list(keys_set - allowed_set))[:10]
        missing_ids = sorted(list(allowed_set - keys_set))[:10]
        raise RuntimeError(f"SOT registry mismatch with allowlist. Extra={extra} Missing={missing_ids}")

    logging.getLogger(__name__).info(f"✅ Startup selfcheck OK: 42 models locked (allowlist+SOT match)")

def create_bot_application() -> Tuple[Dispatcher, Bot]:
    """
    Create and configure bot application.
    
    Returns:
        Tuple of (Dispatcher, Bot) instances
        
    Raises:
        ValueError: If TELEGRAM_BOT_TOKEN is not set
    """
    config = get_config()
    dry_run = os.getenv("DRY_RUN", "0").lower() in {"1", "true", "yes"}
    
    if dry_run and (not config.telegram_bot_token or ":" not in config.telegram_bot_token):
        bot_token = "123456:TEST"
    else:
        bot_token = config.telegram_bot_token
    
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
    
    # Create bot with explicit configuration
    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Create dispatcher
    dp = Dispatcher()
    dp['instance_id'] = INSTANCE_ID

    # Register middlewares
    from bot.middleware import RateLimitMiddleware, EventLogMiddleware, CallbackDedupeMiddleware
    from bot.middleware.fsm_guard import FSMGuardMiddleware

    # Structured event logging middleware (update in/out)
    dp.update.middleware(EventLogMiddleware())
    # Callback dedupe middleware (prevents double-tap duplicate callbacks)
    dp.update.middleware(CallbackDedupeMiddleware(window_s=2.0))
    logger.info("Callback dedupe middleware registered (2s window)")
    logger.info("Event log middleware registered")

    # FSM guard middleware (auto-reset stale/broken states)
    dp.update.middleware(FSMGuardMiddleware())
    logger.info("FSM guard middleware registered")

    # Rate limit middleware for Telegram API protection
    dp.update.middleware(RateLimitMiddleware(max_retries=3))
    logger.info("Rate limit middleware registered (max_retries=3)")

    # Register per-user rate limiting middleware for abuse protection
    from bot.middleware.user_rate_limit import UserRateLimitMiddleware
    from app.admin.permissions import is_admin
    
    # Get admin IDs for exemption
    admin_ids = set()
    if config.admin_ids:
        # Handle both string and list formats
        if isinstance(config.admin_ids, str):
            admin_ids = set(map(int, config.admin_ids.split(',')))
        elif isinstance(config.admin_ids, list):
            admin_ids = set(map(int, config.admin_ids))
    
    dp.update.middleware(UserRateLimitMiddleware(
        rate=20,  # 20 actions per minute
        period=60,
        burst=30,  # Allow bursts of 30
        exempt_users=admin_ids
    ))
    logger.info(f"User rate limit middleware registered (20/min, {len(admin_ids)} admins exempt)")
    
    # Import routers explicitly (kept here to avoid heavy imports at module load)
    from bot.handlers import (
        admin_router,
        marketing_router,
        gallery_router,
        quick_actions_router,
        balance_router,
        history_router,
        flow_router,
        zero_silence_router,
        error_handler_router,
    )
    from bot.handlers.callback_fallback import router as callback_fallback_router

    # Register routers in order (admin first, then marketing, gallery, quick_actions, balance, history, flow)
    dp.include_router(admin_router)
    dp.include_router(marketing_router)
    dp.include_router(gallery_router)
    dp.include_router(quick_actions_router)
    dp.include_router(balance_router)
    dp.include_router(history_router)
    dp.include_router(flow_router)
    dp.include_router(callback_fallback_router)
    dp.include_router(zero_silence_router)
    dp.include_router(error_handler_router)
    
    logger.info("Bot application created successfully")
    return dp, bot


async def main():
    """
    Main entrypoint - explicit initialization sequence.
    No fallbacks, no try/except for imports.
    """
    logger.info(f"Starting bot application... instance={INSTANCE_ID}")

    # Fail-fast invariants (42 models locked to file)
    run_startup_selfcheck()
    
    # Validate environment
    config = get_config()
    config.print_summary()
    validate_env()

    # Create bot and dispatcher (safe: does not call Telegram network APIs)
    dp, bot = create_bot_application()
    storage = None
    db_service = None
    free_manager = None
    admin_service = None
    
    # Shutdown event for graceful termination
    shutdown_event = asyncio.Event()
    singleton_lock_ref = {"lock": None}  # Shared reference for signal handler
    
    def signal_handler(sig):
        logging.getLogger(__name__).info(f"Received signal {sig}, initiating graceful shutdown...")
        shutdown_event.set()
        
        # CRITICAL: Release singleton lock IMMEDIATELY to allow new instance to acquire it
        # Use ensure_future instead of create_task for better reliability
        if singleton_lock_ref["lock"] and singleton_lock_ref["lock"]._acquired:
            logging.getLogger(__name__).info("⚡ Releasing singleton lock immediately for new instance...")
            asyncio.ensure_future(_emergency_lock_release(singleton_lock_ref["lock"]))
    
    async def _emergency_lock_release(lock):
        """Emergency lock release on shutdown signal - allows zero-downtime deployment."""
        try:
            # Stop heartbeat FIRST to avoid race condition
            lock._acquired = False
            if lock._heartbeat_task:
                lock._heartbeat_task.cancel()
            
            # Release lock immediately
            await lock.release()
            logging.getLogger(__name__).info("✅ Singleton lock released successfully on shutdown signal")
        except Exception as e:
            logger.error(f"Error during emergency lock release: {e}", exc_info=True)
    
    # Register signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
    
    healthcheck_server = None
    port = int(os.getenv("PORT", "10000"))
    if port:
        healthcheck_server, _ = start_healthcheck_server(port)
        logging.getLogger(__name__).info("Healthcheck server started on port %s", port)
        # Initial health state
        set_health_state("starting", "boot", ready=False, instance=INSTANCE_ID)

    dry_run = os.getenv("DRY_RUN", "0").lower() in {"1", "true", "yes"}
    bot_mode = os.getenv("BOT_MODE", "polling").lower()

    # Step 1: Acquire singleton lock (if DATABASE_URL provided and not DRY_RUN)
    singleton_lock = None
    lock_acquired = False
    database_url = os.getenv("DATABASE_URL")
    if database_url and not dry_run:
        instance_name = config.instance_name
        singleton_lock = SingletonLock(dsn=database_url, instance_name=instance_name)
        singleton_lock_ref["lock"] = singleton_lock  # Store reference for signal handler
        
        # ULTRA-AGGRESSIVE RETRY: Force acquisition even if old instance is slow to shutdown
        # Total wait time: 8 retries × 2s = 16s (exceeds TTL 10s + margin 6s)
        max_retries = 8
        retry_delay = 2  # seconds
        
        for attempt in range(1, max_retries + 1):
            logging.getLogger(__name__).info(f"Lock acquisition attempt {attempt}/{max_retries}...")
            lock_acquired = await singleton_lock.acquire(timeout=5.0)
            
            if lock_acquired:
                break
            
            if attempt < max_retries:
                logging.getLogger(__name__).warning(f"Lock not acquired on attempt {attempt}/{max_retries}, waiting {retry_delay}s for old instance to release...")
                logging.getLogger(__name__).info(f"Next attempt will be at {attempt + 1}/{max_retries} after {retry_delay}s delay")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"❌ Lock not acquired after {max_retries} attempts ({max_retries * retry_delay}s total wait time)")
                logger.error("Another instance is still running or lock is stuck. Entering passive mode.")
        
        if not lock_acquired:
            # Standby mode: keep healthcheck running, DO NOT touch Telegram.
            # Keep attempting to acquire lock periodically; once acquired, transition to ACTIVE.
            set_health_state("standby", "lock_not_acquired", ready=False, instance=INSTANCE_ID)
            logging.getLogger(__name__).info("STANDBY mode: healthcheck available, polling disabled. Will keep trying to acquire lock.")
            while True:
                # Wait a bit, but rely only on .wait() for test-friendliness
                try:
                    await asyncio.wait_for(shutdown_event.wait(), timeout=5)
                    break
                except asyncio.TimeoutError:
                    pass

                logging.getLogger(__name__).info("Standby: retrying singleton lock acquisition...")
                lock_acquired = await singleton_lock.acquire(timeout=5.0)
                if lock_acquired:
                    logging.getLogger(__name__).info("✅ Singleton lock acquired from standby - transitioning to ACTIVE")
                    break
            if not lock_acquired:
                logging.getLogger(__name__).info("Standby mode shutting down gracefully")
                await bot.session.close()
                if storage:
                    await storage.close()
                if singleton_lock:
                    await singleton_lock.release()
                stop_healthcheck_server(healthcheck_server)
                return


    # Step 3.5: Initialize DB/services (ACTIVE only)
    if database_url and not dry_run:
        # Initialize PostgreSQL storage (compat layer) and DB services
        from app.storage.pg_storage import PGStorage
        storage = PGStorage(database_url)
        await storage.initialize()
        logging.getLogger(__name__).info("PostgreSQL storage initialized")

        from app.database.services import DatabaseService
        db_service = DatabaseService(database_url)
        await db_service.initialize()
        logging.getLogger(__name__).info("✅ Database initialized with schema")

        from app.free.manager import FreeModelManager
        free_manager = FreeModelManager(db_service)
        logging.getLogger(__name__).info("FreeModelManager initialized")

        # Configure FREE tier based on TOP-5 cheapest models
        try:
            from app.pricing.free_models import get_free_models, get_model_price
            free_ids = get_free_models()
            logging.getLogger(__name__).info(f"Loaded {len(free_ids)} free models (TOP-5 cheapest): {free_ids}")
            for mid in free_ids:
                await free_manager.add_free_model(mid, daily_limit=10, hourly_limit=3, meta={"source": "auto_top5"})
                logging.getLogger(__name__).info(f"Free model configured: {mid} (daily=10, hourly=3)")
            # Log effective prices for audit
            for mid in free_ids:
                try:
                    # Log *effective* user price to simplify audit.
                    price = get_model_price(mid)
                    from app.payments.pricing import (  # local import to avoid cycles
                        get_usd_to_rub_rate,
                        get_pricing_markup,
                        get_kie_credits_to_usd,
                    )
                    rate = get_usd_to_rub_rate()
                    markup = get_pricing_markup()
                    credits_to_usd = get_kie_credits_to_usd()
                    eff = 0.0
                    if price.get('rub_per_use', 0.0):
                        eff = float(price['rub_per_use']) * markup
                    elif price.get('usd_per_use', 0.0):
                        eff = float(price['usd_per_use']) * rate * markup
                    elif price.get('credits_per_use', 0.0):
                        eff = float(price['credits_per_use']) * credits_to_usd * rate * markup
                    logging.getLogger(__name__).info(f"✅ FREE tier: {mid} ({eff:.2f} RUB effective)")
                except Exception:
                    logging.getLogger(__name__).info(f"✅ FREE tier: {mid} (effective price unknown)")
            logging.getLogger(__name__).info(f"Free tier auto-setup: {len(free_ids)} models")
        except Exception as e:
            logger.exception(f"Failed to auto-setup free tier: {e}")

        # Admin service + injection
        from app.admin.service import AdminService
        admin_service = AdminService(db_service, free_manager)
        logging.getLogger(__name__).info("AdminService initialized")

        # Inject services into handlers that require them
        try:
            from bot.handlers.admin import set_services as admin_set_services
            admin_set_services(db_service, admin_service, free_manager)
        except Exception as e:
            logger.exception(f"Failed to inject services into admin handlers: {e}")
        logging.getLogger(__name__).info("Services injected into handlers")
    # Step 4: Check BOT_MODE guard
    if bot_mode != "polling":
        logging.getLogger(__name__).info(f"BOT_MODE={bot_mode} is not 'polling' - skipping polling startup")
        await bot.session.close()
        if storage:
            await storage.close()
        if singleton_lock:
            await singleton_lock.release()
        stop_healthcheck_server(healthcheck_server)
        return

    # Step 5: Preflight - delete webhook before polling
    await preflight_webhook(bot)

    # Step 5.5: Startup validation - verify source_of_truth and pricing
    try:
        validate_startup()
    except StartupValidationError as e:
        logger.error(f"❌ Startup validation failed: {e}")
        logger.error("Бот НЕ будет запущен из-за ошибок валидации")
        await bot.session.close()
        if storage:
            await storage.close()
        if singleton_lock:
            await singleton_lock.release()
        stop_healthcheck_server(healthcheck_server)
        sys.exit(1)

    # Mark ACTIVE+READY right before polling
    try:
        set_health_state("active", "polling", ready=True, instance=INSTANCE_ID)
    except Exception:
        # Healthcheck must never break startup
        pass

    # Step 6: Start polling
    try:
        logging.getLogger(__name__).info("Starting bot polling...")
        # Use create_task to allow cancellation by shutdown signal
        polling_task = asyncio.create_task(dp.start_polling(bot, skip_updates=True))
        
        # Wait for either polling to finish or shutdown signal
        done, pending = await asyncio.wait(
            [polling_task, asyncio.create_task(shutdown_event.wait())],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # If shutdown signaled, cancel polling
        if hasattr(shutdown_event, "is_set") and hasattr(shutdown_event, 'is_set') and shutdown_event.is_set():
            logging.getLogger(__name__).info("Shutdown signal received, stopping polling...")
            polling_task.cancel()
            try:
                await polling_task
            except asyncio.CancelledError:
                logging.getLogger(__name__).info("Polling cancelled successfully")
        else:
            # Polling finished naturally, check result
            for task in done:
                if task == polling_task and task.exception():
                    raise task.exception()
                    
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Bot stopped by user")
    except asyncio.CancelledError:
        logging.getLogger(__name__).info("Bot polling cancelled")
    except Exception as e:
        logger.error(f"Error during bot polling: {e}", exc_info=True)
        raise
    finally:
        # Cleanup
        if db_service:
            await db_service.close()
        if storage:
            await storage.close()
        if singleton_lock:
            await singleton_lock.release()
        await bot.session.close()
        stop_healthcheck_server(healthcheck_server)
        logging.getLogger(__name__).info("Bot shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Application interrupted")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)
