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

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Explicit imports - no try/except, no importlib, no fallbacks
from app.locking.single_instance import SingletonLock
from app.utils.config import get_config, validate_env
from app.utils.healthcheck import start_healthcheck_server, stop_healthcheck_server, set_health_state
from app.utils.startup_validation import validate_startup, StartupValidationError
from app.storage.pg_storage import PGStorage, PostgresStorage
from bot.handlers import flow_router, zero_silence_router, error_handler_router
from bot.handlers.marketing import router as marketing_router, set_database_service as marketing_set_db, set_free_manager as marketing_set_free
from bot.handlers.balance import router as balance_router, set_database_service as balance_set_db
from bot.handlers.history import router as history_router, set_database_service as history_set_db
from bot.handlers.admin import router as admin_router, set_services as admin_set_services
from bot.handlers.gallery import router as gallery_router
from bot.handlers.quick_actions import router as quick_actions_router

# Import aiogram components
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


async def preflight_webhook(bot: Bot) -> None:
    """Delete webhook before starting polling to avoid conflicts."""
    result = await bot.delete_webhook(drop_pending_updates=False)
    logger.info("Webhook deleted: %s", result)


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
    
    # Register rate limit middleware for Telegram API protection
    from bot.middleware import RateLimitMiddleware
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
    
    # Register routers in order (admin first, then marketing, gallery, quick_actions, balance, history, flow)
    dp.include_router(admin_router)
    dp.include_router(marketing_router)
    dp.include_router(gallery_router)  # NEW: Gallery with examples
    dp.include_router(quick_actions_router)  # NEW: Quick actions
    dp.include_router(balance_router)
    dp.include_router(history_router)
    dp.include_router(flow_router)
    dp.include_router(zero_silence_router)
    dp.include_router(error_handler_router)
    
    logger.info("Bot application created successfully")
    return dp, bot


