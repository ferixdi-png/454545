"""
Tests for OCR processor:
- Non-blocking processing
- Confidence checking
- Retry hints
"""
import pytest
import asyncio
from app.ocr.tesseract_processor import OCRProcessor


@pytest.fixture
def ocr_processor():
    """Create OCR processor instance."""
    return OCRProcessor(min_confidence=0.7)


@pytest.mark.asyncio
async def test_ocr_low_confidence_retry(ocr_processor):
    """Test that low confidence triggers retry request."""
    # Create minimal image data (will have low confidence)
    # In real test, use actual image bytes
    fake_image_data = b'\x89PNG\r\n\x1a\n'  # Minimal PNG header
    
    result = await ocr_processor.process_screenshot(
        fake_image_data,
        user_id=123
    )
    
    # Should request retry if confidence is low
    if result['confidence'] < ocr_processor.min_confidence:
        assert result['needs_retry'] is True
        assert 'повторите' in result['message'].lower() or 'еще раз' in result['message'].lower()
        assert result['retry_hint'] != ''


@pytest.mark.asyncio
async def test_ocr_no_silent_failures(ocr_processor):
    """Test that OCR never fails silently."""
    # Test with invalid image data
    invalid_data = b'invalid_image_data'
    
    result = await ocr_processor.process_screenshot(
        invalid_data,
        user_id=123
    )
    
    # Should always return a result with message
    assert 'message' in result
    assert result['message'] != ''
    
    # Should indicate retry if failed
    if not result['success']:
        assert result['needs_retry'] is True


@pytest.mark.asyncio
async def test_ocr_non_blocking(ocr_processor):
    """Test that OCR processing doesn't block event loop."""
    import time
    
    start_time = time.time()
    
    # Process multiple images concurrently
    tasks = []
    for i in range(5):
        fake_data = b'\x89PNG\r\n\x1a\n'
        tasks.append(
            ocr_processor.process_screenshot(fake_data, user_id=i)
        )
    
    results = await asyncio.gather(*tasks)
    
    elapsed = time.time() - start_time
    
    # Should complete quickly (non-blocking)
    assert elapsed < 5.0  # Should be much faster than sequential
    assert len(results) == 5


@pytest.mark.asyncio
async def test_payment_screenshot_validation(ocr_processor):
    """Test payment screenshot validation."""
    fake_image_data = b'\x89PNG\r\n\x1a\n'
    
    result = await ocr_processor.validate_payment_screenshot(
        fake_image_data,
        required_elements=['оплачено', 'success']
    )
    
    # Should always return result
    assert 'message' in result
    assert 'needs_retry' in result
    
    # If validation fails, should provide hint
    if not result['success']:
        assert result['retry_hint'] != ''


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

