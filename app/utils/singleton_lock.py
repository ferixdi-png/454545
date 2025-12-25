"""
Async wrappers for singleton lock compatibility.
Provides acquire_singleton_lock and release_singleton_lock functions.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Module-global instance
_singleton_lock_instance = None


async def acquire_singleton_lock(dsn: Optional[str] = None, timeout: float = 5.0) -> bool:
    """
    Async wrapper to acquire singleton lock.
    
    Args:
        dsn: Database connection string
        timeout: Lock acquisition timeout
        
    Returns:
        True if lock acquired, False otherwise
    """
    global _singleton_lock_instance
    
    # Explicit import - no try/except fallback
    from app.locking.single_instance import SingletonLock
    
    if _singleton_lock_instance is None:
        _singleton_lock_instance = SingletonLock(dsn)
    
    return await _singleton_lock_instance.acquire(timeout)


async def release_singleton_lock() -> None:
    """
    Async wrapper to release singleton lock.
    """
    global _singleton_lock_instance
    
    if _singleton_lock_instance is not None:
        await _singleton_lock_instance.release()
        _singleton_lock_instance = None

