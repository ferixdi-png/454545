"""Marketing templates for quick generation."""
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Template:
    """Marketing template."""
    id: str
    name: str
    description: str
    format_key: str
    questions: List[Dict[str, Any]]  # List of questions to ask
    build_prompt: callable  # Function to build prompt from answers


# Template definitions

def _build_banner_prompt(answers: Dict[str, str]) -> str:
    """Build prompt for banner template."""
    product = answers.get("product", "продукт")
    style = answers.get("style", "современный")
    colors = answers.get("colors", "яркие")
    
    return (
        f"Рекламный баннер для {product}, {style} стиль, {colors} цвета, "
        f"высокое качество, профессиональный дизайн"
    )


def _build_social_post_prompt(answers: Dict[str, str]) -> str:
    """Build prompt for social post template."""
    topic = answers.get("topic", "акция")
    mood = answers.get("mood", "позитивное")
    
    return (
        f"Изображение для поста в соцсетях на тему: {topic}, "
        f"{mood} настроение, привлекательное, яркое"
    )


def _build_reels_prompt(answers: Dict[str, str]) -> str:
    """Build prompt for Reels template."""
    content = answers.get("content", "продукт")
    duration = answers.get("duration", "5")
    
    return (
        f"Динамичное видео для Reels: {content}, "
        f"длительность {duration} секунд, вертикальная ориентация, тренды Instagram"
    )


def _build_youtube_short_prompt(answers: Dict[str, str]) -> str:
    """Build prompt for YouTube Short template."""
    topic = answers.get("topic", "обзор")
    
    return (
        f"YouTube Short: {topic}, динамичный монтаж, вертикальное видео, "
        f"захватывающее с первой секунды"
    )


def _build_product_demo_prompt(answers: Dict[str, str]) -> str:
    """Build prompt for product demo template."""
    product = answers.get("product", "товар")
    features = answers.get("features", "основные преимущества")
    
    return (
        f"Демонстрация продукта: {product}, показать {features}, "
        f"профессиональная съёмка, крупный план"
    )


def _build_ugc_prompt(answers: Dict[str, str]) -> str:
    """Build prompt for UGC template."""
    scenario = answers.get("scenario", "использование продукта")
    
    return (
        f"UGC-контент: {scenario}, естественная съёмка, реалистичное видео, "
        f"как снял обычный пользователь"
    )


def _build_voiceover_prompt(answers: Dict[str, str]) -> str:
    """Build prompt for voiceover template."""
    text = answers.get("text", "Привет")
    voice = answers.get("voice", "дружелюбный")
    
    return text  # For TTS, the prompt IS the text


# Template library

TEMPLATES: Dict[str, List[Template]] = {
    "text-to-image": [
        Template(
            id="banner",
            name="🎯 Рекламный баннер",
            description="Баннер для таргетированной рекламы",
            format_key="text-to-image",
            questions=[
                {"key": "product", "text": "Что рекламируем?", "example": "новая коллекция одежды"},
                {"key": "style", "text": "Стиль?", "example": "минимализм, современный, винтаж"},
                {"key": "colors", "text": "Цветовая гамма?", "example": "синий и белый"},
            ],
            build_prompt=_build_banner_prompt,
        ),
        Template(
            id="social_post",
            name="📱 Пост для соцсетей",
            description="Картинка для Instagram/VK/Facebook",
            format_key="text-to-image",
            questions=[
                {"key": "topic", "text": "Тема поста?", "example": "летняя распродажа"},
                {"key": "mood", "text": "Настроение?", "example": "радостное, энергичное"},
            ],
            build_prompt=_build_social_post_prompt,
        ),
        Template(
            id="story_cover",
            name="📖 Обложка для Stories",
            description="Обложка для Instagram/VK Stories",
            format_key="text-to-image",
            questions=[
                {"key": "topic", "text": "О чём Stories?", "example": "за кулисами"},
                {"key": "style", "text": "Стиль?", "example": "яркий, контрастный"},
            ],
            build_prompt=_build_social_post_prompt,
        ),
    ],
    "text-to-video": [
        Template(
            id="reels",
            name="📱 Reels для Instagram",
            description="Вертикальное видео для Reels",
            format_key="text-to-video",
            questions=[
                {"key": "content", "text": "Что показываем?", "example": "использование продукта"},
                {"key": "duration", "text": "Длительность (сек)?", "example": "5"},
            ],
            build_prompt=_build_reels_prompt,
        ),
        Template(
            id="youtube_short",
            name="🎬 YouTube Short",
            description="Короткое вертикальное видео",
            format_key="text-to-video",
            questions=[
                {"key": "topic", "text": "Тема видео?", "example": "лайфхак дня"},
            ],
            build_prompt=_build_youtube_short_prompt,
        ),
    ],
    "image-to-video": [
        Template(
            id="product_demo",
            name="🛍 Демонстрация товара",
            description="Оживить фото товара",
            format_key="image-to-video",
            questions=[
                {"key": "product", "text": "Что за товар?", "example": "наушники"},
                {"key": "features", "text": "Что показать?", "example": "поворот на 360 градусов"},
            ],
            build_prompt=_build_product_demo_prompt,
        ),
        Template(
            id="ugc_video",
            name="📹 UGC-видео",
            description="Видео 'от пользователя'",
            format_key="image-to-video",
            questions=[
                {"key": "scenario", "text": "Сценарий?", "example": "распаковка товара"},
            ],
            build_prompt=_build_ugc_prompt,
        ),
    ],
    "text-to-audio": [
        Template(
            id="voiceover",
            name="🎙 Озвучка текста",
            description="Голосовое сопровождение",
            format_key="text-to-audio",
            questions=[
                {"key": "text", "text": "Текст для озвучки?", "example": "Добро пожаловать!"},
                {"key": "voice", "text": "Характер голоса?", "example": "дружелюбный, энергичный"},
            ],
            build_prompt=_build_voiceover_prompt,
        ),
    ],
}


def get_templates_for_format(format_key: str) -> List[Template]:
    """
    Get templates for a format.
    
    Args:
        format_key: Format key (e.g., "text-to-image")
    
    Returns:
        List of Template objects
    """
    return TEMPLATES.get(format_key, [])


def get_template(template_id: str, format_key: str) -> Optional[Template]:
    """
    Get specific template.
    
    Args:
        template_id: Template ID
        format_key: Format key
    
    Returns:
        Template object or None
    """
    templates = TEMPLATES.get(format_key, [])
    for template in templates:
        if template.id == template_id:
            return template
    return None


def build_payload_from_template(
    template: Template,
    answers: Dict[str, str],
    model_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build generation payload from template answers.
    
    Args:
        template: Template object
        answers: Dictionary of answers to template questions
        model_config: Model configuration
    
    Returns:
        Payload dict ready for generation
    """
    # Build prompt
    prompt = template.build_prompt(answers)
    
    # Start with basic payload
    payload = {"prompt": prompt}
    
    # Add defaults from model schema
    schema = model_config.get("input_schema", {})
    properties = schema.get("properties", {})
    
    for field_name, field_spec in properties.items():
        if field_name == "prompt":
            continue  # Already set
        
        # Add default values
        if "default" in field_spec:
            payload[field_name] = field_spec["default"]
    
    return payload
