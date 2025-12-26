"""Bot information caching and retrieval."""
import asyncio
import logging
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Global cache for bot username
_bot_username_cache: Optional[str] = None
_cache_timestamp: Optional[datetime] = None
_cache_ttl = timedelta(minutes=30)


async def get_bot_username(bot) -> Optional[str]:
    """
    Get bot username with caching and fallback.
    
    Priority:
    1. ENV variable (TELEGRAM_BOT_USERNAME or BOT_USERNAME)
    2. Cached value from bot.get_me() (30 min TTL)
    3. Fresh call to bot.get_me()
    
    Returns:
        Bot username (without @) or None if unable to retrieve
    """
    global _bot_username_cache, _cache_timestamp
    
    # 1. Try config/env first
    try:
        from app.utils.config import get_config
        cfg = get_config()
        if cfg.telegram_bot_username:
            username = cfg.telegram_bot_username.lstrip('@')
            if username:
                return username
    except Exception as e:
        logger.debug(f"Could not get username from config: {e}")
    
    # 2. Check cache
    if _bot_username_cache and _cache_timestamp:
        if datetime.now() - _cache_timestamp < _cache_ttl:
            return _bot_username_cache
    
    # 3. Fetch from API and cache
    try:
        me = await bot.get_me()
        if me and me.username:
            _bot_username_cache = me.username
            _cache_timestamp = datetime.now()
            logger.info(f"✅ Bot username cached: @{_bot_username_cache}")
            return _bot_username_cache
    except Exception as e:
        logger.error(f"Failed to get bot username via get_me(): {e}")
    
    return None


def get_referral_link(username: Optional[str], user_id: int) -> Optional[str]:
    """
    Generate referral link.
    
    Args:
        username: Bot username (without @), None if unavailable
        user_id: Referrer user ID
    
    Returns:
        Referral link or None if username is unavailable
    """
    if not username:
        return None
    
    return f"https://t.me/{username}?start=ref_{user_id}"
