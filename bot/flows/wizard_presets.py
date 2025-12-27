"""Wizard overview and presets support."""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Cache for presets
_presets_cache = None


def load_presets() -> Dict:
    """Load presets from presets_ru.json."""
    global _presets_cache
    
    if _presets_cache is not None:
        return _presets_cache
    
    try:
        repo_root = Path(__file__).resolve().parent.parent.parent
        presets_file = repo_root / "app/ui/presets_ru.json"
        
        if not presets_file.exists():
            logger.warning(f"Presets file not found: {presets_file}")
            return {"presets": []}
        
        with open(presets_file, "r", encoding="utf-8") as f:
            _presets_cache = json.load(f)
        
        logger.info(f"Loaded {len(_presets_cache.get('presets', []))} presets")
        return _presets_cache
    except Exception as e:
        logger.error(f"Failed to load presets: {e}")
        return {"presets": []}


def get_presets_for_format(format_key: str) -> List[Dict]:
    """Get presets matching format."""
    presets_data = load_presets()
    all_presets = presets_data.get("presets", [])
    
    # Filter by format
    matching = [
        p for p in all_presets
        if format_key in p.get("formats", [])
    ]
    
    return matching[:5]  # Max 5 presets


def get_preset_by_id(preset_id: str) -> Optional[Dict]:
    """Get preset by ID."""
    presets_data = load_presets()
    all_presets = presets_data.get("presets", [])
    
    for preset in all_presets:
        if preset.get("id") == preset_id:
            return preset
    
    return None


def detect_model_format(model_config: Dict) -> Optional[str]:
    """
    Detect model format from input_schema.
    
    Returns:
        Format key like "text-to-video", "image-to-image", etc.
    """
    inputs = model_config.get("inputs", {})
    output_type = model_config.get("output_type", "")
    
    # Check required inputs
    has_prompt = "prompt" in inputs and inputs["prompt"].get("required", False)
    has_image = any(
        inp.get("type") in ["IMAGE_URL", "IMAGE_FILE"] and inp.get("required", False)
        for inp in inputs.values()
    )
    has_video = any(
        inp.get("type") in ["VIDEO_URL", "VIDEO_FILE"] and inp.get("required", False)
        for inp in inputs.values()
    )
    has_audio = any(
        inp.get("type") in ["AUDIO_URL", "AUDIO_FILE"] and inp.get("required", False)
        for inp in inputs.values()
    )
    
    # Detect format
    if "VIDEO" in output_type.upper():
        if has_image:
            return "image-to-video"
        elif has_prompt:
            return "text-to-video"
        return "video"
    elif "IMAGE" in output_type.upper():
        if has_image:
            return "image-to-image"
        elif has_prompt:
            return "text-to-image"
        return "image"
    elif "AUDIO" in output_type.upper():
        if has_prompt:
            return "text-to-audio"
        return "audio"
    
    return None
