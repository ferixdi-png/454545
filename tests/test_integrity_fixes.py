"""Tests for critical integrity fixes."""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch


class TestDatabaseSafety:
    """Test database safety layer."""
    
    @pytest.mark.asyncio
    async def test_ensure_user_exists_creates_user(self):
        """Verify ensure_user_exists creates new user."""
        from app.database.users import ensure_user_exists
        
        db = MagicMock()
        db.execute = AsyncMock()
        
        await ensure_user_exists(db, user_id=12345, username="testuser", first_name="Test")
        
        assert db.execute.called
        call_args = db.execute.call_args
        assert "INSERT INTO users" in call_args[0][0]
        assert "ON CONFLICT" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_ensure_user_exists_handles_no_db(self):
        """Verify graceful handling when db_service is None."""
        from app.database.users import ensure_user_exists
        
        # Should not raise
        await ensure_user_exists(None, user_id=12345)
    
    @pytest.mark.asyncio
    async def test_log_generation_never_raises(self):
        """Verify generation event logging never crashes generation."""
        from app.database.generation_events import log_generation_event
        
        db = MagicMock()
        db.fetchval = AsyncMock(side_effect=Exception("DB error"))
        
        # Should return None, not raise
        result = await log_generation_event(
            db,
            user_id=123,
            model_id="test",
            status="started"
        )
        
        assert result is None


class TestIdempotency:
    """Test idempotency system."""
    
    def test_idem_try_start_first_time(self):
        """Verify first start succeeds."""
        from app.utils.idempotency import idem_try_start
        
        started, existing = idem_try_start("test_key_1")
        
        assert started is True
        assert existing is None
    
    def test_idem_try_start_duplicate(self):
        """Verify duplicate start is blocked."""
        from app.utils.idempotency import idem_try_start
        
        key = "test_key_2"
        
        # First start
        started1, _ = idem_try_start(key)
        assert started1 is True
        
        # Duplicate start
        started2, existing = idem_try_start(key)
        assert started2 is False
        assert existing is not None
        assert existing.status == 'started'
    
    def test_idem_finish_updates_status(self):
        """Verify finish updates status."""
        from app.utils.idempotency import idem_try_start, idem_finish
        
        key = "test_key_3"
        
        idem_try_start(key)
        idem_finish(key, 'success', {'result': 'ok'})
        
        # Second start should see completed status
        started, existing = idem_try_start(key)
        assert started is False
        assert existing.status == 'success'
    
    def test_build_generation_key_stable(self):
        """Verify generation key is stable for same inputs."""
        from app.utils.idempotency import build_generation_key
        
        inputs1 = {'prompt': 'test', 'style': 'anime'}
        inputs2 = {'style': 'anime', 'prompt': 'test'}  # Different order
        
        key1 = build_generation_key(123, "flux", inputs1)
        key2 = build_generation_key(123, "flux", inputs2)
        
        assert key1 == key2
    
    def test_build_generation_key_different_for_different_inputs(self):
        """Verify different inputs produce different keys."""
        from app.utils.idempotency import build_generation_key
        
        key1 = build_generation_key(123, "flux", {'prompt': 'test1'})
        key2 = build_generation_key(123, "flux", {'prompt': 'test2'})
        
        assert key1 != key2


class TestInputValidation:
    """Test input validation."""
    
    def test_validate_required_field_missing(self):
        """Verify validation fails for missing required field."""
        from app.ui.input_registry import validate_inputs, UserFacingValidationError
        from app.ui.input_spec import InputSpec, InputField, InputType
        
        model = {
            'model_id': 'test',
            'format': 'text_to_image',
        }
        
        inputs = {}  # Missing prompt
        
        # Mock get_input_spec to return spec with required prompt
        with patch('app.ui.input_registry.get_input_spec') as mock_get_spec:
            mock_get_spec.return_value = InputSpec(
                model_id='test',
                fields=[
                    InputField(name='prompt', type=InputType.TEXT, required=True, description='Prompt')
                ]
            )
            
            with pytest.raises(UserFacingValidationError) as exc_info:
                validate_inputs(model, inputs)
            
            assert 'Prompt' in str(exc_info.value)
    
    def test_validate_number_range(self):
        """Verify number range validation."""
        from app.ui.input_registry import validate_inputs, UserFacingValidationError
        from app.ui.input_spec import InputSpec, InputField, InputType
        
        model = {'model_id': 'test'}
        inputs = {'steps': 150}  # Too high
        
        with patch('app.ui.input_registry.get_input_spec') as mock_get_spec:
            mock_get_spec.return_value = InputSpec(
                model_id='test',
                fields=[
                    InputField(
                        name='steps',
                        type=InputType.NUMBER,
                        required=False,
                        min_value=1,
                        max_value=100,
                        description='Steps'
                    )
                ]
            )
            
            with pytest.raises(UserFacingValidationError) as exc_info:
                validate_inputs(model, inputs)
            
            assert 'максимум' in str(exc_info.value)


class TestPaymentIntegrity:
    """Test payment flow hardening."""
    
    @pytest.mark.asyncio
    async def test_free_model_skips_payment(self):
        """Verify FREE models skip payment."""
        from app.payments.integration import generate_with_payment
        
        with patch('app.payments.integration.is_free_model') as mock_is_free:
            mock_is_free.return_value = True
            
            with patch('app.payments.integration.KieGenerator') as mock_gen:
                mock_gen.return_value.generate = AsyncMock(return_value={
                    'success': True,
                    'result_urls': ['http://example.com/result.jpg']
                })
                
                result = await generate_with_payment(
                    model_id='flux_schnell',
                    user_inputs={'prompt': 'test'},
                    user_id=123,
                    amount=10.0  # Should be ignored
                )
                
                assert result['success'] is True
                assert result['payment_status'] == 'free_tier'


class TestJobLockSafety:
    """Test job lock is released in finally."""
    
    def test_lock_released_on_exception(self):
        """Verify lock is released even on exception."""
        from app.locking.job_lock import acquire_job_lock, release_job_lock
        
        uid = 99999
        rid = "test_rid"
        
        acquired, _ = acquire_job_lock(uid, rid, "test_model")
        assert acquired is True
        
        # Simulate exception in finally block
        exception_raised = False
        try:
            raise ValueError("Test exception")
        except ValueError:
            exception_raised = True
        finally:
            release_job_lock(uid, rid)
        
        assert exception_raised
        
        # Should be able to acquire again
        acquired2, _ = acquire_job_lock(uid, rid, "test_model")
        assert acquired2 is True
