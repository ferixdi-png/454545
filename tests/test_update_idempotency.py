"""
Test multi-instance idempotency via processed_updates table.

Validates that duplicate Telegram updates are rejected when running
multiple bot instances (e.g., during Render rolling deployments).
"""
import pytest
import os


# Skip DB tests if no database available
TEST_DB = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")


@pytest.mark.skipif(not TEST_DB, reason="No DATABASE_URL")
@pytest.mark.asyncio
async def test_mark_update_processed_first_time():
    """Test marking a new update as processed."""
    from app.database.services import DatabaseService
    from app.database.processed_updates import mark_update_processed, is_update_processed
    
    db_service = DatabaseService(TEST_DB)
    await db_service.initialize()
    
    update_id = 123456789
    
    # First time should return True
    is_first = await mark_update_processed(db_service, update_id)
    assert is_first is True, "First time marking should return True"
    
    # Verify it's now marked
    is_processed = await is_update_processed(db_service, update_id)
    assert is_processed is True, "Update should be marked as processed"
    
    await db_service.close()


@pytest.mark.skipif(not TEST_DB, reason="No DATABASE_URL")
@pytest.mark.asyncio
async def test_mark_update_processed_duplicate():
    """Test marking the same update twice (idempotency)."""
    from app.database.services import DatabaseService
    from app.database.processed_updates import mark_update_processed, is_update_processed
    
    db_service = DatabaseService(TEST_DB)
    await db_service.initialize()
    
    update_id = 987654321
    
    # First call
    is_first_1 = await mark_update_processed(db_service, update_id)
    assert is_first_1 is True, "First call should return True"
    
    # Second call (duplicate)
    is_first_2 = await mark_update_processed(db_service, update_id)
    assert is_first_2 is False, "Duplicate call should return False"
    
    # Verify still marked
    is_processed = await is_update_processed(db_service, update_id)
    assert is_processed is True, "Update should still be marked"
    
    await db_service.close()


@pytest.mark.skipif(not TEST_DB, reason="No DATABASE_URL")
@pytest.mark.asyncio
async def test_is_update_processed_new():
    """Test checking if a new update was processed."""
    from app.database.services import DatabaseService
    from app.database.processed_updates import is_update_processed
    
    db_service = DatabaseService(TEST_DB)
    await db_service.initialize()
    
    update_id = 111222333
    
    # Not yet processed
    is_processed = await is_update_processed(db_service, update_id)
    assert is_processed is False, "New update should not be marked"
    
    await db_service.close()


@pytest.mark.skipif(not TEST_DB, reason="No DATABASE_URL")
@pytest.mark.asyncio
async def test_multi_instance_race_condition():
    """
    Simulate two instances trying to process the same update.
    
    This mimics the scenario during Render rolling deployment:
    - Instance A receives update 500
    - Instance B also receives update 500
    - Only one should process it (first to mark it)
    """
    from app.database.services import DatabaseService
    from app.database.processed_updates import mark_update_processed, is_update_processed
    
    db_service = DatabaseService(TEST_DB)
    await db_service.initialize()
    
    update_id = 555666777
    
    # Instance A marks first
    instance_a_result = await mark_update_processed(db_service, update_id)
    assert instance_a_result is True, "Instance A should win the race"
    
    # Instance B tries to mark (loses race)
    instance_b_result = await mark_update_processed(db_service, update_id)
    assert instance_b_result is False, "Instance B should detect duplicate"
    
    # Verify only one processing occurred
    is_processed = await is_update_processed(db_service, update_id)
    assert is_processed is True
    
    await db_service.close()


def test_processed_updates_logic_import():
    """Test that processed_updates module can be imported."""
    from app.database.processed_updates import mark_update_processed, is_update_processed, cleanup_old_updates
    
    # Verify functions exist
    assert callable(mark_update_processed)
    assert callable(is_update_processed)
    assert callable(cleanup_old_updates)
