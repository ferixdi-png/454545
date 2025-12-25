"""
OCR/Tesseract processor with UX improvements:
- Non-blocking processing
- Confidence checking with retry requests
- No silent failures
"""
import logging
import asyncio
from typing import Dict, Any, Optional, Tuple
from io import BytesIO
import base64

logger = logging.getLogger(__name__)

# Try to import tesseract
try:
    import pytesseract
    from PIL import Image
    HAS_TESSERACT = True
except ImportError:
    pytesseract = None
    Image = None
    HAS_TESSERACT = False
    logger.warning("pytesseract or PIL not available, OCR will be disabled")


class OCRProcessor:
    """OCR processor with confidence checking and UX improvements."""
    
    def __init__(self, min_confidence: float = 0.7):
        """
        Initialize OCR processor.
        
        Args:
            min_confidence: Minimum confidence threshold (0.0-1.0)
        """
        self.min_confidence = min_confidence
        self._executor = None
    
    async def process_screenshot(
        self,
        image_data: bytes,
        user_id: int,
        expected_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process screenshot asynchronously (non-blocking).
        
        Args:
            image_data: Image bytes
            user_id: User identifier
            expected_text: Optional expected text to validate against
            
        Returns:
            Result dict with:
            - success: bool
            - text: Extracted text
            - confidence: Confidence score (0.0-1.0)
            - message: User-friendly message
            - needs_retry: bool (if confidence is low)
            - retry_hint: str (what should be visible)
        """
        if not HAS_TESSERACT and pytesseract is None:
            return {
                'success': False,
                'text': '',
                'confidence': 0.0,
                'message': 'OCR недоступен (модуль не установлен). Пожалуйста, повторите попытку с более четким скриншотом.',
                'needs_retry': True,
                'retry_hint': 'Скриншот должен быть четким и содержать читаемый текст'
            }
        
        try:
            # Run OCR in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._process_image_sync,
                image_data,
                expected_text
            )
            
            confidence = result['confidence']
            text = result['text']
            
            # Check confidence
            if confidence < self.min_confidence:
                retry_hint = self._generate_retry_hint(expected_text, text)
                return {
                    'success': False,
                    'text': text,
                    'confidence': confidence,
                    'message': f'Распознавание неуверенно (уверенность: {confidence:.0%}). Пожалуйста, отправьте скриншот еще раз.',
                    'needs_retry': True,
                    'retry_hint': retry_hint
                }
            
            # Success
            return {
                'success': True,
                'text': text,
                'confidence': confidence,
                'message': 'Скриншот успешно распознан',
                'needs_retry': False,
                'retry_hint': ''
            }
        
        except Exception as e:
            logger.error(f"OCR processing error: {e}", exc_info=True)
            return {
                'success': False,
                'text': '',
                'confidence': 0.0,
                'message': f'Ошибка при распознавании: {str(e)}. Пожалуйста, попробуйте еще раз.',
                'needs_retry': True,
                'retry_hint': 'Убедитесь, что скриншот четкий и содержит текст'
            }
    
    def _process_image_sync(
        self,
        image_data: bytes,
        expected_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """Synchronous image processing (runs in executor)."""
        try:
            # Load image
            if Image is None:
                image = image_data
            else:
                image = Image.open(BytesIO(image_data))
            
            # Run OCR
            ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, lang='rus+eng')
            
            # Extract text and calculate confidence
            text_parts = []
            confidences = []
            
            for i, word in enumerate(ocr_data.get('text', [])):
                if word.strip():
                    text_parts.append(word)
                    conf = float(ocr_data.get('conf', [0])[i] or 0) / 100.0
                    confidences.append(conf)
            
            text = ' '.join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            # Validate against expected text if provided
            if expected_text:
                # Simple validation (can be improved)
                expected_lower = expected_text.lower().strip()
                text_lower = text.lower().strip()
                if expected_lower not in text_lower and text_lower not in expected_lower:
                    # Text doesn't match expected
                    avg_confidence = min(avg_confidence, 0.5)  # Lower confidence
            
            return {
                'text': text,
                'confidence': avg_confidence,
                'raw_data': ocr_data
            }
        
        except Exception as e:
            logger.error(f"Sync OCR processing error: {e}", exc_info=True)
            raise
    
    def _generate_retry_hint(self, expected_text: Optional[str], extracted_text: str) -> str:
        """Generate helpful hint for retry."""
        hints = []
        
        if expected_text:
            hints.append(f"Убедитесь, что на скриншоте видно: '{expected_text}'")
        
        if not extracted_text or len(extracted_text.strip()) < 5:
            hints.append("Текст должен быть четко виден и читаем")
        
        hints.append("Скриншот должен быть в хорошем качестве, без размытия")
        hints.append("Убедитесь, что весь необходимый текст попадает в кадр")
        
        return ". ".join(hints) if hints else "Пожалуйста, отправьте более четкий скриншот"
    
    async def validate_payment_screenshot(
        self,
        image_data: bytes,
        required_elements: list = None
    ) -> Dict[str, Any]:
        """
        Validate payment screenshot for required elements.
        
        Args:
            image_data: Image bytes
            required_elements: List of required text elements (e.g., ['оплачено', 'success'])
            
        Returns:
            Validation result
        """
        if required_elements is None:
            required_elements = ['оплачено', 'успешно', 'success', 'paid']
        
        result = await self.process_screenshot(image_data, user_id=0)
        
        if not result['success']:
            return result
        
        text_lower = result['text'].lower()
        found_elements = [elem for elem in required_elements if elem.lower() in text_lower]
        
        if not found_elements:
            return {
                'success': False,
                'text': result['text'],
                'confidence': result['confidence'],
                'message': 'На скриншоте не найдены признаки успешной оплаты. Пожалуйста, отправьте скриншот еще раз.',
                'needs_retry': True,
                'retry_hint': f"Убедитесь, что на скриншоте видно одно из: {', '.join(required_elements)}"
            }
        
        return result


# Global instance
_ocr_processor: Optional[OCRProcessor] = None


def get_ocr_processor(min_confidence: float = 0.7) -> OCRProcessor:
    """Get or create global OCR processor instance."""
    global _ocr_processor
    if _ocr_processor is None:
        _ocr_processor = OCRProcessor(min_confidence)
    return _ocr_processor
