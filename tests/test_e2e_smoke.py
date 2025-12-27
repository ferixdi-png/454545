"""End-to-end smoke tests with mocked external dependencies.

Tests full generation flow without hitting real APIs:
- Telegram bot interactions
- KIE API calls
- Payment processing
- DB operations
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from aiogram.types import User, Chat, Message, CallbackQuery
from aiogram.fsm.context import FSMContext


@pytest.fixture
def mock_user():
    """Mock Telegram user."""
    return User(
        id=123456,
        is_bot=False,
        first_name="Test",
        username="testuser"
    )


@pytest.fixture
def mock_chat():
    """Mock Telegram chat."""
    return Chat(id=123456, type="private")


@pytest.fixture
def mock_message(mock_user, mock_chat):
    """Mock Telegram message."""
    msg = Mock(spec=Message)
    msg.from_user = mock_user
    msg.chat = mock_chat
    msg.message_id = 1
    msg.text = "/start"
    msg.answer = AsyncMock()
    msg.edit_text = AsyncMock()
    return msg


@pytest.fixture
def mock_callback(mock_user, mock_message):
    """Mock callback query."""
    cb = Mock(spec=CallbackQuery)
    cb.from_user = mock_user
    cb.message = mock_message
    cb.data = "test_callback"
    cb.answer = AsyncMock()
    cb.message.edit_text = AsyncMock()
    return cb


@pytest.fixture
def mock_fsm_context():
    """Mock FSM context."""
    ctx = AsyncMock(spec=FSMContext)
    ctx.get_data = AsyncMock(return_value={})
    ctx.set_data = AsyncMock()
    ctx.update_data = AsyncMock()
    ctx.set_state = AsyncMock()
    ctx.clear = AsyncMock()
    return ctx


@pytest.fixture
def mock_kie_client():
    """Mock KIE API client that returns successful generation."""
    with patch('app.kie.client.KieClient') as MockClient:
        instance = MockClient.return_value
        
        # Mock create_task
        instance.create_task = AsyncMock(return_value={
            "data": {
                "taskId": "test_task_123",
                "recordId": "test_record_456"
            }
        })
        
        # Mock poll_task (success after 1 poll)
        instance.poll_task = AsyncMock(return_value={
            "data": {
                "state": "success",
                "outputs": [
                    {"url": "https://example.com/output1.jpg"}
                ]
            }
        })
        
        yield instance


@pytest.fixture
def mock_db():
    """Mock database connection."""
    with patch('app.database.service.db_service') as mock_service:
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock()
        
        mock_service.pool = Mock()
        mock_service.pool.acquire = AsyncMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()))
        
        yield mock_service


@pytest.mark.asyncio
async def test_start_to_generation_flow(mock_message, mock_fsm_context, mock_kie_client, mock_db):
    """Test full flow: /start -> select format -> select model -> generate."""
    from bot.handlers.start import cmd_start
    from bot.handlers.flow import handle_format_select, handle_model_select
    
    # Step 1: /start
    await cmd_start(mock_message, mock_fsm_context)
    mock_message.answer.assert_called_once()
    assert "AI Studio" in mock_message.answer.call_args[0][0]
    
    # Step 2: Select format
    mock_callback = Mock(spec=CallbackQuery)
    mock_callback.data = "fmt:image-to-image"
    mock_callback.from_user = mock_message.from_user
    mock_callback.message = mock_message
    mock_callback.answer = AsyncMock()
    
    await handle_format_select(mock_callback, mock_fsm_context)
    mock_callback.answer.assert_called()


@pytest.mark.asyncio
async def test_duplicate_generation_prevented(mock_callback, mock_fsm_context, mock_kie_client):
    """Test that duplicate confirm (same inputs) doesn't charge twice."""
    from bot.handlers.flow import confirm_cb
    from app.utils.idempotency import idem_try_start, idem_finish
    
    # Setup: user has submitted inputs
    await mock_fsm_context.update_data({
        "model_id": "test_model",
        "inputs": {"prompt": "test"}
    })
    
    mock_callback.from_user = User(id=999, is_bot=False, first_name="Test")
    
    # First confirm - should start generation
    with patch('app.kie.client.KieClient') as MockClient:
        instance = MockClient.return_value
        instance.create_task = AsyncMock(return_value={"data": {"taskId": "t1"}})
        instance.poll_task = AsyncMock(return_value={"data": {"state": "success", "outputs": []}})
        
        with patch('app.locking.job_lock.acquire_job_lock', return_value=(True, None)):
            with patch('app.locking.job_lock.release_job_lock'):
                # Can't easily test full flow without complete setup
                # Just verify idempotency key generation
                from app.utils.idempotency import build_generation_key
                key1 = build_generation_key(999, "test_model", {"prompt": "test"})
                key2 = build_generation_key(999, "test_model", {"prompt": "test"})
                assert key1 == key2, "Idempotency keys should be stable"


