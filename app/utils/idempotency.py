"""
Lightweight idempotency utilities (in-memory fallback).

Production note:
- For full durability, persist idempotency keys in DB (jobs table).
- This module provides a safe fallback to prevent double-click / retry storms from
  creating duplicate upstream tasks and duplicate charges.
"""
from __future__ import annotations

import time
import threading
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

_LOCK = threading.Lock()

@dataclass
class IdemEntry:
    created_at: float
    status: str  # 'started' | 'done' | 'failed'
    value: Optional[dict] = None

_STORE: Dict[str, IdemEntry] = {}

def idem_try_start(key: str, ttl_s: float = 120.0) -> Tuple[bool, Optional[IdemEntry]]:
    """
    Try to start an idempotent operation.

    Returns:
        (started, existing_entry)
    """
    now = time.time()
    with _LOCK:
        # purge expired
        expired = [k for k,v in _STORE.items() if now - v.created_at > ttl_s]
        for k in expired:
            _STORE.pop(k, None)

        if key in _STORE:
            return False, _STORE[key]

        _STORE[key] = IdemEntry(created_at=now, status='started', value=None)
        return True, None

def idem_finish(key: str, status: str, value: Optional[dict] = None) -> None:
    with _LOCK:
        if key in _STORE:
            _STORE[key].status = status
            _STORE[key].value = value


def build_generation_key(user_id: int, model_id: str, inputs: dict) -> str:
    """
    Build stable idempotency key for generation.
    
    Args:
        user_id: User ID
        model_id: Model ID
        inputs: Normalized user inputs dict
    
    Returns:
        Idempotency key (stable hash)
    """
    import hashlib
    
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


def idem_get(key: str) -> Optional[IdemEntry]:
    with _LOCK:
        return _STORE.get(key)


def cleanup_old_keys(max_age_seconds: float) -> int:
    """Clean up old idempotency keys.
    
    Returns: Number of keys cleaned up
    """
    now = time.time()
    with _LOCK:
        expired = [k for k, v in _STORE.items() if now - v.created_at > max_age_seconds]
        for k in expired:
            _STORE.pop(k, None)
        return len(expired)


def clear_all_keys() -> None:
    """Clear all idempotency keys (called on shutdown)."""
    with _LOCK:
        _STORE.clear()
