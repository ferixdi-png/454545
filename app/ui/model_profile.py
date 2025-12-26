"""
Model Profile - маркетинговые карточки моделей.

Создает "продающую" презентацию модели для UI.
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _get_output_format_label(model: Dict) -> str:
    """Определить формат результата для UI."""
    output_type = model.get("output_type", "unknown")
    category = model.get("category", "").lower()
    
    # Video formats
    if "video" in output_type or "video" in category:
        # Check for aspect ratio hints
        schema = model.get("input_schema", {})
        props = schema.get("properties", {})
        
        if "aspect_ratio" in props:
            return "Видео (9:16 Reels/TikTok)"
        return "Видео"
    
    # Image formats
    if "image" in output_type or "image" in category:
        return "Изображение"
    
    # Text
    if "text" in output_type or "text" in category:
        return "Текст"
    
    # Audio/Voice
    if "audio" in output_type or "audio" in category:
        return "Аудио/Озвучка"
    
    # Music
    if "music" in category:
        return "Музыка"
    
    return "Результат"


def _get_marketing_use_cases(model: Dict) -> List[str]:
    """
    Определить маркетинговые use cases для модели.
    
    Основано на category, tags, description из SOURCE_OF_TRUTH.
    """
    category = model.get("category", "").lower()
    tags = [t.lower() for t in model.get("tags", [])]
    model_id = model.get("model_id", "").lower()
    
    uses = []
    
    # Video models
    if "video" in category or "video" in model_id:
        uses.append("🎬 Видео для Reels/TikTok/Shorts")
        uses.append("📱 Контент для соцсетей")
        uses.append("🎥 Превью и обложки")
    
    # Image models
    elif "image" in category or "image" in model_id or "t2i" in model_id:
        uses.append("🖼️ Креативы для рекламы")
        uses.append("📸 Баннеры и иллюстрации")
        uses.append("🎨 Визуалы для постов")
    
    # Text models
    elif "text" in category or "copy" in category:
        uses.append("✍️ Тексты объявлений")
        uses.append("📝 Посты и описания")
        uses.append("💬 Сценарии для видео")
    
    # Audio/Voice
    elif "audio" in category or "voice" in category or "speech" in category:
        uses.append("🎧 Озвучка видео")
        uses.append("📻 Аудио для рекламы")
        uses.append("🗣️ Голосовой контент")
    
    # Music
    elif "music" in category:
        uses.append("🎵 Фоновая музыка")
        uses.append("🎶 Треки для видео")
        uses.append("🔊 Звуковые эффекты")
    
    # Enhance/Tools
    elif "enhance" in category or "upscale" in category:
        uses.append("✨ Улучшение качества")
        uses.append("🔧 Обработка контента")
        uses.append("🖼️ Подготовка к публикации")
    
    # Generic fallback
    if not uses:
        uses = [
            "🚀 Креативный контент",
            "📱 Материалы для SMM",
            "🎯 Маркетинговые задачи"
        ]
    
    return uses[:4]  # Max 4 bullets


def _get_price_badge(model: Dict) -> Dict[str, any]:
    """
    Получить badge цены для UI.
    
    Returns:
        {
            "is_free": bool,
            "label": str,  # "🎁 БЕСПЛАТНО" или "💰 150 ₽"
            "price_rub": float or None,
            "daily_limit": int or None
        }
    """
    pricing = model.get("pricing", {})
    is_free = pricing.get("is_free", False)
    
    if is_free:
        # Check for daily limit (if exists in metadata)
        daily_limit = model.get("free_daily_limit")  # Can be added to SOT
        
        if daily_limit:
            return {
                "is_free": True,
                "label": f"🎁 БЕСПЛАТНО ({daily_limit}/день)",
                "price_rub": 0,
                "daily_limit": daily_limit
            }
        else:
            return {
                "is_free": True,
                "label": "🎁 БЕСПЛАТНО",
                "price_rub": 0,
                "daily_limit": None
            }
    
    # Paid model - get final user price
    # Use rub_per_gen from pricing (already includes markup if applied at SOT level)
    rub_per_gen = pricing.get("rub_per_gen", 0)
    
    if rub_per_gen > 0:
        return {
            "is_free": False,
            "label": f"💰 {rub_per_gen:.0f} ₽",
            "price_rub": rub_per_gen,
            "daily_limit": None
        }
    
    # No price info
    return {
        "is_free": False,
        "label": "💰 Платная",
        "price_rub": None,
        "daily_limit": None
    }


def _get_example_prompts(model: Dict) -> List[str]:
    """Получить примеры промптов для модели."""
    # Check ui_example_prompts first
    ui_examples = model.get("ui_example_prompts", [])
    if ui_examples and len(ui_examples) > 0:
        return ui_examples[:2]  # Max 2
    
    # Fallback to examples
    examples = model.get("examples", [])
    if examples and len(examples) > 0:
        # Extract prompts from examples if they're objects
        prompts = []
        for ex in examples[:2]:
            if isinstance(ex, dict):
                prompt = ex.get("prompt", ex.get("text", ""))
                if prompt:
                    prompts.append(prompt)
            elif isinstance(ex, str):
                prompts.append(ex)
        
        if prompts:
            return prompts
    
    # Generic examples based on category
    category = model.get("category", "").lower()
    
    if "video" in category:
        return [
            "Современный город в киберпанк-стиле, неоновые огни",
            "Кот играет с клубком пряжи, 4K"
        ]
    elif "image" in category:
        return [
            "Минималистичный логотип для стартапа",
            "Абстрактный баннер для соцсетей"
        ]
    elif "text" in category:
        return [
            "Напиши пост для Instagram про новый продукт",
            "Создай сценарий для Reels на 30 секунд"
        ]
    elif "audio" in category or "voice" in category:
        return [
            "Озвучь: Добро пожаловать в наш сервис!",
            "Голос для рекламного ролика"
        ]
    elif "music" in category:
        return [
            "Энергичная фоновая музыка для видео",
            "Спокойный эмбиент для медитации"
        ]
    
    return ["Опишите что хотите получить"]


def _get_short_pitch(model: Dict) -> str:
    """Короткий pitch (1 строка) для модели."""
    description = model.get("description", "")
    
    # Если есть описание - используем первое предложение
    if description:
        first_sentence = description.split('.')[0].split('\n')[0]
        if len(first_sentence) > 10 and len(first_sentence) < 80:
            return first_sentence.strip()
    
    # Fallback на основе category
    category = model.get("category", "").lower()
    display_name = model.get("display_name", "Модель")
    
    if "video" in category:
        return f"Генерация видео для соцсетей и рекламы"
    elif "image" in category:
        return f"Создание изображений и креативов"
    elif "text" in category:
        return f"Написание текстов и сценариев"
    elif "audio" in category or "voice" in category:
        return f"Озвучка и работа с аудио"
    elif "music" in category:
        return f"Генерация музыки и звуков"
    elif "enhance" in category:
        return f"Улучшение и обработка контента"
    
    return f"Нейросеть для креативных задач"


def _get_upsell_line(model: Dict) -> Optional[str]:
    """Получить upsell строку для платных моделей."""
    is_free = model.get("pricing", {}).get("is_free", False)
    
    if is_free:
        return None  # No upsell for free models
    
    # Generic upsell for paid models
    return "✨ Премиум качество • Без лимитов • Быстрая генерация"


def build_profile(model: Dict) -> Dict:
    """
    Построить маркетинговый профиль модели.
    
    Args:
        model: модель из SOURCE_OF_TRUTH
    
    Returns:
        {
            "model_id": str,
            "display_name": str,
            "short_pitch": str,  # 1 line
            "best_for": List[str],  # 3-4 bullets
            "output_format": str,  # "Видео 9:16", "Изображение", etc
            "examples": List[str],  # 2 example prompts
            "price": {
                "is_free": bool,
                "label": str,
                "price_rub": float,
                "daily_limit": int or None
            },
            "upsell_line": str or None,
            "category": str  # UI category
        }
    """
    from app.ui.catalog import map_category
    
    return {
        "model_id": model.get("model_id", ""),
        "display_name": model.get("display_name", ""),
        "short_pitch": _get_short_pitch(model),
        "best_for": _get_marketing_use_cases(model),
        "output_format": _get_output_format_label(model),
        "examples": _get_example_prompts(model),
        "price": _get_price_badge(model),
        "upsell_line": _get_upsell_line(model),
        "category": map_category(model.get("category", "")),
    }
