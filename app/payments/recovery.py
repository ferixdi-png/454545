"""Startup cleanup for stuck reservations and locks.

Recovers from crashes by:
- Releasing old payment reservations
- Unlocking stuck job locks
- Cleaning up stale idempotency keys
"""
import logging
import time
from typing import Optional

log = logging.getLogger(__name__)


async def cleanup_stuck_resources(max_age_seconds: int = 600) -> None:
    """Clean up stuck resources from crashes/restarts.
    
    Args:
        max_age_seconds: Max age for locks/reservations (default 10 min)
    """
    log.info("🧹 Starting startup cleanup...")
    
    # 1. Clean up stuck job locks
    try:
        from app.locking.job_lock import cleanup_old_locks
        cleaned_locks = cleanup_old_locks(max_age_seconds)
        if cleaned_locks > 0:
            log.info(f"Cleaned up {cleaned_locks} stuck job locks")
    except (ImportError, AttributeError) as e:
        log.debug(f"Job lock cleanup not available: {e}")
    except Exception as e:
        log.warning(f"Failed to cleanup job locks: {e}")
    
    # 2. Clean up old idempotency keys
    try:
        from app.utils.idempotency import cleanup_old_keys
        cleaned_keys = cleanup_old_keys(max_age_seconds)
        if cleaned_keys > 0:
            log.info(f"Cleaned up {cleaned_keys} old idempotency keys")
    except (ImportError, AttributeError) as e:
        log.debug(f"Idempotency cleanup not available: {e}")
    except Exception as e:
        log.warning(f"Failed to cleanup idempotency keys: {e}")
    
    # 3. Clean up rate limit history
    try:
        from bot.middleware.user_rate_limit import cleanup_old_limits
        cleanup_old_limits(max_age_seconds)
        log.info("Cleaned up old rate limit entries")
    except (ImportError, AttributeError) as e:
        log.debug(f"Rate limit cleanup not available: {e}")
    except Exception as e:
        log.warning(f"Failed to cleanup rate limits: {e}")
    
    # Note: Payment reservations are DB-based and handled by their own TTL
    # (would need DB access to clean up, which is handled separately)
    
    log.info("✅ Startup cleanup complete")


async def schedule_periodic_cleanup(interval_seconds: int = 3600) -> None:
    """Schedule periodic cleanup task (runs every hour by default)."""
    import asyncio
    
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await cleanup_stuck_resources(max_age_seconds=interval_seconds)
        except asyncio.CancelledError:
            log.info("Periodic cleanup task cancelled")
            break
        except Exception as e:
            log.error(f"Periodic cleanup failed: {e}")
