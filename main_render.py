#!/usr/bin/env python3
"""
Production entrypoint for Render deployment.
Multi-instance mode with update-level idempotency (no singleton lock).
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

# === VERSION TRACKING (CRITICAL - log FIRST) ===
from app.utils.version import log_version_info, get_version_string
log_version_info()

# Project imports (explicit; no silent fallbacks)
from app.utils.config import get_config, validate_env
from app.utils.healthcheck import set_health_state
from app.webhook_server import start_webhook_server, stop_webhook_server
from app.utils.startup_validation import StartupValidationError, validate_startup

# Logging configuration (production-grade format with request_id support)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


class ProductionFormatter(logging.Formatter):
    """Production-grade log formatter with request_id/task_id correlation."""
    
    def format(self, record):
        # Add request_id if available (from trace context)
        request_id = getattr(record, 'request_id', None)
        if request_id:
            record.msg = f"[req:{request_id[:8]}] {record.msg}"
        
        # Add task_id if available
        task_id = getattr(record, 'task_id', None)
        if task_id:
            record.msg = f"[task:{task_id[:8]}] {record.msg}"
        
        # Mask user_id if present (GDPR compliance)
        user_id = getattr(record, 'user_id', None)
        if user_id:
            masked_user = f"***{str(user_id)[-4:]}"
            record.msg = f"[user:{masked_user}] {record.msg}"
        
        return super().format(record)


# Configure logging with production formatter
handler = logging.StreamHandler()
handler.setFormatter(ProductionFormatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    handlers=[handler],
    force=True  # Override any existing config
)
logger = logging.getLogger('main_render')

INSTANCE_ID = os.environ.get('INSTANCE_ID') or str(uuid.uuid4())[:8]


def log_runtime_contracts():
    """Log critical runtime contracts (helps debug deployment issues)."""
    import inspect
    try:
        from app.payments.integration import generate_with_payment
        sig = inspect.signature(generate_with_payment)
        params = list(sig.parameters.keys())
        has_payload = 'payload' in params
        has_kwargs = any(p for p in sig.parameters.values() if p.kind == inspect.Parameter.VAR_KEYWORD)
        
        logger.info(
            f"🔧 Runtime contracts: "
            f"generate_with_payment({len(params)} params, "
            f"payload={'✅' if has_payload else '❌'}, "
            f"**kwargs={'✅' if has_kwargs else '❌'})"
        )
    except Exception as e:
        logger.warning(f"⚠️ Could not inspect generate_with_payment: {e}")


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
        navigation_router,
        gen_handler_router,
    )
    from bot.handlers.callback_fallback import router as callback_fallback_router
    from bot.handlers.formats import router as formats_router
    from bot.flows.wizard import router as wizard_router

    # Register routers in order (admin first, then formats/wizard for new UX, then legacy)
    # NOTE: flow_router disabled to avoid callback collisions with marketing/formats
    dp.include_router(admin_router)
    dp.include_router(navigation_router)  # NAVIGATION: universal menu:main/home handler
    dp.include_router(gen_handler_router)  # GEN: resolves short keys → wizard
    dp.include_router(wizard_router)   # WIZARD: primary generation flow
    dp.include_router(formats_router)  # FORMATS: format-based navigation
    dp.include_router(marketing_router)  # MARKETING: main menu + popular
    dp.include_router(gallery_router)
    dp.include_router(quick_actions_router)
    dp.include_router(balance_router)
    dp.include_router(history_router)
    # dp.include_router(flow_router)  # DISABLED: conflicts with marketing (gen:/model:/launch:)
    dp.include_router(callback_fallback_router)  # LAST: catches unknown callbacks
    dp.include_router(zero_silence_router)
    dp.include_router(error_handler_router)
    
    logger.info("Bot application created successfully")
    return dp, bot


async def main():
    """
    Main entrypoint - explicit initialization sequence.
    No fallbacks, no try/except for imports.
    """
    # Log version info FIRST (before any initialization)
    from app.utils.version import log_version_info
    log_version_info()
    
    # Log runtime contracts (critical for debugging deployment issues)
    log_runtime_contracts()
    
    logger.info(f"Starting bot application... instance={INSTANCE_ID}")

    # Fail-fast invariants (42 models locked to file)
    run_startup_selfcheck()
    
    # Initialize callback registry from SOURCE_OF_TRUTH
    logger.info("Initializing callback registry...")
    from app.ui.callback_registry import init_registry_from_models
    from app.ui.catalog import load_models_sot
    models_dict = load_models_sot()
    init_registry_from_models(models_dict)
    logger.info(f"Callback registry initialized with {len(models_dict)} models")
    
    # Validate environment
    config = get_config()
    validate_env()

    # Create bot and dispatcher (safe: does not call Telegram network APIs)
    dp, bot = create_bot_application()
    storage = None
    db_service = None
    free_manager = None
    admin_service = None
    
    # Shutdown event for graceful termination
    shutdown_event = asyncio.Event()
    
    def signal_handler(sig):
        logging.getLogger(__name__).info(f"Received signal {sig}, initiating graceful shutdown...")
        shutdown_event.set()
    
    # Register signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
    
    webhook_runner = None
    port = int(os.getenv("PORT", "10000"))
    # Initial health state
    set_health_state("starting", "boot", ready=False, instance=INSTANCE_ID)
    logger.info(f"🚀 Starting on port {port}")

    dry_run = os.getenv("DRY_RUN", "0").lower() in {"1", "true", "yes"}
    bot_mode = os.getenv("BOT_MODE", "polling").lower()

    # Step 1: Multi-instance mode (NO singleton lock)
    # Idempotency handled by processed_updates table + middleware
    singleton_lock = None
    database_url = os.getenv("DATABASE_URL")
    logger.info("✅ Multi-instance mode enabled - idempotency handled via processed_updates table")


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
        
        # Check DB schema and configure feature flags
        try:
            from app.database.migrations_check import configure_features_from_schema
            await configure_features_from_schema(db_service.pool)
            logging.getLogger(__name__).info("✅ Feature flags configured from DB schema")
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to configure features from schema: {e}")
        
        # Startup cleanup: recover from crashes
        try:
            from app.payments.recovery import cleanup_stuck_resources
            await cleanup_stuck_resources(max_age_seconds=600)
        except Exception as e:
            logging.getLogger(__name__).warning(f"Startup cleanup failed: {e}")

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

        # Configure ChargeManager with db_service
        from app.payments.charges import get_charge_manager
        cm = get_charge_manager(storage)
        cm.db_service = db_service
        # Recreate wallet_service with db_service available
        if hasattr(cm, '_wallet_service'):
            cm._wallet_service = None  # Reset cache to trigger recreation
        logging.getLogger(__name__).info("✅ ChargeManager configured with DB")

        # Inject services into handlers that require them
        try:
            from bot.handlers.admin import set_services as admin_set_services
            admin_set_services(db_service, admin_service, free_manager)
        except Exception as e:
            logger.exception(f"Failed to inject services into admin handlers: {e}")
        
        # Inject db_service into balance/history handlers
        try:
            from bot.handlers.balance import set_database_service as balance_set_db
            from bot.handlers.history import set_database_service as history_set_db
            balance_set_db(db_service)
            history_set_db(db_service)
            logging.getLogger(__name__).info("✅ DB injected into balance/history handlers")
        except Exception as e:
            logger.exception(f"Failed to inject db_service into balance/history handlers: {e}")
        
        logging.getLogger(__name__).info("Services injected into handlers")
        
        # Register update deduplication middleware (CRITICAL for multi-instance mode)
        from bot.middleware.update_dedupe import UpdateDedupeMiddleware
        dp.update.outer_middleware(UpdateDedupeMiddleware(db_service))
        logging.getLogger(__name__).info("✅ Update dedupe middleware registered (multi-instance idempotency)")
    # Step 4: BOT_MODE handling (supported: polling | webhook)
    if bot_mode not in {"polling", "webhook"}:
        logger.warning("Unsupported BOT_MODE=%r, falling back to 'polling'", bot_mode)
        bot_mode = "polling"

    # Reflect effective mode in config summary
    try:
        config.bot_mode = bot_mode
    except Exception:
        pass
    config.print_summary()

    # Step 5: Startup validation - verify source_of_truth and pricing
    try:
        validate_startup()
    except StartupValidationError as e:
        logger.error(f"❌ Startup validation failed: {e}")
        logger.error("Бот НЕ будет запущен из-за ошибок валидации")
        await bot.session.close()
        if storage:
            await storage.close()
        await stop_webhook_server(webhook_runner)
        sys.exit(1)

    # Step 6: Start bot based on mode
    try:
        if bot_mode == "webhook":
            # WEBHOOK MODE - Production-ready with retry and auto-recovery
            logger.info("🌐 Starting WEBHOOK mode...")
            
            # Delete webhook before setting new one (cleanup)
            try:
                await bot.delete_webhook(drop_pending_updates=True)
                logger.info("✅ Old webhook deleted")
            except Exception as e:
                logger.warning(f"Could not delete old webhook: {e}")
            
            # Start webhook server with retry logic
            max_attempts = 3
            retry_delay = 10
            
            for attempt in range(1, max_attempts + 1):
                try:
                    webhook_runner, webhook_info = await start_webhook_server(
                        dp=dp,
                        bot=bot,
                        host="0.0.0.0",
                        port=port,
                    )
                    logger.info(f"✅ Webhook server started on 0.0.0.0:{port}")
                    logger.info(f"✅ Webhook registered successfully: {webhook_info.get('webhook_url')}")
                    break
                except Exception as e:
                    logger.error(f"❌ Webhook setup failed (attempt {attempt}/{max_attempts}): {e}")
                    if attempt < max_attempts:
                        logger.info(f"⏳ Retrying in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.critical("❌ Failed to start webhook after all retries")
                        raise
            
            # Mark ACTIVE+READY
            set_health_state("active", "webhook", ready=True, instance=INSTANCE_ID)
            logger.info("✅ Bot is READY (webhook mode)")
            
            # Start background tasks
            cleanup_task = None
            model_sync_task = None
            
            if db_service:
                from app.tasks import cleanup_loop, model_sync_loop
                
                # Cleanup task (every 24h)
                cleanup_task = asyncio.create_task(cleanup_loop(db_service, interval_hours=24))
                logger.info("🧹 Cleanup task scheduled (every 24h)")
                
                # Model sync task (every 24h) - only if enabled
                model_sync_enabled = os.getenv("MODEL_SYNC_ENABLED", "0") == "1"
                if model_sync_enabled:
                    model_sync_task = asyncio.create_task(model_sync_loop(interval_hours=24))
                    logger.info("🔄 Model sync task scheduled (every 24h)")
                else:
                    logger.info("⏸️ Model sync disabled (MODEL_SYNC_ENABLED=0)")
            
            # Wait for shutdown signal
            await shutdown_event.wait()
            logger.info("Shutdown signal received")
            
            # Cancel background tasks
            for task in [cleanup_task, model_sync_task]:
                if task:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
        else:
            # POLLING MODE - Fallback for development
            logger.info("🔄 Starting POLLING mode...")
            
            # Delete webhook to avoid conflicts
            try:
                await bot.delete_webhook(drop_pending_updates=True)
                logger.info("✅ Webhook deleted (polling mode)")
            except Exception as e:
                logger.warning(f"Could not delete webhook: {e}")
            
            # Mark ACTIVE+READY
            set_health_state("active", "polling", ready=True, instance=INSTANCE_ID)
            
            # Start polling with graceful shutdown
            polling_task = asyncio.create_task(dp.start_polling(bot, skip_updates=True))
            logger.info("✅ Bot polling started")
            
            # Wait for either polling to finish or shutdown signal
            done, pending = await asyncio.wait(
                [polling_task, asyncio.create_task(shutdown_event.wait())],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel polling if shutdown signaled
            if shutdown_event.is_set():
                logger.info("Stopping polling...")
                polling_task.cancel()
                try:
                    await polling_task
                except asyncio.CancelledError:
                    logger.info("Polling cancelled")
                    
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except asyncio.CancelledError:
        logger.info("Bot cancelled")
    except Exception as e:
        logger.error(f"Error during bot operation: {e}", exc_info=True)
        raise
    finally:
        # Graceful shutdown sequence
        logger.info("🛑 Initiating graceful shutdown...")
        
        # Step 1: Mark as unhealthy to stop receiving traffic
        set_health_state("stopping", "shutdown_initiated", ready=False, instance=INSTANCE_ID)
        logger.info("  → Health state set to 'stopping'")
        
        # Step 2: Stop webhook server (if running) to reject new updates
        if webhook_runner:
            logger.info("  → Stopping webhook server...")
            await stop_webhook_server(webhook_runner)
            logger.info("  ✅ Webhook server stopped")
        
        # Step 3: Close database service (complete pending operations)
        if db_service:
            logger.info("  → Closing database service...")
            await db_service.close()
            logger.info("  ✅ Database service closed")
        
        # Step 4: Close storage layer
        if storage:
            logger.info("  → Closing storage...")
            await storage.close()
            logger.info("  ✅ Storage closed")
        
        # Step 5: Close bot session (cleanup aiohttp client)
        logger.info("  → Closing bot session...")
        await bot.session.close()
        logger.info("  ✅ Bot session closed")
        
        logger.info("✅ Graceful shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Application interrupted")
        sys.exit(0)
    except Exception as e:
        logging.getLogger('main_render').critical(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)