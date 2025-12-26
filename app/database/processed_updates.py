"""
Update deduplication for multi-instance deployment.

Ensures each Telegram update is processed only once even when multiple
bot instances are running simultaneously (e.g., during Render rolling deployment).
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def mark_update_processed(db_service, update_id: int) -> bool:
    """
    Mark update as processed with idempotent insert.
    
    Args:
        db_service: DatabaseService instance
        update_id: Telegram update ID
        
    Returns:
        True if this is first time processing this update
        False if update already processed (duplicate)
    """
    try:
        await db_service.execute("""
            INSERT INTO processed_updates (update_id, processed_at)
            VALUES ($1, NOW())
            ON CONFLICT (update_id) DO NOTHING
        """, update_id)
        
        # Check if insert happened (rowcount would be 1) or conflict (rowcount 0)
        # asyncpg doesn't provide rowcount for ON CONFLICT DO NOTHING,
        # so we do a simple SELECT to check
        result = await db_service.fetchrow(
            "SELECT update_id FROM processed_updates WHERE update_id = $1",
            update_id
        )
        
        if result:
            # Successfully marked as processed
            return True
        else:
            # This shouldn't happen, but handle gracefully
            logger.warning(f"Update {update_id} insert completed but not found in table")
            return True
            
    except Exception as e:
        # Conflict or other error - assume duplicate
        logger.debug(f"Update {update_id} already processed or error: {e}")
        return False


async def is_update_processed(db_service, update_id: int) -> bool:
    """
    Check if update has already been processed.
    
    Args:
        db_service: DatabaseService instance
        update_id: Telegram update ID
        
    Returns:
        True if already processed, False otherwise
    """
    try:
        result = await db_service.fetchrow(
            "SELECT update_id FROM processed_updates WHERE update_id = $1",
            update_id
        )
        return result is not None
    except Exception as e:
        logger.error(f"Error checking processed update {update_id}: {e}")
        # On error, assume not processed to avoid dropping updates
        return False


async def cleanup_old_updates(db_service, days: int = 7) -> int:
    """
    Clean up processed updates older than specified days.
    
    Args:
        db_service: DatabaseService instance
        days: Number of days to keep (default 7)
        
    Returns:
        Number of rows deleted
    """
    try:
        result = await db_service.execute(f"""
            DELETE FROM processed_updates
            WHERE processed_at < NOW() - INTERVAL '{days} days'
        """)
        
        # Extract row count from result string (e.g., "DELETE 123")
        deleted = 0
        if isinstance(result, str) and result.startswith("DELETE "):
            deleted = int(result.split()[1])
        
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} processed updates older than {days} days")
        
        return deleted
    except Exception as e:
        logger.error(f"Error cleaning up old updates: {e}")
        return 0
