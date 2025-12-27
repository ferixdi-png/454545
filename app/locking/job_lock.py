"""
In-memory TTL-based job lock for single-instance deployment.

Prevents users from starting multiple concurrent generations.
For multi-instance (production scale), replace with Redis-based locking.
"""
import logging
import time
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class JobLock:
    """Job lock metadata."""
    uid: int
    rid: str
    model_id: str
    acquired_at: float
    ttl_s: float
    
    def is_expired(self) -> bool:
        """Check if lock has expired."""
        return time.time() > (self.acquired_at + self.ttl_s)


# Global in-memory lock storage (single instance only)
_job_locks: Dict[int, JobLock] = {}


def acquire_job_lock(
    uid: int,
    rid: str,
    model_id: str,
    ttl_s: float = 1800.0
) -> Tuple[bool, Optional[JobLock]]:
    """
    Try to acquire a job lock for user.
    
    Args:
        uid: User ID
        rid: Request ID
        model_id: Model being used
        ttl_s: Lock TTL in seconds (default 30 min)
        
    Returns:
        (acquired: bool, existing_lock: JobLock | None)
        - (True, None) if lock acquired
        - (False, JobLock) if lock already held and not expired
    """
    now = time.time()
    
    # Check if user already has a lock
    if uid in _job_locks:
        existing = _job_locks[uid]
        
        # If expired, remove and allow new lock
        if existing.is_expired():
            logger.info(
                f"🔓 Expired lock removed for user {uid} "
                f"(rid={existing.rid}, age={now - existing.acquired_at:.1f}s)"
            )
            del _job_locks[uid]
        else:
            # Active lock exists
            logger.warning(
                f"⛔ Lock denied for user {uid}: active lock exists "
                f"(rid={existing.rid}, model={existing.model_id}, "
                f"age={now - existing.acquired_at:.1f}s, ttl={existing.ttl_s}s)"
            )
            return False, existing
    
    # Acquire new lock
    lock = JobLock(
        uid=uid,
        rid=rid,
        model_id=model_id,
        acquired_at=now,
        ttl_s=ttl_s
    )
    _job_locks[uid] = lock
    
    logger.info(
        f"🔒 Lock acquired for user {uid} "
        f"(rid={rid}, model={model_id}, ttl={ttl_s}s)"
    )
    
    return True, None


def release_job_lock(uid: int, rid: Optional[str] = None) -> bool:
    """
    Release job lock for user.
    
    Args:
        uid: User ID
        rid: Optional request ID (for verification)
        
    Returns:
        True if lock was released, False if no lock found
    """
    if uid not in _job_locks:
        logger.debug(f"🔓 No lock to release for user {uid}")
        return False
    
    existing = _job_locks[uid]
    
    # Verify RID if provided
    if rid and existing.rid != rid:
        logger.warning(
            f"⚠️ Lock release RID mismatch for user {uid}: "
            f"expected={existing.rid}, got={rid}"
        )
        # Still release to avoid stuck locks
    
    del _job_locks[uid]
    logger.info(
        f"🔓 Lock released for user {uid} "
        f"(rid={existing.rid}, held_for={time.time() - existing.acquired_at:.1f}s)"
    )
    
    return True


def cleanup_expired_locks() -> int:
    """
    Clean up all expired locks.
    
    Returns:
        Number of locks removed
    """
    now = time.time()
    expired_uids = [
        uid for uid, lock in _job_locks.items()
        if lock.is_expired()
    ]
    
    for uid in expired_uids:
        lock = _job_locks[uid]
        logger.info(
            f"🧹 Cleaning expired lock for user {uid} "
            f"(rid={lock.rid}, age={now - lock.acquired_at:.1f}s)"
        )
        del _job_locks[uid]
    
    return len(expired_uids)


def get_lock_stats() -> Dict[str, any]:
    """
    Get lock statistics for monitoring.
    
    Returns:
        Dict with active locks count and oldest lock age
    """
    if not _job_locks:
        return {"active_locks": 0, "oldest_lock_age_s": 0}
    
    now = time.time()
    oldest_age = max(
        now - lock.acquired_at
        for lock in _job_locks.values()
    )
    
    return {
        "active_locks": len(_job_locks),
        "oldest_lock_age_s": oldest_age
    }


def cleanup_old_locks(max_age_seconds: float) -> int:
    """Clean up locks older than specified age.
    
    Used at startup to recover from crashes.
    
    Returns: Number of locks cleaned up
    """
    now = time.time()
    old_uids = [
        uid for uid, lock in _job_locks.items()
        if now - lock.acquired_at > max_age_seconds
    ]
    
    for uid in old_uids:
        lock = _job_locks[uid]
        logger.info(
            f"🧹 Removing stuck lock for user {uid} "
            f"(age={now - lock.acquired_at:.1f}s)"
        )
        del _job_locks[uid]
    
    return len(old_uids)


def cleanup_all_locks() -> None:
    """Clear all locks (called on shutdown)."""
    _job_locks.clear()
