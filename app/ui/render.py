"""UI rendering functions - unified style for all screens."""
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


def render_welcome(first_name: str, total_models: int, free_count: int) -> str:
    """
    Render welcome screen.
    
    Args:
        first_name: User's first name
        total_models: Total number of models
        free_count: Number of free models
    
    Returns:
        Formatted welcome message
    """
    return (
        f"👋 <b>{first_name}</b>, добро пожаловать в <b>AI Studio</b>!\n\n"
        f"🚀 <b>{total_models} премиальных нейросетей</b> для креативных задач\n\n"
        f"<b>Создавайте за минуты:</b>\n"
        f"• Креативы для соцсетей\n"
        f"• Видео для Reels, TikTok, YouTube\n"
        f"• Изображения для рекламы\n"
        f"• Тексты, озвучку, музыку\n\n"
        f"🎁 <b>{free_count} моделей бесплатно</b>\n\n"
        f"👇 Выберите формат:"
    )


def render_menu() -> str:
    """Render main menu text."""
    return (
        "🏠 <b>Главное меню</b>\n\n"
        "Выберите раздел:"
    )


def render_format_page(
    format_name: str,
    description: str,
    input_desc: str,
    output_desc: str,
    model_count: int
) -> str:
    """
    Render format page header.
    
    Args:
        format_name: Format display name (e.g., "Text → Image")
        description: Short description for marketers
        input_desc: What user needs to provide
        output_desc: What they'll get
        model_count: Number of models in this format
    
    Returns:
        Formatted message
    """
    return (
        f"🎨 <b>{format_name}</b>\n\n"
        f"{description}\n\n"
        f"<b>Что нужно:</b> {input_desc}\n"
        f"<b>Что получите:</b> {output_desc}\n\n"
        f"📊 Доступно моделей: <b>{model_count}</b>\n\n"
        f"👇 Выберите модель:"
    )


def render_model_card(model_config: Dict[str, Any], show_advanced: bool = False) -> str:
    """
    Render model card (consistent format everywhere).
    
    Args:
        model_config: Model configuration from KIE_SOURCE_OF_TRUTH
        show_advanced: Whether to show advanced details
    
    Returns:
        Formatted model card
    """
    display_name = model_config.get("display_name", "Модель")
    description = model_config.get("description", "Нейросеть")
    category = model_config.get("category", "")
    output_type = model_config.get("output_type", "")
    
    pricing = model_config.get("pricing", {})
    price_rub = pricing.get("rub_per_use", 0)
    is_free = pricing.get("is_free", False)
    
    # Format emojis
    category_emoji = _get_category_emoji(category)
    output_emoji = _get_output_emoji(output_type)
    
    text = (
        f"{category_emoji} <b>{display_name}</b>\n\n"
        f"<b>Коротко:</b> {description}\n\n"
    )
    
    # Marketing benefits
    benefits = _get_marketing_benefits(category, output_type)
    if benefits:
        text += "<b>Подходит для:</b>\n"
        for benefit in benefits[:3]:
            text += f"• {benefit}\n"
        text += "\n"
    
    # Input/Output
    input_desc = _get_input_description(category, model_config)
    text += f"<b>Вход:</b> {input_desc}\n"
    text += f"<b>Выход:</b> {output_emoji} {output_type or 'результат'}\n\n"
    
    # Price
    if is_free:
        text += "🆓 <b>БЕСПЛАТНО</b>\n\n"
    else:
        text += f"💰 <b>Цена:</b> {price_rub:.2f} ₽\n\n"
    
    # Tips (short version by default)
    if not show_advanced:
        text += "<b>Совет:</b> Опишите детально, что хотите увидеть\n"
    else:
        # Advanced tips
        tips = _get_model_tips(category)
        if tips:
            text += "<b>Как сделать хорошо:</b>\n"
            for tip in tips[:3]:
                text += f"• {tip}\n"
            text += "\n"
        
        # Common mistakes
        mistakes = _get_common_mistakes(category)
        if mistakes:
            text += "<b>Частые ошибки:</b>\n"
            for mistake in mistakes[:2]:
                text += f"• {mistake}\n"
    
    return text


def render_wizard_step(
    model_name: str,
    field_name: str,
    field_desc: str,
    is_required: bool,
    example: Optional[str] = None
) -> str:
    """
    Render wizard step.
    
    Args:
        model_name: Model display name
        field_name: Field name
        field_desc: Field description
        is_required: Whether field is required
        example: Example value
    
    Returns:
        Formatted message
    """
    text = (
        f"🧙 <b>Создание: {model_name}</b>\n\n"
        f"📝 <b>{field_desc}</b>\n\n"
    )
    
    if is_required:
        text += "⚠️ <i>Обязательное поле</i>\n\n"
    else:
        text += "💡 <i>Необязательное (можете пропустить)</i>\n\n"
    
    if example:
        text += f"<b>Пример:</b> {example}\n\n"
    
    text += "👇 Введите значение:"
    
    return text


