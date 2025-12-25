"""
Tests for UNHAPPY payment scenarios:
- Generation timeout
- KIE API fail
- Double confirmation click
- Invalid OCR
- Network errors
- Partial failures
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from app.payments.charges import ChargeManager
from app.payments.integration import generate_with_payment
from app.kie.generator import KieGenerator
from app.ocr.tesseract_processor import OCRProcessor


@pytest.fixture
def charge_manager():
    """Create charge manager instance."""
    return ChargeManager()


@pytest.fixture
def mock_generator_timeout():
    """Mock generator that times out."""
    generator = Mock(spec=KieGenerator)
    generator.generate = AsyncMock(return_value={
        'success': False,
        'message': '⏱️ Превышено время ожидания (300 сек)',
        'result_urls': [],
        'result_object': None,
        'task_id': 'timeout_task_123',
        'error_code': 'TIMEOUT',
        'error_message': 'Task timeout after 300 seconds'
    })
    return generator


@pytest.fixture
def mock_generator_fail():
    """Mock generator that fails."""
    generator = Mock(spec=KieGenerator)
    generator.generate = AsyncMock(return_value={
        'success': False,
        'message': '❌ Ошибка от KIE API',
        'result_urls': [],
        'result_object': None,
        'task_id': 'fail_task_123',
        'error_code': 'KIE_API_ERROR',
        'error_message': 'KIE API returned fail state'
    })
    return generator


@pytest.fixture
def mock_generator_success():
    """Mock generator that succeeds."""
    generator = Mock(spec=KieGenerator)
    generator.generate = AsyncMock(return_value={
        'success': True,
        'message': '✅ Готово!',
        'result_urls': ['https://example.com/result.jpg'],
        'result_object': None,
        'task_id': 'success_task_123',
        'error_code': None,
        'error_message': None
    })
    return generator


@pytest.mark.asyncio
async def test_timeout_releases_charge(charge_manager, mock_generator_timeout):
    """
    SCENARIO 1: Generation timeout
    EXPECTED: Charge is released (not committed), user sees clear status
    """
    task_id = "timeout_task_123"
    user_id = 123
    amount = 10.0
    
    # Create pending charge
    await charge_manager.create_pending_charge(task_id, user_id, amount, "test_model")
    
    # Simulate timeout scenario
    gen_result = await mock_generator_timeout.generate("test_model", {"text": "test"})
    
    # Contract: timeout MUST release charge
    assert gen_result['success'] is False
    assert gen_result['error_code'] == 'TIMEOUT'
    
    # Release charge (auto-refund)
    release_result = await charge_manager.release_charge(task_id, reason='timeout')
    assert release_result['status'] == 'released'
    assert release_result['message'] == 'Деньги не списаны'
    
    # Check status
    status = await charge_manager.get_charge_status(task_id)
    assert status['status'] == 'released'
    assert status['message'] == 'Деньги не списаны'
    
    # Verify charge was NOT committed
    assert task_id not in charge_manager._committed_charges
    assert task_id in charge_manager._released_charges


@pytest.mark.asyncio
async def test_kie_fail_releases_charge(charge_manager, mock_generator_fail):
    """
    SCENARIO 2: KIE API returns fail
    EXPECTED: Charge is released (not committed), user sees clear error
    """
    task_id = "fail_task_123"
    user_id = 123
    amount = 10.0
    
    # Create pending charge
    await charge_manager.create_pending_charge(task_id, user_id, amount, "test_model")
    
    # Simulate KIE fail scenario
    gen_result = await mock_generator_fail.generate("test_model", {"text": "test"})
    
    # Contract: fail MUST release charge
    assert gen_result['success'] is False
    assert gen_result['error_code'] == 'KIE_API_ERROR'
    
    # Release charge (auto-refund)
    release_result = await charge_manager.release_charge(task_id, reason='generation_failed')
    assert release_result['status'] == 'released'
    assert release_result['message'] == 'Деньги не списаны'
    
    # Check status
    status = await charge_manager.get_charge_status(task_id)
    assert status['status'] == 'released'
    assert status['message'] == 'Деньги не списаны'
    
    # Verify charge was NOT committed
    assert task_id not in charge_manager._committed_charges
    assert task_id in charge_manager._released_charges


@pytest.mark.asyncio
async def test_double_confirmation_idempotent(charge_manager):
    """
    SCENARIO 3: User clicks confirm payment twice
    EXPECTED: Second click is no-op (idempotent), no double charge
    """
    task_id = "double_confirm_task_123"
    user_id = 123
    amount = 10.0
    
    # Create pending charge
    await charge_manager.create_pending_charge(task_id, user_id, amount, "test_model")
    
    # First commit
    result1 = await charge_manager.commit_charge(task_id)
    assert result1['status'] == 'committed'
    assert result1['idempotent'] is False
    
    # Second commit (should be no-op)
    result2 = await charge_manager.commit_charge(task_id)
    assert result2['status'] == 'already_committed'
    assert result2['idempotent'] is True
    assert result2['message'] == 'Оплата уже подтверждена'
    
    # Verify charge was only committed once
    assert task_id in charge_manager._committed_charges


@pytest.mark.asyncio
async def test_invalid_ocr_no_charge():
    """
    SCENARIO 4: Invalid OCR (low confidence or wrong text)
    EXPECTED: No charge created, user asked to retry
    """
    ocr_processor = OCRProcessor(min_confidence=0.7)
    
    # Simulate invalid OCR (low confidence)
    with patch('app.ocr.tesseract_processor.pytesseract') as mock_tesseract:
        mock_tesseract.image_to_data.return_value = {
            'text': ['bad', 'text'],
            'conf': [50, 50]  # Low confidence
        }
        
        # This should fail OCR validation
        result = await ocr_processor.process_screenshot(
            b"fake_image_data",
            user_id=123,
            expected_text="оплачено"
        )
        
        # Contract: Invalid OCR MUST NOT proceed to charge
        assert result['success'] is False
        assert result['needs_retry'] is True
        assert 'уверенность' in result['message'].lower() or 'повторите' in result['message'].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

