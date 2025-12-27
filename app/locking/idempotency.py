"""
Idempotency system for webhook retries and duplicate updates.

Telegram/Render can deliver same update multiple times.
This prevents duplicate charges, generations, and tasks.
"""
import time
import hashlib
import logging
from typing import Dict, Any, Optional, Tuple
from threading import Lock

logger = logging.getLogger(__name__)


class IdempotencyStore:
    """In-memory TTL-based idempotency store."""
    
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
    
    def try_start(self, key: str, ttl_s: int = 300) -> Tuple[bool, Optional[Dict]]:
        """
        Try to start operation with given key.
        
        Args:
            key: Idempotency key (unique per operation)
            ttl_s: TTL in seconds (default 5 min)
        
        Returns:
            (started, existing):
                - started=True: operation started (you own it)
                - started=False: operation exists (see existing dict)
                - existing: None if started, or dict with status/payload
        """
        with self._lock:
            now = time.time()
            
            # Cleanup expired entries
            expired = [k for k, v in self._store.items() if v['expires_at'] < now]
            for k in expired:
                del self._store[k]
            
            # Check if key exists
            if key in self._store:
                existing = self._store[key]
                return (False, existing)
            
            # Start new operation
            self._store[key] = {
                'status': 'pending',
                'started_at': now,
                'expires_at': now + ttl_s,
                'payload': None,
            }
            
            return (True, None)
    
    def finish(self, key: str, status: str, payload: Any = None) -> None:
        """
        Mark operation as finished.
        
        Args:
            key: Idempotency key
            status: 'success', 'failed', 'timeout'
            payload: Optional result payload
        """
        with self._lock:
            if key in self._store:
                self._store[key]['status'] = status
                self._store[key]['payload'] = payload
    
    def get(self, key: str) -> Optional[Dict]:
        """Get operation state."""
        with self._lock:
            now = time.time()
            if key in self._store:
                entry = self._store[key]
                if entry['expires_at'] >= now:
                    return entry
                else:
                    del self._store[key]
            return None


# Global singleton
_idem_store = IdempotencyStore()


def idem_try_start(key: str, ttl_s: int = 300) -> Tuple[bool, Optional[Dict]]:
    """
    Try to start idempotent operation.
    
    Returns:
        (started, existing)
    """
    return _idem_store.try_start(key, ttl_s)


def idem_finish(key: str, status: str, payload: Any = None) -> None:
    """Finish idempotent operation."""
    _idem_store.finish(key, status, payload)


def idem_get(key: str) -> Optional[Dict]:
    """Get operation state."""
    return _idem_store.get(key)


def build_generation_key(user_id: int, model_id: str, inputs: Dict[str, Any]) -> str:
    """
    Build stable idempotency key for generation.
    
    Args:
        user_id: User ID
        model_id: Model ID
        inputs: Normalized user inputs dict
    
    Returns:
        Idempotency key (stable hash)
    """
    # Normalize inputs (sorted keys)
    normalized = {k: v for k, v in sorted(inputs.items()) if v is not None}
    
    # Build stable repr
    parts = [
        str(user_id),
        model_id,
        repr(normalized),
    ]
    
    payload = '|'.join(parts)
    hash_hex = hashlib.sha256(payload.encode()).hexdigest()[:16]
    
    return f"gen:{user_id}:{model_id}:{hash_hex}"
