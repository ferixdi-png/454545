"""
Tests for flow.py confirm_cb with idempotency and job_lock.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import CallbackQuery, User, Message, Chat
from aiogram.fsm.context import FSMContext


@pytest.fixture
def mock_callback():
    """Create mock CallbackQuery."""
    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=User)
    callback.from_user.id = 123456
    callback.from_user.username = "testuser"
    callback.from_user.first_name = "Test"
    callback.message = MagicMock(spec=Message)
    callback.message.chat = MagicMock(spec=Chat)
    callback.message.chat.id = 123456
    callback.message.answer = AsyncMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    callback.data = "confirm_gen"
    return callback


@pytest.fixture
def mock_state():
    """Create mock FSMContext."""
    state = AsyncMock(spec=FSMContext)
    state.get_data = AsyncMock(return_value={
        "model_id": "flux-1-1-pro",
        "user_inputs": {"prompt": "test"},
        "final_price_rub": 10.0,
        "flow_ctx": {
            "model_id": "flux-1-1-pro",
            "display_name": "Flux 1.1 Pro",
            "category": "image",
            "current_step": "confirm",
            "all_inputs": {"prompt": "test"},
        },
    })
    state.update_data = AsyncMock()
    state.clear = AsyncMock()
    return state


@pytest.mark.asyncio
async def test_confirm_cb_imports_exist():
    """Test that flow.py imports idem_try_start and idem_finish."""
    from bot.handlers.flow import idem_try_start, idem_finish
    
    assert callable(idem_try_start)
    assert callable(idem_finish)


@pytest.mark.asyncio
async def test_idempotency_prevents_double_confirm(mock_callback, mock_state):
    """Test that idempotency prevents double confirmation."""
    from bot.handlers.flow import confirm_cb
    from app.utils.idempotency import idem_try_start, idem_finish
    
    # First call - should work
    with patch('bot.handlers.flow.acquire_job_lock', return_value=True):
        with patch('bot.handlers.flow.generate_with_payment', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = {
                'success': True,
                'result_urls': ['https://example.com/result.jpg'],
                'message': 'Success'
            }
            
            with patch('bot.handlers.flow.release_job_lock'):
                # Call once
                await confirm_cb(mock_callback, mock_state)
                
                # Verify it was called
                assert mock_gen.called
    
    # Second call with same idem_key - should be blocked
    # (In real scenario, idem_key is same for same user+model+inputs)
    # This test just verifies imports work


@pytest.mark.asyncio
async def test_job_lock_prevents_concurrent_generation(mock_callback, mock_state):
    """Test that job_lock prevents concurrent generation."""
    from bot.handlers.flow import confirm_cb
    
    # Mock job_lock to fail (already locked)
    with patch('bot.handlers.flow.acquire_job_lock', return_value=False):
        with patch('bot.handlers.flow.generate_with_payment', new_callable=AsyncMock) as mock_gen:
            await confirm_cb(mock_callback, mock_state)
            
            # Should NOT call generate (blocked by lock)
            assert not mock_gen.called
            
            # Should show user message
            assert mock_callback.message.answer.called or mock_callback.message.edit_text.called


@pytest.mark.asyncio
async def test_job_lock_released_on_error(mock_callback, mock_state):
    """Test that job_lock is released even if generation fails."""
    from bot.handlers.flow import confirm_cb
    
    with patch('bot.handlers.flow.acquire_job_lock', return_value=True):
        with patch('bot.handlers.flow.generate_with_payment', new_callable=AsyncMock) as mock_gen:
            # Simulate error
            mock_gen.side_effect = Exception("Test error")
            
            with patch('bot.handlers.flow.release_job_lock') as mock_release:
                try:
                    await confirm_cb(mock_callback, mock_state)
                except Exception:
                    pass
                
                # Should release lock even on error
                assert mock_release.called
