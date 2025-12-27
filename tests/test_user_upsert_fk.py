"""Test DB user upsert to prevent FK violations."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_ensure_user_exists_creates_new_user():
    """ensure_user_exists should create user if not exists."""
    from app.database.services import ensure_user_exists
    
    # Mock DB service
    mock_db = MagicMock()
    mock_user_service = AsyncMock()
    mock_user_service.get_or_create = AsyncMock(return_value={
        "user_id": 123,
        "username": "testuser",
        "first_name": "Test",
        "created_just_now": True
    })
    
    with patch('app.database.services.UserService', return_value=mock_user_service):
        await ensure_user_exists(mock_db, 123, "testuser", "Test")
    
    mock_user_service.get_or_create.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_user_exists_updates_existing():
    """ensure_user_exists should be idempotent."""
    from app.database.services import ensure_user_exists
    
    mock_db = MagicMock()
    mock_user_service = AsyncMock()
    mock_user_service.get_or_create = AsyncMock(return_value={
        "user_id": 123,
        "username": "testuser",
        "first_name": "Test",
        "created_just_now": False
    })
    
    with patch('app.database.services.UserService', return_value=mock_user_service):
        # Call twice - should not crash
        await ensure_user_exists(mock_db, 123, "testuser", "Test")
        await ensure_user_exists(mock_db, 123, "testuser", "Test")
    
    assert mock_user_service.get_or_create.call_count == 2


@pytest.mark.asyncio
async def test_generation_event_calls_ensure_user():
    """log_generation_event should call ensure_user_exists (verified by reading code)."""
    from app.database.generation_events import log_generation_event
    import inspect
    
    # Verify ensure_user_exists is called in the function
    source = inspect.getsource(log_generation_event)
    assert "ensure_user_exists" in source, "log_generation_event should call ensure_user_exists"


@pytest.mark.asyncio
async def test_ensure_user_graceful_failure():
    """ensure_user_exists should not crash on DB errors."""
    from app.database.services import ensure_user_exists
    
    mock_db = MagicMock()
    
    with patch('app.database.services.UserService', side_effect=Exception("DB error")):
        # Should not raise
        await ensure_user_exists(mock_db, 123, "test", "Test")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
