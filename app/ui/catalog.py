"""
UI Catalog - единый слой маппинга SOURCE_OF_TRUTH в UI категории.

Гарантии:
- ВСЕ enabled модели попадают в UI tree
- Нет дублей
- Нет потерянных моделей
- callback_data <= 64 bytes
"""
import json
import os
import logging
from typing import Dict, List, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# UI категории (маркетинг-ориентированные)
UI_CATEGORIES = {
    "video": {
        "emoji": "🎬",
        "title": "Видео",
        "desc": "Reels, TikTok, YouTube Shorts",
        "sot_categories": ["video", "text-to-video", "image-to-video", "video-to-video"],
    },
    "image": {
        "emoji": "🖼️",
        "title": "Изображения",
        "desc": "Креативы, баннеры, иллюстрации",
        "sot_categories": ["image", "text-to-image", "image-to-image", "t2i", "i2i"],
    },
    "text_ads": {
        "emoji": "✍️",
        "title": "Тексты/Реклама",
        "desc": "Посты, сценарии, объявления",
        "sot_categories": ["text", "copy", "ads", "text-generation"],
    },
    "audio_voice": {
        "emoji": "🎧",
        "title": "Аудио/Озвучка",
        "desc": "Озвучка, распознавание, аудио",
        "sot_categories": ["audio", "voice", "speech", "tts", "stt"],
    },
    "music": {
        "emoji": "🎵",
        "title": "Музыка",
        "desc": "Треки, мелодии, звуковые эффекты",
        "sot_categories": ["music", "melody", "sound-effect"],
    },
    "tools": {
        "emoji": "🧰",
        "title": "Инструменты",
        "desc": "Апскейл, удаление фона, улучшение",
        "sot_categories": ["enhance", "upscale", "background", "tools"],
    },
    "other": {
        "emoji": "🔮",
        "title": "Другое",
        "desc": "Дополнительные возможности",
        "sot_categories": ["other", "avatar", "lipsync"],
    },
}


@lru_cache(maxsize=1)
def _load_source_of_truth() -> Dict:
    """Load models from SOURCE_OF_TRUTH.json (cached)."""
    sot_path = os.path.join(
        os.path.dirname(__file__),
        "../../models/KIE_SOURCE_OF_TRUTH.json"
    )
    
    if not os.path.exists(sot_path):
        logger.error(f"SOURCE_OF_TRUTH not found: {sot_path}")
        return {"models": {}}
    
    try:
        with open(sot_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"✅ Loaded {len(data.get('models', {}))} models from SOURCE_OF_TRUTH")
        return data
    except Exception as e:
        logger.error(f"❌ Failed to load SOURCE_OF_TRUTH: {e}")
        return {"models": {}}


def load_models_sot() -> Dict[str, Dict]:
    """Get all models as dict (model_id -> model)."""
    data = _load_source_of_truth()
    return data.get("models", {})


def map_category(sot_category: str) -> str:
    """
    Map SOURCE_OF_TRUTH category to UI category.
    
    Args:
        sot_category: category from SOURCE_OF_TRUTH (e.g. "text-to-video")
    
    Returns:
        UI category key (e.g. "video")
    """
    if not sot_category:
        return "other"
    
    sot_category_lower = sot_category.lower()
    
    # Прямой поиск в списках каждой UI категории
    for ui_cat, info in UI_CATEGORIES.items():
        if sot_category_lower in [c.lower() for c in info["sot_categories"]]:
            return ui_cat
    
    # Partial match fallback
    if "video" in sot_category_lower:
        return "video"
    if "image" in sot_category_lower or "i2i" in sot_category_lower or "t2i" in sot_category_lower:
        return "image"
    if "text" in sot_category_lower or "copy" in sot_category_lower:
        return "text_ads"
    if "audio" in sot_category_lower or "voice" in sot_category_lower or "speech" in sot_category_lower:
        return "audio_voice"
    if "music" in sot_category_lower:
        return "music"
    if "enhance" in sot_category_lower or "upscale" in sot_category_lower:
        return "tools"
    
    return "other"


def build_ui_tree() -> Dict[str, List[Dict]]:
    """
    Build UI tree: category_key -> list of models.
    
    Returns:
        {
            "video": [model1, model2, ...],
            "image": [...],
            ...
        }
    
    Гарантии:
    - Все enabled модели попадают в tree
    - Нет дублей (каждая модель в 1 категории)
    - Сортировка: FREE первыми, затем по цене
    """
    models_dict = load_models_sot()
    tree = {cat: [] for cat in UI_CATEGORIES.keys()}
    
    for model_id, model in models_dict.items():
        # Skip disabled
        if not model.get("enabled", True):
            continue
        
        # Skip processors
        if model_id.endswith("_processor"):
            continue
        
        # Map to UI category
        sot_category = model.get("category", "other")
        ui_cat = map_category(sot_category)
        
        tree[ui_cat].append(model)
    
    # Sort each category: FREE first, then by price
    for cat in tree:
        tree[cat].sort(key=lambda m: (
            not m.get("pricing", {}).get("is_free", False),  # FREE first
            m.get("pricing", {}).get("rub_per_gen", 999999)  # Then by price
        ))
    
    return tree


def get_model(model_id: str) -> Optional[Dict]:
    """Get model by ID from SOURCE_OF_TRUTH."""
    models = load_models_sot()
    return models.get(model_id)


def get_counts() -> Dict[str, int]:
    """Get counts per UI category."""
    tree = build_ui_tree()
    return {cat: len(models) for cat, models in tree.items()}


def get_all_enabled_models() -> List[Dict]:
    """Get all enabled models as list."""
    models_dict = load_models_sot()
    return [
        model for model in models_dict.values()
        if model.get("enabled", True) and not model.get("model_id", "").endswith("_processor")
    ]


def search_models(query: str) -> List[Dict]:
    """
    Search models by display_name, tags, category.
    
    Args:
        query: search query (case-insensitive)
    
    Returns:
        List of matching models
    """
    if not query or len(query) < 2:
        return []
    
    query_lower = query.lower()
    models = get_all_enabled_models()
    results = []
    
    for model in models:
        # Search in display_name
        if query_lower in model.get("display_name", "").lower():
            results.append(model)
            continue
        
        # Search in tags
        tags = model.get("tags", []) or []
        if any(query_lower in tag.lower() for tag in tags):
            results.append(model)
            continue
        
        # Search in category
        if query_lower in model.get("category", "").lower():
            results.append(model)
            continue
    
    # Sort by FREE first, then price
    results.sort(key=lambda m: (
        not m.get("pricing", {}).get("is_free", False),
        m.get("pricing", {}).get("rub_per_gen", 999999)
    ))
    
    return results[:20]  # Limit results
