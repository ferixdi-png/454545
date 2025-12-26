"""
Tests for generation events fix (db_service injection).
Ensures log_generation_event is called correctly and doesn't crash.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.payments.integration import generate_with_payment
from app.database.generation_events import log_generation_event


@pytest.mark.asyncio
async def test_log_generation_event_uses_fetchval():
    """Test that log_generation_event uses fetchval for RETURNING id."""
    # Mock db_service with fetchval
    mock_db = MagicMock()
    mock_db.fetchval = AsyncMock(return_value=123)
    
    # Call log_generation_event
    event_id = await log_generation_event(
        mock_db,
        user_id=1,
        model_id='test-model',
        status='started',
        is_free_applied=False,
        price_rub=10.0
    )
    
    # Verify fetchval was called
    assert mock_db.fetchval.called
    assert event_id == 123
    
    # Verify SQL contains RETURNING id
    call_args = mock_db.fetchval.call_args
    sql = call_args[0][0]
    assert 'RETURNING id' in sql
    assert 'INSERT INTO generation_events' in sql


@pytest.mark.asyncio
async def test_generate_with_payment_free_no_db_service():
    """Test FREE model generation without db_service doesn't crash."""
    # Mock ChargeManager without db_service
    mock_cm = MagicMock()
    mock_cm.db_service = None
    mock_cm.get_user_balance = AsyncMock(return_value=100.0)
    mock_cm.add_to_history = MagicMock()
    
    # Mock KieGenerator
    mock_gen_result = {
        'success': True,
        'result_urls': ['https://example.com/result.jpg'],
        'task_id': 'task-123'
    }
    
    with patch('app.payments.integration.get_charge_manager', return_value=mock_cm):
        with patch('app.payments.integration.is_free_model', return_value=True):
            with patch('app.payments.integration.KieGenerator') as MockGen:
                MockGen.return_value.generate = AsyncMock(return_value=mock_gen_result)
                
                # Call generate_with_payment
                result = await generate_with_payment(
                    model_id='z-image',
                    user_inputs={'prompt': 'test'},
                    user_id=1,
                    amount=0.0,
                    charge_manager=mock_cm
                )
    
    # Verify it succeeded without crashing
    assert result['success'] is True
    assert result['payment_status'] == 'free_tier'
    assert 'FREE модель' in result['payment_message']


@pytest.mark.asyncio
async def test_generate_with_payment_calls_log_with_db_service():
    """Test that generate_with_payment calls log_generation_event with db_service when available."""
    # Mock ChargeManager WITH db_service
    mock_db = MagicMock()
    mock_db.fetchval = AsyncMock(return_value=456)
    
    mock_cm = MagicMock()
    mock_cm.db_service = mock_db
    mock_cm.get_user_balance = AsyncMock(return_value=100.0)
    mock_cm.add_to_history = MagicMock()
    
    # Mock KieGenerator
    mock_gen_result = {
        'success': True,
        'result_urls': ['https://example.com/result.jpg'],
        'task_id': 'task-456'
    }
    
    with patch('app.payments.integration.get_charge_manager', return_value=mock_cm):
        with patch('app.payments.integration.is_free_model', return_value=True):
            with patch('app.payments.integration.KieGenerator') as MockGen:
                MockGen.return_value.generate = AsyncMock(return_value=mock_gen_result)
                with patch('app.payments.integration.log_generation_event', new_callable=AsyncMock) as mock_log:
                    
                    # Call generate_with_payment
                    result = await generate_with_payment(
                        model_id='z-image',
                        user_inputs={'prompt': 'test'},
                        user_id=1,
                        amount=0.0,
                        charge_manager=mock_cm
                    )
    
    # Verify log_generation_event was called with db_service as first arg
    assert mock_log.called
    assert mock_log.call_count >= 2  # start + complete
    
    # Check first call has db_service
    first_call = mock_log.call_args_list[0]
    assert first_call[0][0] == mock_db  # First positional arg is db_service


@pytest.mark.asyncio
async def test_generate_with_payment_paid_model_with_db():
    """Test paid model generation with db_service."""
    # Mock ChargeManager WITH db_service
    mock_db = MagicMock()
    mock_db.fetchval = AsyncMock(return_value=789)
    
    mock_cm = MagicMock()
    mock_cm.db_service = mock_db
    mock_cm.get_user_balance = AsyncMock(return_value=100.0)
    mock_cm.add_to_history = MagicMock()
    mock_cm.create_pending_charge = AsyncMock(return_value={'status': 'pending', 'message': 'OK'})
    mock_cm.commit_charge = AsyncMock(return_value={'status': 'committed', 'message': 'Charged'})
    
    # Mock KieGenerator
    mock_gen_result = {
        'success': True,
        'result_urls': ['https://example.com/paid-result.jpg'],
        'task_id': 'task-paid-789'
    }
    
    with patch('app.payments.integration.get_charge_manager', return_value=mock_cm):
        with patch('app.payments.integration.is_free_model', return_value=False):
            with patch('app.payments.integration.KieGenerator') as MockGen:
                MockGen.return_value.generate = AsyncMock(return_value=mock_gen_result)
                with patch('app.payments.integration.log_generation_event', new_callable=AsyncMock) as mock_log:
                    with patch('app.payments.integration.track_generation', new_callable=AsyncMock):
                        
                        # Call generate_with_payment
                        result = await generate_with_payment(
                            model_id='flux-pro',
                            user_inputs={'prompt': 'premium test'},
                            user_id=1,
                            amount=25.0,
                            charge_manager=mock_cm
                        )
    
    # Verify success
    assert result['success'] is True
    
    # Verify log_generation_event was called with db_service
    assert mock_log.called
    assert mock_log.call_count >= 2
    
    # Check all calls have db_service as first arg
    for call in mock_log.call_args_list:
        assert call[0][0] == mock_db


@pytest.mark.asyncio
async def test_log_generation_event_without_db_returns_none():
    """Test log_generation_event handles missing db_service gracefully."""
    # When db_service is None, function should not crash
    # (This is actually prevented by the caller now, but test defensive code)
    
    # Mock db_service that raises on fetchval
    mock_db = MagicMock()
    mock_db.fetchval = AsyncMock(side_effect=Exception("DB error"))
    
    # Call should handle exception and return None
    event_id = await log_generation_event(
        mock_db,
        user_id=1,
        model_id='test-model',
        status='started',
        is_free_applied=False,
        price_rub=10.0
    )
    
    # Should return None on error
    assert event_id is None
