"""Test cancel flow and lock release."""
import pytest
from app.ui.cancel_handler import (
    set_cancel_flag,
    is_cancelled,
    clear_cancel_flag,
    cancel_task,
    handle_timeout,
    should_allow_cancel,
    get_cancel_confirmation_message,
)


def test_cancel_flag_lifecycle():
    """Test cancel flag set/check/clear cycle."""
    task_id = "test_task_123"
    
    # Initially not cancelled
    assert is_cancelled(task_id) is False
    
    # Set cancel flag
    set_cancel_flag(task_id)
    assert is_cancelled(task_id) is True
    
    # Clear flag
    clear_cancel_flag(task_id)
    assert is_cancelled(task_id) is False


@pytest.mark.asyncio
async def test_cancel_task_basic():
    """Test basic task cancellation."""
    task_id = "cancel_test_456"
    user_id = 789
    
    result = await cancel_task(task_id, user_id)
    
    assert result is True, "Cancel should succeed"
    
    # Flag should be cleared after cancel completes
    # (cancel_task clears it internally)


@pytest.mark.asyncio
async def test_cancel_task_with_lock_release():
    """Test cancel task calls lock release function."""
    task_id = "lock_test_789"
    user_id = 101112
    
    lock_released = False
    
    async def mock_release_lock(uid):
        nonlocal lock_released
        lock_released = True
        assert uid == user_id, "Should pass correct user_id"
    
    await cancel_task(task_id, user_id, release_lock_func=mock_release_lock)
    
    assert lock_released is True, "Lock release function should be called"


@pytest.mark.asyncio
async def test_cancel_task_with_idempotency():
    """Test cancel task finalizes idempotency."""
    task_id = "idempotency_test_101"
    user_id = 131415
    
    finalized = False
    
    async def mock_finalize(tid, status):
        nonlocal finalized
        finalized = True
        assert tid == task_id, "Should pass correct task_id"
        assert status == "cancelled", "Status should be cancelled"
    
    await cancel_task(task_id, user_id, finalize_idempotency_func=mock_finalize)
    
    assert finalized is True, "Idempotency finalize should be called"


@pytest.mark.asyncio
async def test_timeout_handling_short():
    """Test timeout handling for short duration."""
    result = await handle_timeout("task1", 123, elapsed_seconds=60)
    
    assert result["status"] == "timeout_short"
    assert result["action"] == "wait_more"
    assert "подожд" in result["message"].lower()


@pytest.mark.asyncio
async def test_timeout_handling_medium():
    """Test timeout handling for medium duration."""
    result = await handle_timeout("task2", 123, elapsed_seconds=180)
    
    assert result["status"] == "timeout_medium"
    assert result["action"] == "retry"
    assert "повтор" in result["message"].lower()


@pytest.mark.asyncio
async def test_timeout_handling_long():
    """Test timeout handling for long duration."""
    result = await handle_timeout("task3", 123, elapsed_seconds=400)
    
    assert result["status"] == "timeout_long"
    assert result["action"] == "failed"


def test_should_allow_cancel_timing():
    """Test cancel timing logic."""
    # Should NOT allow cancel immediately
    assert should_allow_cancel(1) is False
    assert should_allow_cancel(3) is False
    
    # Should allow after 5+ seconds
    assert should_allow_cancel(5) is True
    assert should_allow_cancel(10) is True
    assert should_allow_cancel(60) is True


def test_cancel_confirmation_message():
    """Test cancel confirmation message."""
    msg = get_cancel_confirmation_message()
    
    assert isinstance(msg, str)
    assert len(msg) > 0
    assert "отмен" in msg.lower()


@pytest.mark.asyncio
async def test_cancel_multiple_tasks():
    """Test cancelling multiple different tasks."""
    task1 = "multi_task_1"
    task2 = "multi_task_2"
    
    set_cancel_flag(task1)
    set_cancel_flag(task2)
    
    assert is_cancelled(task1) is True
    assert is_cancelled(task2) is True
    
    clear_cancel_flag(task1)
    
    assert is_cancelled(task1) is False
    assert is_cancelled(task2) is True  # Still cancelled
    
    clear_cancel_flag(task2)
    assert is_cancelled(task2) is False
