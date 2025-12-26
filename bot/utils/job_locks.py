from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class JobLock:
    rid: str
    model_id: str
    ts: float
    ttl_s: float


_locks: Dict[int, JobLock] = {}


def try_acquire(user_id: int, rid: str, model_id: str, ttl_s: float = 900.0) -> Tuple[bool, Optional[JobLock]]:
    """Acquire per-user generation lock. Returns (acquired, existing_lock)."""
    now = time.time()
    existing = _locks.get(int(user_id))
    if existing and (now - existing.ts) <= existing.ttl_s:
        return False, existing
    _locks[int(user_id)] = JobLock(rid=rid, model_id=model_id, ts=now, ttl_s=float(ttl_s))
    return True, None


def release(user_id: int, rid: Optional[str] = None) -> None:
    existing = _locks.get(int(user_id))
    if not existing:
        return
    if rid is not None and existing.rid != rid:
        return
    _locks.pop(int(user_id), None)


def get(user_id: int) -> Optional[JobLock]:
    existing = _locks.get(int(user_id))
    if not existing:
        return None
    now = time.time()
    if (now - existing.ts) > existing.ttl_s:
        _locks.pop(int(user_id), None)
        return None
    return existing
