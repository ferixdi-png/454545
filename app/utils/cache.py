"""
Simple in-memory cache for frequently accessed data.
Uses LRU cache with TTL support.
"""
import asyncio
import time
import logging
from typing import Any, Optional, Dict, Callable, Awaitable
from functools import wraps

logger = logging.getLogger(__name__)


class TTLCache:
    """
    Simple TTL (Time To Live) cache.
    Thread-safe для async operations.
    """
    
    def __init__(self, default_ttl: float = 300.0):
        """
        Args:
            default_ttl: Default time-to-live in seconds (5 minutes)
        """
        self.default_ttl = default_ttl
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if expired/not found
        """
        async with self._lock:
            if key not in self._cache:
                return None
            
            value, expires_at = self._cache[key]
            
            if time.time() > expires_at:
                # Expired
                del self._cache[key]
                return None
            
            return value
    
    async def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (optional, uses default if not provided)
        """
        ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + ttl
        
        async with self._lock:
            self._cache[key] = (value, expires_at)
    
    async def delete(self, key: str):
        """Delete key from cache."""
        async with self._lock:
            self._cache.pop(key, None)
    
    async def clear(self):
        """Clear all cache."""
        async with self._lock:
            self._cache.clear()
    
    async def cleanup_expired(self):
        """Remove expired entries."""
        current_time = time.time()
        
        async with self._lock:
            expired_keys = [
                key for key, (_, expires_at) in self._cache.items()
                if current_time > expires_at
            ]
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "total_entries": len(self._cache),
            "expired": sum(
                1 for _, expires_at in self._cache.values()
                if time.time() > expires_at
            )
        }


def cached(ttl: float = 300.0, key_prefix: str = ""):
    """
    Decorator для кэширования async функций.
    
    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key
        
    Example:
        @cached(ttl=600.0, key_prefix="user")
        async def get_user(user_id: int):
            # Expensive database query
            return await db.fetch_user(user_id)
    """
    def decorator(func: Callable[..., Awaitable[Any]]):
        # Create cache instance per function
        cache = TTLCache(default_ttl=ttl)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from arguments
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)
            
            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return cached_value
            
            # Cache miss - call function
            logger.debug(f"Cache MISS: {cache_key}")
            result = await func(*args, **kwargs)
            
            # Store in cache
            await cache.set(cache_key, result, ttl=ttl)
            
            return result
        
        # Attach cache instance for manual operations
        wrapper.cache = cache
        return wrapper
    
    return decorator


# Global cache instance for shared data
global_cache = TTLCache(default_ttl=600.0)  # 10 minutes default
