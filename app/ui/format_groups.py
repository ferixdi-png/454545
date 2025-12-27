"""Format grouping and sorting helpers."""
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Format groups for catalog organization
FORMAT_GROUPS = {
    "text2image": {
        "emoji": "📝→🖼",
        "title": "Текст в картинку",
        "desc": "Креативы, баннеры, иллюстрации"
    },
    "image2image": {
        "emoji": "🖼→🖼",
        "title": "Редактировать фото",
        "desc": "Изменить стиль, улучшить, вариации"
    },
    "image2video": {
        "emoji": "🖼→🎥",
        "title": "Фото в видео",
        "desc": "Оживить фото, создать анимацию"
    },
    "text2video": {
        "emoji": "📝→🎥",
        "title": "Текст в видео",
        "desc": "Генерация видео из промпта"
    },
    "audio2text": {
        "emoji": "🎧→📝",
        "title": "Аудио в текст",
        "desc": "Транскрибация, распознавание речи"
    },
    "text2audio": {
        "emoji": "📝→🎧",
        "title": "Текст в озвучку",
        "desc": "Голосовые сообщения, звуки"
    },
    "tools": {
        "emoji": "🛠",
        "title": "Инструменты",
        "desc": "Фон, апскейл, обработка"
    }
}


def get_format_group(model: Dict) -> str:
    """
    Get format group for model (from overlay or inferred).
    
    Args:
        model: Model dict (with overlay)
    
    Returns:
        Format group key (text2image, image2video, tools, etc.)
    """
    # Check UI overlay first
    if "ui" in model and "format_group" in model["ui"]:
        return model["ui"]["format_group"]
    
    # Fallback: infer from category
    category = model.get("category", "").lower()
    
    if "text-to-image" in category or "t2i" in category:
        return "text2image"
    elif "image-to-image" in category or "i2i" in category:
        return "image2image"
    elif "image-to-video" in category:
        return "image2video"
    elif "text-to-video" in category:
        return "text2video"
    elif "audio-to-text" in category or "stt" in category or "transcription" in category:
        return "audio2text"
    elif "text-to-audio" in category or "tts" in category or "text-to-speech" in category:
        return "text2audio"
    elif "upscale" in category or "background" in category or "enhance" in category:
        return "tools"
    else:
        return "tools"  # Default fallback


def get_popular_score(model: Dict) -> int:
    """
    Get popularity score (higher = more popular).
    
    Args:
        model: Model dict (with overlay)
    
    Returns:
        Score 0-100
    """
    # Check UI overlay
    if "ui" in model and "popular_score" in model["ui"]:
        return model["ui"]["popular_score"]
    
    # Fallback heuristic: cheaper + faster = more popular
    pricing = model.get("pricing", {})
    rub_per_gen = pricing.get("rub_per_gen", 999999)
    
    # Simple heuristic: cheaper = more popular
    if rub_per_gen < 10:
        return 90
    elif rub_per_gen < 50:
        return 70
    elif rub_per_gen < 200:
        return 50
    else:
        return 30


def group_by_format(models: Dict[str, Dict]) -> Dict[str, List[Dict]]:
    """
    Group models by format group.
    
    Args:
        models: Dict of models (model_id -> model)
    
    Returns:
        Dict[format_group, List[model]]
    """
    groups = {key: [] for key in FORMAT_GROUPS.keys()}
    
    for model_id, model in models.items():
        if not model.get("enabled", True):
            continue
        
        format_group = get_format_group(model)
        if format_group not in groups:
            format_group = "tools"  # Fallback
        
        groups[format_group].append(model)
    
    # Sort each group by popular_score
    for group_key in groups:
        groups[group_key].sort(key=lambda m: get_popular_score(m), reverse=True)
    
    return groups


def get_popular_models(models: Dict[str, Dict], limit: int = 10) -> List[Dict]:
    """
    Get top N popular models (sorted by popular_score).
    
    Args:
        models: Dict of models
        limit: Max models to return
    
    Returns:
        List of models sorted by popularity
    """
    enabled = [m for m in models.values() if m.get("enabled", True)]
    enabled.sort(key=lambda m: get_popular_score(m), reverse=True)
    return enabled[:limit]
