"""User database operations - safe upserts to prevent FK violations."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def ensure_user_exists(
    db_service,
    user_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
) -> None:
    """
    Ensure user exists in database with current metadata.
    
    Uses INSERT ... ON CONFLICT DO UPDATE to atomically:
    - Create user if missing
    - Update username/first_name if changed
    
    This prevents FK violations when logging events or payments.
    Safe to call multiple times (idempotent).
    
    Args:
        db_service: Database service
        user_id: Telegram user ID
        username: Optional Telegram username
        first_name: Optional first name
    
    Raises:
        Never raises - logs warnings on failure
    """
    if not db_service:
        logger.warning(f"ensure_user_exists: no db_service for user {user_id}")
        return
    
    try:
        await db_service.execute(
            """
            INSERT INTO users (user_id, username, first_name, created_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (user_id) 
            DO UPDATE SET
                username = COALESCE(EXCLUDED.username, users.username),
                first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                updated_at = NOW()
            """,
            user_id,
            username,
            first_name,
        )
        logger.debug(f"User {user_id} ensured in DB")
        
    except Exception as e:
        # Non-critical: log warning but don't crash
        logger.warning(f"Failed to ensure user {user_id}: {e}")
