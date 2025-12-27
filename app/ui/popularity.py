"""Popularity system for models (manual curation, no lies).

RULES:
- Default popularity stored in popular_models.json
- Fallback: free tier + cheapest + safe defaults
- Never claim "топ по аналитике" unless actually tracked
"""
import json
import logging
from pathlib import Path
from typing import List, Set, Optional

log = logging.getLogger(__name__)

# Cache
_popular_models: Optional[List[str]] = None


def get_popular_models() -> List[str]:
    """Get curated list of popular models (manually maintained).
    
    Returns list of model_ids in priority order.
    """
    global _popular_models
    
    if _popular_models is not None:
        return _popular_models
    
    # Try to load from file
    content_dir = Path(__file__).parent / "content"
    popular_file = content_dir / "model_marketing_tags.json"
    
    try:
        if popular_file.exists():
            data = json.loads(popular_file.read_text(encoding="utf-8"))
            _popular_models = data.get("popular_models", [])
            
            if _popular_models:
                log.info(f"Loaded {len(_popular_models)} popular models from file")
                return _popular_models
    except Exception as e:
        log.warning(f"Failed to load popular models from file: {e}")
    
    # Fallback: safe defaults (free + commonly used)
    # Must use IDs from allowlist only
    _popular_models = [
        "flux-2/pro-text-to-image",
        "flux-2/flex-text-to-image",
        "google/imagen4-fast",
        "seedream/4.5-text-to-image",
        "kling-2.6/text-to-video",
        "wan/2-6-text-to-video",
        "elevenlabs/text-to-speech-turbo-2-5",
        "topaz/image-upscale",
    ]
    
    log.info(f"Using {len(_popular_models)} fallback popular models")
    return _popular_models


def filter_popular_by_format(format_id: str, all_models: List[dict], limit: int = 3) -> List[dict]:
    """Get top N popular models for specific format.
    
    Args:
        format_id: Format identifier (e.g., "text-to-image")
        all_models: List of all model dicts with 'model_id' and 'format'
        limit: Max number to return (default 3 for "Рекомендуем")
    
    Returns:
        List of model dicts, ordered by popularity
    """
    popular_ids = get_popular_models()
    
    # Filter by format
    format_models = [m for m in all_models if m.get("format") == format_id]
    
    # Sort by popularity (maintain order from popular_ids)
    popular_set = set(popular_ids)
    
    # First: popular models in order
    result = []
    for model_id in popular_ids:
        for model in format_models:
            if model.get("model_id") == model_id:
                result.append(model)
                break
        
        if len(result) >= limit:
            break
    
    # If not enough, add remaining models
    if len(result) < limit:
        for model in format_models:
            if model.get("model_id") not in popular_set:
                result.append(model)
                if len(result) >= limit:
                    break
    
    return result[:limit]


def get_popular_for_home(all_models: List[dict], limit: int = 12) -> List[dict]:
    """Get models for "⭐ Популярное" section on home screen.
    
    Args:
        all_models: List of all model dicts
        limit: Max to show (8-12 recommended)
    
    Returns:
        List of model dicts in popularity order
    """
    popular_ids = get_popular_models()
    
    result = []
    popular_set = set(popular_ids)
    
    # Add popular models in order
    for model_id in popular_ids:
        for model in all_models:
            if model.get("model_id") == model_id:
                result.append(model)
                break
        
        if len(result) >= limit:
            break
    
    return result[:limit]


def is_popular(model_id: str) -> bool:
    """Check if model is in popular list."""
    return model_id in get_popular_models()


def reload_popular_models() -> None:
    """Force reload popular models from file (admin utility)."""
    global _popular_models
    _popular_models = None
    get_popular_models()