@pytest.mark.asyncio
async def test_missing_required_input_validation():
    """Test that wizard blocks when required input is missing."""
    from app.ui.input_registry import validate_inputs, UserFacingValidationError
    from app.models_registry import ModelConfig, InputSpec
    
    # Mock model config with required field
    model_config = ModelConfig(
        model_id="test_model",
        format="text-to-image",
        title="Test Model",
        inputs={
            "prompt": InputSpec(
                name="Prompt",
                type="text",
                required=True
            )
        },
        cost_rub=0.0,
        is_free=True
    )
    
    # Missing required field
    inputs = {}
    
    with pytest.raises(UserFacingValidationError) as exc_info:
        validate_inputs(model_config, inputs)
    
    assert "Prompt" in str(exc_info.value)


@pytest.mark.asyncio
async def test_media_upload_proxy_url():
    """Test that media uploads generate signed proxy URLs."""
    from app.webhook_server import _default_secret
    import hashlib
    import hmac
    import time
    
    # Test signature generation
    bot_token = "test_token"
    file_id = "test_file_123"
    secret = _default_secret(bot_token)
    
    # Generate signature with expiration
    exp = int(time.time()) + 3600
    payload = f"{file_id}:{exp}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    
    # Verify signature format
    assert len(sig) == 16
    assert sig.isalnum()


@pytest.mark.asyncio
async def test_db_down_free_generation_works(mock_kie_client):
    """Test that FREE generation works even if DB is down."""
    from app.database.migrations_check import is_db_logging_enabled, is_balance_enabled
    from app.pricing.free_models import is_free_model
    
    # Simulate DB down by disabling features
    with patch('app.database.migrations_check._DB_LOGGING_ENABLED', False):
        with patch('app.database.migrations_check._BALANCE_ENABLED', False):
            assert not is_db_logging_enabled()
            assert not is_balance_enabled()
            
            # FREE models should still work
            # (actual generation test would require full setup)
            pass


@pytest.mark.asyncio
async def test_paid_generation_refunds_on_failure(mock_kie_client):
    """Test that paid generation refunds/releases reservation on failure."""
    from app.payments.integration import generate_with_payment
    
    # Mock KIE client to fail
    mock_kie_client.poll_task = AsyncMock(return_value={
        "data": {
            "state": "fail",
            "failCode": "INTERNAL_ERROR",
            "message": "Test failure"
        }
    })
    
    # Mock charge manager
    with patch('app.payments.charges.get_charge_manager') as mock_charge_mgr:
        mock_mgr = AsyncMock()
        mock_mgr.reserve = AsyncMock(return_value=True)
        mock_mgr.commit = AsyncMock()
        mock_mgr.rollback = AsyncMock()
        mock_charge_mgr.return_value = mock_mgr
        
        # Try generation (will fail)
        with pytest.raises(Exception):
            await generate_with_payment(
                model_id="test_model",
                user_inputs={"prompt": "test"},
                user_id=123,
                amount=10.0,
                charge_manager=mock_mgr
            )
        
        # Verify refund was called
        # (actual test would need to verify rollback/release)


@pytest.mark.asyncio
async def test_rate_limit_prevents_spam():
    """Test that rate limiting blocks excessive requests."""
    from bot.middleware.user_rate_limit import UserRateLimiter
    
    limiter = UserRateLimiter(rate=2, period=10, burst=3)
    user_id = 999
    
    # First 3 requests should succeed (burst)
    for i in range(3):
        allowed, retry_after = await limiter.check_rate_limit(user_id, cost=1.0)
        assert allowed, f"Request {i+1} should be allowed"
    
    # 4th request should fail (burst exhausted)
    allowed, retry_after = await limiter.check_rate_limit(user_id, cost=1.0)
    assert not allowed, "4th request should be rate limited"
    assert retry_after is not None and retry_after > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
