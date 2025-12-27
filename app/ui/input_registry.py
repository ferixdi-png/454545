"""
Input validation registry - strict enforcement per model/format.

Prevents "required field missing" API errors by validating BEFORE generation.
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from app.ui.input_spec import InputSpec, InputField, InputType, get_input_spec
from app.ui.formats import FORMATS

logger = logging.getLogger(__name__)


class UserFacingValidationError(Exception):
    """User-friendly validation error (safe to show)."""
    pass


def validate_inputs(model_config: Dict[str, Any], inputs: Dict[str, Any]) -> None:
    """
    Strictly validate user inputs against model requirements.
    
    Args:
        model_config: Model configuration from SOURCE_OF_TRUTH
        inputs: User-provided inputs
    
    Raises:
        UserFacingValidationError: If validation fails (safe message)
    """
    spec = get_input_spec(model_config)
    
    if not spec or not spec.fields:
        # No validation needed
        return
    
    # Check all required fields
    missing_fields = []
    for field in spec.fields:
        if field.required:
            value = inputs.get(field.name)
            
            # Check if value is present and non-empty
            if value is None or (isinstance(value, str) and not value.strip()):
                missing_fields.append(field.description or field.name)
    
    if missing_fields:
        fields_str = ", ".join(missing_fields)
        raise UserFacingValidationError(
            f"❌ Не заполнены обязательные поля: {fields_str}"
        )
    
    # Type-specific validation
    for field in spec.fields:
        value = inputs.get(field.name)
        if value is None:
            continue
        
        # Number validation
        if field.type == InputType.NUMBER:
            try:
                num_val = float(value)
                
                if field.min_value is not None and num_val < field.min_value:
                    raise UserFacingValidationError(
                        f"❌ {field.description or field.name}: "
                        f"минимум {field.min_value}"
                    )
                
                if field.max_value is not None and num_val > field.max_value:
                    raise UserFacingValidationError(
                        f"❌ {field.description or field.name}: "
                        f"максимум {field.max_value}"
                    )
            except (ValueError, TypeError):
                raise UserFacingValidationError(
                    f"❌ {field.description or field.name}: "
                    f"должно быть числом"
                )
        
        # Enum validation
        if field.type == InputType.ENUM:
            if field.enum_values and value not in field.enum_values:
                valid_str = ", ".join(field.enum_values)
                raise UserFacingValidationError(
                    f"❌ {field.description or field.name}: "
                    f"выберите один из: {valid_str}"
                )
        
        # URL validation (basic)
        if field.type in [InputType.IMAGE_URL, InputType.VIDEO_URL, InputType.AUDIO_URL]:
            if not isinstance(value, str) or not value.startswith('http'):
                raise UserFacingValidationError(
                    f"❌ {field.description or field.name}: "
                    f"должен быть URL (http://...)"
                )


def get_format_requirements(format_key: str) -> str:
    """
    Get human-readable requirements for format.
    
    Args:
        format_key: Format identifier (e.g., 'text_to_image')
    
    Returns:
        Human-readable requirements string
    """
    format_obj = FORMATS.get(format_key)
    if not format_obj:
        return "Неизвестный формат"
    
    # Common requirements by format
    requirements = {
        'text_to_image': "Требуется: текстовое описание (prompt)",
        'image_to_image': "Требуется: исходное изображение + описание изменений",
        'text_to_video': "Требуется: текстовое описание видео",
        'image_to_video': "Требуется: исходное изображение",
        'video_to_video': "Требуется: исходное видео + описание изменений",
        'text_to_speech': "Требуется: текст для озвучки",
        'speech_to_text': "Требуется: аудиофайл или голосовое сообщение",
        'text_to_music': "Требуется: описание музыки (стиль, настроение)",
        'image_upscale': "Требуется: изображение для улучшения",
        'remove_background': "Требуется: изображение с объектом",
        'video_upscale': "Требуется: видео для улучшения качества",
    }
    
    return requirements.get(format_key, "Требуется: см. описание модели")


# Model-specific overrides (for complex cases)
MODEL_OVERRIDES = {
    'flux_schnell': {
        'required': ['prompt'],
        'hints': "Опишите что хотите увидеть на изображении",
    },
    'runway_gen3': {
        'required': ['prompt'],
        'hints': "Опишите сцену и действие для видео",
    },
    'elevenlabs_tts': {
        'required': ['text'],
        'hints': "Введите текст для озвучки (до 5000 символов)",
    },
    'rembg': {
        'required': ['image_url'],
        'hints': "Загрузите фото с объектом на фоне",
    },
}


def get_model_requirements(model_id: str) -> Optional[Dict[str, Any]]:
    """Get model-specific requirement overrides."""
    return MODEL_OVERRIDES.get(model_id)