async def main():
    """
    Main entrypoint - explicit initialization sequence.
    No fallbacks, no try/except for imports.
    """
    logger.info("Starting bot application...")
    
    # Validate environment
    config = get_config()
    config.print_summary()
    validate_env()
    
    # Shutdown event for graceful termination
    shutdown_event = asyncio.Event()
    singleton_lock_ref = {"lock": None}  # Shared reference for signal handler
    
    def signal_handler(sig):
        logger.info(f"Received signal {sig}, initiating graceful shutdown...")
        shutdown_event.set()
        
        # CRITICAL: Release singleton lock IMMEDIATELY to allow new instance to acquire it
        # Use ensure_future instead of create_task for better reliability
        if singleton_lock_ref["lock"] and singleton_lock_ref["lock"]._acquired:
            logger.info("⚡ Releasing singleton lock immediately for new instance...")
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
            logger.info("✅ Singleton lock released successfully on shutdown signal")
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
        logger.info("Healthcheck server started on port %s", port)

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
            logger.info(f"Lock acquisition attempt {attempt}/{max_retries}...")
            lock_acquired = await singleton_lock.acquire(timeout=5.0)
            
            if lock_acquired:
                break
            
            if attempt < max_retries:
                logger.warning(f"Lock not acquired on attempt {attempt}/{max_retries}, waiting {retry_delay}s for old instance to release...")
                logger.info(f"Next attempt will be at {attempt + 1}/{max_retries} after {retry_delay}s delay")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"❌ Lock not acquired after {max_retries} attempts ({max_retries * retry_delay}s total wait time)")
                logger.error("Another instance is still running or lock is stuck. Entering passive mode.")
        
        if not lock_acquired:
            set_health_state("passive", "lock_not_acquired")
            # Passive mode: keep healthcheck running, but NO polling
            logger.info("Passive mode: healthcheck available, polling disabled")
            # Wait for shutdown signal
            try:
                await shutdown_event.wait()
                logger.info("Passive mode shutting down gracefully")
            except asyncio.CancelledError:
                logger.info("Passive mode interrupted")
            finally:
                stop_healthcheck_server(healthcheck_server)
            return
        logger.info("Singleton lock acquired successfully - running in active mode")
        set_health_state("active", "lock_acquired")
    else:
        if dry_run:
            logger.info("DRY_RUN enabled - skipping singleton lock")
            lock_acquired = True  # Allow DRY_RUN to proceed
            set_health_state("active", "dry_run_mode")
    
    # Step 2: Initialize storage (if DATABASE_URL provided and not DRY_RUN)
    storage = None
    db_service = None
    free_manager = None
    admin_service = None
    
    if database_url and not dry_run:
        storage = PostgresStorage(dsn=database_url)
        await storage.initialize()
        logger.info("PostgreSQL storage initialized")
        
        # Initialize DatabaseService for new handlers
        from app.database.services import DatabaseService
        from app.free.manager import FreeModelManager
        from app.admin.service import AdminService
        
        db_service = DatabaseService(database_url)
        await db_service.initialize()
        logger.info("DatabaseService initialized")
        
        # Initialize FreeModelManager
        free_manager = FreeModelManager(db_service)
        logger.info("FreeModelManager initialized")
        
        # AUTO-SETUP: Configure FREE models (0 RUB only) as free tier
        try:
            import json
            from pathlib import Path
            
            sot_path = Path("models/KIE_SOURCE_OF_TRUTH.json")
            with open(sot_path, 'r', encoding='utf-8') as f:
                sot = json.load(f)
            
            # Get 5 cheapest models (as per startup validation requirement)
            models = sot.get('models', {})
            enabled_models = [
                (model_id, model) for model_id, model in models.items()
                if model.get('enabled', True)
                and model.get('pricing', {}).get('rub_per_gen') is not None
            ]
            
            # Sort by price and take top 5 cheapest
            enabled_models.sort(key=lambda x: x[1].get('pricing', {}).get('rub_per_gen', 999999))
            free_tier_ids = [model_id for model_id, _ in enabled_models[:5]]
            
            if free_tier_ids:
                for model_id in free_tier_ids:
                    is_free = await free_manager.is_model_free(model_id)
                    
                    if not is_free:
                        price = next(m.get('pricing', {}).get('rub_per_gen', 0) for mid, m in enabled_models if mid == model_id)
                        await free_manager.add_free_model(
                            model_id=model_id,
                            daily_limit=10,
                            hourly_limit=3
                        )
                        logger.info(f"✅ Auto-configured FREE: {model_id} ({price} RUB)")
                
                logger.info(f"Free tier auto-setup: {len(free_tier_ids)} models")
            else:
                logger.warning("No enabled models found in SOURCE_OF_TRUTH")
        except Exception as e:
            logger.warning(f"Free tier auto-setup skipped: {e}")
        
        # Initialize AdminService
        admin_service = AdminService(db_service, free_manager)
        logger.info("AdminService initialized")
        
        # Set services for handlers
        marketing_set_db(db_service)
        marketing_set_free(free_manager)
        balance_set_db(db_service)
        history_set_db(db_service)
        admin_set_services(db_service, admin_service, free_manager)
        logger.info("Services injected into handlers")
    else:
        if dry_run:
            logger.info("DRY_RUN enabled - skipping storage initialization")
    
    # Step 3: Create bot application
    try:
        dp, bot = create_bot_application()
    except ValueError as e:
        logger.error(f"Failed to create bot application: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error creating bot application: {e}", exc_info=True)
        sys.exit(1)
    
    if dry_run:
        logger.info("DRY_RUN enabled - skipping polling startup")
        await bot.session.close()
        if storage:
            await storage.close()
        if singleton_lock:
            await singleton_lock.release()
        stop_healthcheck_server(healthcheck_server)
        return

    # Step 4: Check BOT_MODE guard
    if bot_mode != "polling":
        logger.info(f"BOT_MODE={bot_mode} is not 'polling' - skipping polling startup")
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

    # Step 6: Start polling
    try:
        logger.info("Starting bot polling...")
        # Use create_task to allow cancellation by shutdown signal
        polling_task = asyncio.create_task(dp.start_polling(bot, skip_updates=True))
        
        # Wait for either polling to finish or shutdown signal
        done, pending = await asyncio.wait(
            [polling_task, asyncio.create_task(shutdown_event.wait())],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # If shutdown signaled, cancel polling
        if shutdown_event.is_set():
            logger.info("Shutdown signal received, stopping polling...")
            polling_task.cancel()
            try:
                await polling_task
            except asyncio.CancelledError:
                logger.info("Polling cancelled successfully")
        else:
            # Polling finished naturally, check result
            for task in done:
                if task == polling_task and task.exception():
                    raise task.exception()
                    
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except asyncio.CancelledError:
        logger.info("Bot polling cancelled")
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
        logger.info("Bot shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)