def render_confirm(model_name: str, inputs: Dict[str, Any], price_rub: float, is_free: bool) -> str:
    """
    Render confirmation screen.
    
    Args:
        model_name: Model display name
        inputs: Dictionary of input values
        price_rub: Price in rubles
        is_free: Whether it's free
    
    Returns:
        Formatted message
    """
    text = (
        f"✅ <b>Подтверждение запуска</b>\n\n"
        f"🎯 <b>Модель:</b> {model_name}\n\n"
        f"<b>Параметры:</b>\n"
    )
    
    for field_name, value in inputs.items():
        # Truncate long values
        value_str = str(value)
        if len(value_str) > 100:
            value_str = value_str[:97] + "..."
        text += f"• {field_name}: {value_str}\n"
    
    text += "\n"
    
    if is_free:
        text += "🆓 <b>Бесплатно</b>\n\n"
    else:
        text += f"💰 <b>Стоимость:</b> {price_rub:.2f} ₽\n\n"
    
    text += "🚀 Всё готово к запуску!"
    
    return text


def render_success(model_name: str, result_url: Optional[str] = None) -> str:
    """
    Render success screen.
    
    Args:
        model_name: Model display name
        result_url: URL to result (if available)
    
    Returns:
        Formatted message
    """
    text = (
        f"✅ <b>Готово!</b>\n\n"
        f"🎨 Модель: {model_name}\n\n"
    )
    
    if result_url:
        text += "📎 Результат готов и будет отправлен следующим сообщением\n\n"
    else:
        text += "⏳ Генерация завершена\n\n"
    
    text += "🔁 Хотите создать ещё?"
    
    return text


def render_error(model_name: str, error_msg: str, is_retryable: bool = True) -> str:
    """
    Render error screen.
    
    Args:
        model_name: Model display name
        error_msg: Error message (sanitized)
        is_retryable: Whether user can retry
    
    Returns:
        Formatted message
    """
    text = (
        f"❌ <b>Ошибка генерации</b>\n\n"
        f"🎨 Модель: {model_name}\n\n"
        f"<b>Что произошло:</b>\n{error_msg}\n\n"
    )
    
    if is_retryable:
        text += "💡 Попробуйте изменить параметры и запустить снова"
    else:
        text += "💡 Свяжитесь с поддержкой, если проблема повторяется"
    
    return text


# Helper functions

def _get_category_emoji(category: str) -> str:
    """Get emoji for category."""
    category_lower = category.lower()
    
    if "video" in category_lower:
        return "🎬"
    if "image" in category_lower:
        return "🖼"
    if "audio" in category_lower or "voice" in category_lower:
        return "🎙"
    if "music" in category_lower:
        return "🎵"
    if "text" in category_lower:
        return "✍️"
    
    return "🎨"


def _get_output_emoji(output_type: str) -> str:
    """Get emoji for output type."""
    output_lower = output_type.lower()
    
    if "video" in output_lower:
        return "🎬"
    if "image" in output_lower:
        return "🖼"
    if "audio" in output_lower:
        return "🎙"
    if "text" in output_lower:
        return "📝"
    
    return "✨"


def _get_marketing_benefits(category: str, output_type: str) -> List[str]:
    """Get marketing benefits for category."""
    category_lower = category.lower()
    
    if "text-to-image" in category_lower:
        return [
            "Баннеры для рекламы",
            "Обложки для постов",
            "Креативы для таргета",
        ]
    
    if "image-to-image" in category_lower:
        return [
            "Улучшение фото",
            "Удаление фона",
            "Ретушь изображений",
        ]
    
    if "video" in category_lower or "video" in output_type.lower():
        return [
            "Reels для Instagram",
            "Shorts для YouTube",
            "Видео для TikTok",
        ]
    
    if "audio" in category_lower or "voice" in category_lower:
        return [
            "Озвучка видео",
            "Аудио для рекламы",
            "Голосовые сообщения",
        ]
    
    return ["Креативный контент", "Маркетинговые материалы", "SMM и реклама"]


def _get_input_description(category: str, model_config: Dict[str, Any]) -> str:
    """Get input description."""
    category_lower = category.lower()
    
    if "text-to-" in category_lower:
        return "✍️ текстовое описание"
    
    if "image-to-" in category_lower:
        return "🖼 изображение"
    
    if "audio-to-" in category_lower:
        return "🎙 аудио"
    
    if "video-to-" in category_lower:
        return "🎬 видео"
    
    # Try to infer from schema
    schema = model_config.get("input_schema", {})
    required = schema.get("required", [])
    
    if "prompt" in required or "text" in required:
        return "✍️ текст"
    if "image_url" in required or "image" in required:
        return "🖼 изображение"
    if "audio_url" in required or "audio" in required:
        return "🎙 аудио"
    
    return "данные"


def _get_model_tips(category: str) -> List[str]:
    """Get tips for using model."""
    category_lower = category.lower()
    
    if "image" in category_lower or "video" in category_lower:
        return [
            "Опишите детали: цвета, стиль, настроение",
            "Укажите композицию и ракурс",
            "Добавьте конкретику: время суток, освещение",
        ]
    
    if "audio" in category_lower or "voice" in category_lower:
        return [
            "Пишите текст естественно, как говорите",
            "Используйте короткие предложения",
            "Избегайте сложных терминов",
        ]
    
    return [
        "Будьте конкретны в описании",
        "Используйте простой язык",
        "Проверьте параметры перед запуском",
    ]


def _get_common_mistakes(category: str) -> List[str]:
    """Get common mistakes."""
    category_lower = category.lower()
    
    if "image" in category_lower or "video" in category_lower:
        return [
            "Слишком общее описание",
            "Противоречивые требования",
        ]
    
    return [
        "Пустые обязательные поля",
        "Слишком длинный запрос",
    ]
