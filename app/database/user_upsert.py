"""Ensure user exists in DB before operations (prevents FK violations)."""
import logging
from typing import Optional
from datetime import datetime

log = logging.getLogger(__name__)

# Cache to avoid spamming DB with upserts
_user_upsert_cache: dict[int, float] = {}  # user_id -> timestamp
UPSERT_TTL_SECONDS = 600  # 10 minutes


async def ensure_user_exists(
    pool,
    user_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    force: bool = False,
) -> bool:
    """Ensure user exists in users table (upsert).
    
    Prevents FK violations in generation_events, payments, balances, etc.
    
    Args:
        pool: Database pool
        user_id: Telegram user ID
        username: Telegram username
        first_name: Telegram first name
        last_name: Telegram last name
        force: Force upsert even if cached
    
    Returns:
        True if user exists/created
    """
    if not pool:
        return False
    
    # Check cache to avoid spam
    if not force:
        last_upsert = _user_upsert_cache.get(user_id, 0)
        if (datetime.utcnow().timestamp() - last_upsert) < UPSERT_TTL_SECONDS:
            return True  # Recently upserted
    
    try:
        async with pool.acquire() as conn:
            # Try new schema (tg_username, tg_first_name, tg_last_name)
            try:
                await conn.execute(
                    """
                    INSERT INTO users (user_id, tg_username, tg_first_name, tg_last_name, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, NOW(), NOW())
                    ON CONFLICT (user_id) 
                    DO UPDATE SET 
                        tg_username = EXCLUDED.tg_username,
                        tg_first_name = EXCLUDED.tg_first_name,
                        tg_last_name = EXCLUDED.tg_last_name,
                        updated_at = NOW()
                    """,
                    user_id,
                    username,
                    first_name,
                    last_name,
                )
            except Exception:
                # Fallback to old schema (username, first_name, last_name)
                await conn.execute(
                    """
                    INSERT INTO users (user_id, username, first_name, last_name, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, NOW(), NOW())
                    ON CONFLICT (user_id) 
                    DO UPDATE SET 
                        username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        updated_at = NOW()
                    """,
                    user_id,
                    username,
                    first_name,
                    last_name,
                )
            
            # Update cache
            _user_upsert_cache[user_id] = datetime.utcnow().timestamp()
            
            log.debug(f"Ensured user exists: {user_id}")
            return True
            
    except Exception as e:
        log.warning(f"Failed to ensure user exists (non-critical): {e}")
        return False


async def ensure_user_from_telegram(pool, tg_user) -> bool:
    """Ensure user exists from Telegram User object.
    
    Args:
        pool: Database pool
        tg_user: Telegram User object
    
    Returns:
        True if successful
    """
    if not tg_user:
        return False
    
    return await ensure_user_exists(
        pool,
        user_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
    )


def clear_user_cache(user_id: Optional[int] = None):
    """Clear user upsert cache.
    
    Args:
        user_id: Specific user ID to clear, or None for all
    """
    if user_id is not None:
        _user_upsert_cache.pop(user_id, None)
    else:
        _user_upsert_cache.clear()
