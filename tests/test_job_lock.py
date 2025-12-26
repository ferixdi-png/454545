"""Tests for job locking system."""
import time
import pytest

from app.locking.job_lock import (
    acquire_job_lock,
    release_job_lock,
    cleanup_expired_locks,
    get_lock_stats,
    _job_locks,
)


@pytest.fixture(autouse=True)
def clear_locks():
    """Clear lock storage before each test."""
    _job_locks.clear()
    yield
    _job_locks.clear()


def test_acquire_first_lock():
    """Test acquiring lock when no lock exists."""
    acquired, existing = acquire_job_lock(
        uid=123,
        rid="req-001",
        model_id="test-model",
        ttl_s=60.0
    )
    
    assert acquired is True
    assert existing is None
    assert 123 in _job_locks
    assert _job_locks[123].model_id == "test-model"


def test_acquire_blocked_by_active_lock():
    """Test that second acquire is blocked while first is active."""
    # First acquire
    acquired1, _ = acquire_job_lock(123, "req-001", "model-a", ttl_s=60.0)
    assert acquired1 is True
    
    # Second acquire (should fail)
    acquired2, existing = acquire_job_lock(123, "req-002", "model-b", ttl_s=60.0)
    assert acquired2 is False
    assert existing is not None
    assert existing.rid == "req-001"
    assert existing.model_id == "model-a"


def test_acquire_after_expiry():
    """Test that lock can be acquired after TTL expires."""
    # Acquire with very short TTL
    acquire_job_lock(123, "req-001", "model-a", ttl_s=0.1)
    
    # Wait for expiry
    time.sleep(0.15)
    
    # Should be able to acquire again
    acquired, existing = acquire_job_lock(123, "req-002", "model-b", ttl_s=60.0)
    assert acquired is True
    assert existing is None
    assert _job_locks[123].rid == "req-002"


def test_release_existing_lock():
    """Test releasing an active lock."""
    acquire_job_lock(123, "req-001", "model-a", ttl_s=60.0)
    
    released = release_job_lock(123, rid="req-001")
    assert released is True
    assert 123 not in _job_locks


def test_release_nonexistent_lock():
    """Test releasing when no lock exists."""
    released = release_job_lock(999)
    assert released is False


def test_release_with_rid_mismatch():
    """Test release with mismatched RID (still releases)."""
    acquire_job_lock(123, "req-001", "model-a", ttl_s=60.0)
    
    # Release with different RID (should still work)
    released = release_job_lock(123, rid="req-999")
    assert released is True
    assert 123 not in _job_locks


def test_cleanup_expired_locks():
    """Test cleanup of expired locks."""
    # Create mix of active and expired locks
    acquire_job_lock(100, "req-100", "model-a", ttl_s=0.1)  # Will expire
    acquire_job_lock(200, "req-200", "model-b", ttl_s=0.1)  # Will expire
    acquire_job_lock(300, "req-300", "model-c", ttl_s=60.0)  # Active
    
    # Wait for expiry
    time.sleep(0.15)
    
    # Cleanup
    removed = cleanup_expired_locks()
    
    assert removed == 2
    assert 100 not in _job_locks
    assert 200 not in _job_locks
    assert 300 in _job_locks


def test_get_lock_stats_empty():
    """Test stats when no locks exist."""
    stats = get_lock_stats()
    assert stats["active_locks"] == 0
    assert stats["oldest_lock_age_s"] == 0


def test_get_lock_stats_with_locks():
    """Test stats with active locks."""
    acquire_job_lock(100, "req-100", "model-a", ttl_s=60.0)
    time.sleep(0.1)
    acquire_job_lock(200, "req-200", "model-b", ttl_s=60.0)
    
    stats = get_lock_stats()
    assert stats["active_locks"] == 2
    assert stats["oldest_lock_age_s"] >= 0.1


def test_multiple_users_independent():
    """Test that different users have independent locks."""
    acquire_job_lock(100, "req-100", "model-a", ttl_s=60.0)
    acquire_job_lock(200, "req-200", "model-b", ttl_s=60.0)
    
    assert 100 in _job_locks
    assert 200 in _job_locks
    assert _job_locks[100].model_id == "model-a"
    assert _job_locks[200].model_id == "model-b"


def test_lock_reacquire_after_release():
    """Test that lock can be reacquired immediately after release."""
    acquire_job_lock(123, "req-001", "model-a", ttl_s=60.0)
    release_job_lock(123)
    
    # Should be able to acquire again
    acquired, existing = acquire_job_lock(123, "req-002", "model-b", ttl_s=60.0)
    assert acquired is True
    assert existing is None
    assert _job_locks[123].rid == "req-002"
