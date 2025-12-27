"""Consistent naming across all UI screens.

RULES:
- One function per entity type (model, format)
- No random synonyms between screens
- Same name in catalog, search, cards, buttons
"""
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from app.ui.tone import FORMAT_NAMES

log = logging.getLogger(__name__)

# Cache for marketing tags
_marketing_tags: Optional[Dict[str, Any]] = None


def model_display_name(model_id: str, model_data: Optional[Dict[str, Any]] = None) -> str:
    """Get consistent display name for model.
    
    Priority:
    1. model_data['title'] if provided
    2. Marketing name from model_marketing_tags.json
    3. Cleaned model_id (fallback)
    
    Args:
        model_id: Model identifier (e.g., "flux/dev")
        model_data: Optional model data from SOURCE_OF_TRUTH
    
    Returns:
        Display name (e.g., "Flux Dev")
    """
    # Try model_data title first
    if model_data and isinstance(model_data, dict):
        title = model_data.get("title")
        if title and isinstance(title, str):
            return title.strip()
    
    # Try marketing tags
    tags = _get_marketing_tags()
    if model_id in tags:
        tag_data = tags[model_id]
        if isinstance(tag_data, dict) and "description" in tag_data:
            # Use first part of description as name (before dash if present)
            desc = tag_data["description"]
            if " — " in desc:
                return desc.split(" — ")[0].strip()
            return desc.strip()
    
    # Fallback: clean up model_id
    # "flux/dev" -> "Flux Dev"
    # "stable-diffusion-xl/base" -> "Stable Diffusion XL Base"
    name = model_id.replace("/", " ").replace("-", " ").title()
    return name


def format_display_name(format_id: str) -> str:
    """Get consistent display name for format.
    
    Args:
        format_id: Format identifier (e.g., "text-to-image")
    
    Returns:
        Display name (e.g., "Текст → Изображение")
    """
    return FORMAT_NAMES.get(format_id, format_id)


def category_display_name(category_id: str) -> str:
    """Get display name for preset category.
    
    Args:
        category_id: Category identifier (e.g., "ads", "reels")
    
    Returns:
        Display name
    """
    category_names = {
        "ads": "Реклама и Performance",
        "reels": "Reels / TikTok / Shorts",
        "branding": "Брендинг и дизайн",
        "ecommerce": "E-commerce",
        "audio": "Аудио и голос",
        "utilities": "Утилиты",
    }
    
    return category_names.get(category_id, category_id.title())


def short_description(model_id: str) -> Optional[str]:
    """Get short marketing description for model.
    
    Returns 1-line description or None.
    """
    tags = _get_marketing_tags()
    if model_id in tags:
        tag_data = tags[model_id]
        if isinstance(tag_data, dict):
            return tag_data.get("description")
    
    return None


def get_perfect_for_tags(model_id: str) -> Optional[list]:
    """Get 'perfect for' tags for model card.
    
    Returns list like ["Реклама", "Обложки", "UGC"] or None.
    """
    tags = _get_marketing_tags()
    if model_id in tags:
        tag_data = tags[model_id]
        if isinstance(tag_data, dict):
            return tag_data.get("perfect_for")
    
    return None


def get_difficulty(model_id: str) -> Optional[str]:
    """Get difficulty level: "Легко" | "Средне" | "Сложно"."""
    tags = _get_marketing_tags()
    if model_id in tags:
        tag_data = tags[model_id]
        if isinstance(tag_data, dict):
            return tag_data.get("difficulty")
    
    return None


def _get_marketing_tags() -> Dict[str, Any]:
    """Load marketing tags from JSON (cached)."""
    global _marketing_tags
    
    if _marketing_tags is not None:
        return _marketing_tags
    
    content_dir = Path(__file__).parent / "content"
    tags_file = content_dir / "model_marketing_tags.json"
    
    try:
        if tags_file.exists():
            data = json.loads(tags_file.read_text(encoding="utf-8"))
            _marketing_tags = data.get("model_tags", {})
            log.info(f"Loaded marketing tags for {len(_marketing_tags)} models")
            return _marketing_tags
    except Exception as e:
        log.warning(f"Failed to load marketing tags: {e}")
    
    _marketing_tags = {}
    return _marketing_tags


def reload_marketing_tags() -> None:
    """Force reload marketing tags (admin utility)."""
    global _marketing_tags
    _marketing_tags = None
    _get_marketing_tags()
