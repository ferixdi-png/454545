"""
Telegram update deduplication middleware.

Prevents processing the same update multiple times when running
multiple instances behind a load balancer or during rolling deployments.
"""
import logging
from typing import Any, Awaitable, Callable, Dict

from telegram import Update
from telegram.ext import BaseHandler, ContextTypes

from app.database.service import DatabaseService
from app.database.processed_updates import mark_update_processed

logger = logging.getLogger(__name__)


class UpdateDedupeMiddleware:
    """Middleware to prevent duplicate update processing across instances."""
    
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
    
    async def __call__(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        next_handler: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]
    ) -> Any:
        """
        Check if update already processed, skip if duplicate.
        
        Args:
            update: Telegram update object
            context: Bot context
            next_handler: Next handler in chain
            
        Returns:
            Handler result or None if duplicate
        """
        if not update or not hasattr(update, 'update_id'):
            # No update_id, cannot dedupe - pass through
            return await next_handler(update, context)
        
        update_id = update.update_id
        
        # Try to mark as processed (returns False if already exists)
        is_first_time = await mark_update_processed(self.db_service, update_id)
        
        if not is_first_time:
            # Already processed by another instance - drop silently
            logger.info(
                f"⏭️ Update {update_id} already processed, skipping (multi-instance dedupe)",
                extra={"update_id": update_id, "dedupe": True}
            )
            return None
        
        # First time seeing this update - process normally
        logger.debug(
            f"✅ Update {update_id} marked as new, processing",
            extra={"update_id": update_id}
        )
        
        return await next_handler(update, context)
