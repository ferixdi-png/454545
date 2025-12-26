"""
Background cleanup tasks.

Runs periodic maintenance operations:
- Clean old processed_updates (> 7 days)
- Clean old generation_events (> 30 days)
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.database.services import DatabaseService
from app.database.processed_updates import cleanup_old_updates

logger = logging.getLogger(__name__)


async def cleanup_loop(db_service: DatabaseService, interval_hours: int = 24):
    """
    Run cleanup tasks periodically.
    
    Args:
        db_service: Database service instance
        interval_hours: How often to run cleanup (default: 24h)
    """
    logger.info(f"🧹 Cleanup task started (runs every {interval_hours}h)")
    
    while True:
        try:
            # Wait for interval
            await asyncio.sleep(interval_hours * 3600)
            
            logger.info("🧹 Running cleanup tasks...")
            
            # Task 1: Clean old processed_updates (> 7 days)
            deleted_updates = await cleanup_old_updates(db_service, days=7)
            logger.info(f"✅ Cleaned {deleted_updates} old processed_updates (>7 days)")
            
            # Task 2: Clean old generation_events (> 30 days) - keep for analytics
            try:
                async with db_service.pool.acquire() as conn:
                    deleted_events = await conn.execute("""
                        DELETE FROM generation_events
                        WHERE created_at < NOW() - INTERVAL '30 days'
                    """)
                    count = deleted_events.split()[1] if ' ' in deleted_events else '0'
                    logger.info(f"✅ Cleaned {count} old generation_events (>30 days)")
            except Exception as e:
                logger.error(f"Failed to clean generation_events: {e}")
            
            logger.info("✅ Cleanup tasks completed")
            
        except asyncio.CancelledError:
            logger.info("🛑 Cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in cleanup loop: {e}", exc_info=True)
            # Continue running despite errors


async def run_cleanup_once(db_service: DatabaseService):
    """Run cleanup tasks once (for manual trigger)."""
    logger.info("🧹 Running one-time cleanup...")
    
    deleted_updates = await cleanup_old_updates(db_service, days=7)
    logger.info(f"✅ Cleaned {deleted_updates} processed_updates")
    
    async with db_service.pool.acquire() as conn:
        result = await conn.execute("""
            DELETE FROM generation_events
            WHERE created_at < NOW() - INTERVAL '30 days'
        """)
        logger.info(f"✅ Cleaned generation_events: {result}")
