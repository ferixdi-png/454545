"""
Tests for payment safety invariants:
- Charge only on success
- Auto-refund on fail/timeout
- Idempotency protection
"""
import pytest
import asyncio
from app.payments.charges import ChargeManager


@pytest.fixture
def charge_manager():
    """Create charge manager instance."""
    return ChargeManager()


@pytest.mark.asyncio
async def test_commit_charge_idempotency(charge_manager):
    """Test that commit_charge is idempotent."""
    task_id = "test_task_1"
    user_id = 123
    amount = 10.0
    
    # Create pending charge
    await charge_manager.create_pending_charge(task_id, user_id, amount, "test_model")
    
    # Commit first time
    result1 = await charge_manager.commit_charge(task_id)
    assert result1['status'] == 'committed'
    assert result1['idempotent'] is False
    
    # Commit second time (should be no-op)
    result2 = await charge_manager.commit_charge(task_id)
    assert result2['status'] == 'already_committed'
    assert result2['idempotent'] is True


@pytest.mark.asyncio
async def test_release_charge_idempotency(charge_manager):
    """Test that release_charge is idempotent."""
    task_id = "test_task_2"
    user_id = 123
    amount = 10.0
    
    # Create pending charge
    await charge_manager.create_pending_charge(task_id, user_id, amount, "test_model")
    
    # Release first time
    result1 = await charge_manager.release_charge(task_id, "test_reason")
    assert result1['status'] == 'released'
    assert result1['idempotent'] is False
    
    # Release second time (should be no-op)
    result2 = await charge_manager.release_charge(task_id, "test_reason")
    assert result2['status'] == 'already_released'
    assert result2['idempotent'] is True


@pytest.mark.asyncio
async def test_charge_only_on_success(charge_manager):
    """Test that charge is only committed on success."""
    task_id = "test_task_3"
    user_id = 123
    amount = 10.0
    
    # Create pending charge
    await charge_manager.create_pending_charge(task_id, user_id, amount, "test_model")
    
    # Simulate success: commit charge
    commit_result = await charge_manager.commit_charge(task_id)
    assert commit_result['status'] == 'committed'
    
    # Check status
    status = await charge_manager.get_charge_status(task_id)
    assert status['status'] == 'committed'
    assert status['message'] == 'Оплачено'


@pytest.mark.asyncio
async def test_auto_refund_on_fail(charge_manager):
    """Test auto-refund on generation failure."""
    task_id = "test_task_4"
    user_id = 123
    amount = 10.0
    
    # Create pending charge
    await charge_manager.create_pending_charge(task_id, user_id, amount, "test_model")
    
    # Simulate fail: release charge
    release_result = await charge_manager.release_charge(task_id, "generation_failed")
    assert release_result['status'] == 'released'
    
    # Check status
    status = await charge_manager.get_charge_status(task_id)
    assert status['status'] == 'released'
    assert status['message'] == 'Деньги не списаны'


@pytest.mark.asyncio
async def test_refund_committed_charge(charge_manager):
    """Test refunding an already committed charge."""
    task_id = "test_task_5"
    user_id = 123
    amount = 10.0
    
    # Create and commit charge
    await charge_manager.create_pending_charge(task_id, user_id, amount, "test_model")
    await charge_manager.commit_charge(task_id)
    
    # Try to release (should trigger refund)
    release_result = await charge_manager.release_charge(task_id, "cancelled")
    assert release_result['status'] == 'refunded'


@pytest.mark.asyncio
async def test_charge_status_messages(charge_manager):
    """Test user-visible status messages."""
    task_id = "test_task_6"
    user_id = 123
    amount = 10.0
    
    # Pending
    await charge_manager.create_pending_charge(task_id, user_id, amount, "test_model")
    status = await charge_manager.get_charge_status(task_id)
    assert status['status'] == 'pending'
    assert status['message'] == 'Ожидание оплаты'
    
    # Committed
    await charge_manager.commit_charge(task_id)
    status = await charge_manager.get_charge_status(task_id)
    assert status['status'] == 'committed'
    assert status['message'] == 'Оплачено'
    
    # Released (new task)
    task_id2 = "test_task_7"
    await charge_manager.create_pending_charge(task_id2, user_id, amount, "test_model")
    await charge_manager.release_charge(task_id2, "test")
    status = await charge_manager.get_charge_status(task_id2)
    assert status['status'] == 'released'
    assert status['message'] == 'Деньги не списаны'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

