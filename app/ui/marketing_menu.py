"""
Marketing-focused UI structure for bot.

Маркетинговые категории для SMM/маркетологов:
- Видео-креативы (Reels/Shorts/TikTok)
- Визуалы (баннеры, посты, обложки)
- Тексты (посты, описания)
- Аватары/UGC
- Озвучка/аудио
- Улучшалки (апскейл, фон)
- Экспериментальные
"""
from typing import Dict, List
import json
import os


MARKETING_CATEGORIES = {
    "video_creatives": {
        "emoji": "🎥",
        "title": "Видео",
        "desc": "Генерация видео: Reels, Shorts, TikTok",
        "kie_categories": ["video"],
        "tags": ["reels", "shorts", "tiktok", "video", "видео"]
    },
    "visuals": {
        "emoji": "🖼️",
        "title": "Изображения",
        "desc": "Создание картинок: баннеры, посты, иллюстрации",
        "kie_categories": ["image"],
        "tags": ["banner", "post", "cover", "image", "картинка"]
    },
    "avatars": {
        "emoji": "🧑‍🎤",
        "title": "Аватары",
        "desc": "Персонажи и говорящие головы",
        "kie_categories": ["avatar"],
        "tags": ["avatar", "character", "lipsync", "аватар"]
    },
    "audio": {
        "emoji": "🔊",
        "title": "Аудио",
        "desc": "Озвучка, распознавание речи",
        "kie_categories": ["audio"],
        "tags": ["audio", "voice", "speech", "аудио"]
    },
    "music": {
        "emoji": "🎵",
        "title": "Музыка",
        "desc": "Генерация музыки и звуковых эффектов",
        "kie_categories": ["music"],
        "tags": ["music", "melody", "sound", "музыка"]
    },
    "enhance": {
        "emoji": "✨",
        "title": "Улучшение",
        "desc": "Апскейл, удаление фона и водяных знаков",
        "kie_categories": ["enhance"],
        "tags": ["upscale", "background", "enhance", "качество"]
    },
    "other": {
        "emoji": "🔮",
        "title": "Другие",
        "desc": "Дополнительные инструменты",
        "kie_categories": ["other"],
        "tags": ["other", "tools"]
    }
}


def load_registry() -> List[Dict]:
    """Load KIE models registry from SOURCE OF TRUTH."""
    registry_path = os.path.join(
        os.path.dirname(__file__),
        "../../models/KIE_SOURCE_OF_TRUTH.json"
    )
    
    if not os.path.exists(registry_path):
        return []
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Конвертируем из dict в list
        models_dict = data.get("models", {})
        return list(models_dict.values())


def map_model_to_marketing_category(model: Dict) -> str:
    """Map KIE model to marketing category based on SOURCE_OF_TRUTH category."""
    category = model.get("category", "other")
    
    # Direct mapping from SOURCE_OF_TRUTH categories
    category_map = {
        "video": "video_creatives",
        "image": "visuals",
        "avatar": "avatars",
        "audio": "audio",
        "music": "music",
        "enhance": "enhance",
        "other": "other"
    }
    
    return category_map.get(category, "other")


def build_ui_tree() -> Dict[str, List[Dict]]:
    """
    Build UI tree from registry.
    
    Includes ONLY enabled models.
    Models without input_schema will use fallback (prompt-only).
    
    Сортировка по цене: самые дешёвые первыми.
    """
    registry = load_registry()
    tree = {cat: [] for cat in MARKETING_CATEGORIES.keys()}
    
    for model in registry:
        # Skip non-model entries (processors, etc.)
        model_id = model.get("model_id", "")
        if not model_id or model_id.endswith("_processor"):
            continue
        
        # Skip disabled models
        if not model.get("enabled", True):
            continue
        
        # Get price from SOURCE OF TRUTH format
        pricing = model.get("pricing", {})
        # Не требуем обязательное наличие pricing - покажем все модели
        
        mk_cat = map_model_to_marketing_category(model)
        tree[mk_cat].append(model)
    
    # Sort each category by price (cheapest first)
    # Модели без цены идут в конец
    for cat in tree:
        tree[cat].sort(key=lambda m: m.get("pricing", {}).get("rub_per_gen", 999999))
    
    return tree


def get_category_info(category_key: str) -> Dict:
    """Get marketing category info."""
    return MARKETING_CATEGORIES.get(category_key, {})


def get_model_by_id(model_id: str) -> Dict:
    """Get model from registry by ID."""
    registry = load_registry()
    for model in registry:
        if model.get("model_id") == model_id:
            return model
    return {}


def count_models_by_category() -> Dict[str, int]:
    """Count models in each marketing category."""
    tree = build_ui_tree()
    return {cat: len(models) for cat, models in tree.items()}
