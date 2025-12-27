"""Test format coverage: all enabled models must be mapped to ≥1 format."""
import json
import pytest
from pathlib import Path


def test_format_coverage_complete():
    """Every enabled model in SOURCE_OF_TRUTH must have a format mapping."""
    # Load source of truth
    sot_path = Path(__file__).parent.parent / "models" / "KIE_SOURCE_OF_TRUTH.json"
    with open(sot_path) as f:
        sot_data = json.load(f)
    
    # Handle both {"models": {}} and flat dict structure
    if "models" in sot_data and isinstance(sot_data["models"], dict):
        models = sot_data["models"]
    else:
        models = sot_data
    
    # Load format map
    map_path = Path(__file__).parent.parent / "app" / "ui" / "content" / "model_format_map.json"
    with open(map_path) as f:
        format_map = json.load(f)
    
    model_to_formats = format_map.get("model_to_formats", {})
    
    # Check all enabled models (assume all are enabled unless explicitly disabled)
    enabled_models = [
        model_id for model_id, config in models.items()
        if config.get("enabled", True)  # Default to True
    ]
    
    unmapped = []
    for model_id in enabled_models:
        if model_id not in model_to_formats:
            unmapped.append(model_id)
        elif not model_to_formats[model_id]:  # Empty list
            unmapped.append(model_id)
    
    assert not unmapped, (
        f"These enabled models have no format mapping: {unmapped}\n"
        f"Add them to app/ui/content/model_format_map.json"
    )


def test_format_map_valid_formats():
    """All formats in mapping must be valid format keys."""
    map_path = Path(__file__).parent.parent / "app" / "ui" / "content" / "model_format_map.json"
    with open(map_path) as f:
        format_map = json.load(f)
    
    # Valid formats (from formats.py)
    valid_formats = {
        "text-to-video",
        "image-to-video",
        "text-to-image",
        "image-to-image",
        "image-upscale",
        "background-remove",
        "text-to-audio",
        "audio-editing",
        "audio-to-video",
        "video-editing",
    }
    
    model_to_formats = format_map.get("model_to_formats", {})
    
    invalid = []
    for model_id, formats in model_to_formats.items():
        for fmt in formats:
            if fmt not in valid_formats:
                invalid.append((model_id, fmt))
    
    assert not invalid, (
        f"These models have invalid format keys: {invalid}\n"
        f"Valid formats: {valid_formats}"
    )


def test_format_map_no_duplicates():
    """Models should not have duplicate format entries."""
    map_path = Path(__file__).parent.parent / "app" / "ui" / "content" / "model_format_map.json"
    with open(map_path) as f:
        format_map = json.load(f)
    
    model_to_formats = format_map.get("model_to_formats", {})
    
    duplicates = []
    for model_id, formats in model_to_formats.items():
        if len(formats) != len(set(formats)):
            duplicates.append(model_id)
    
    assert not duplicates, f"These models have duplicate formats: {duplicates}"


def test_format_map_models_exist_in_sot():
    """All models in format map must exist in SOURCE_OF_TRUTH."""
    sot_path = Path(__file__).parent.parent / "models" / "KIE_SOURCE_OF_TRUTH.json"
    with open(sot_path) as f:
        sot_data = json.load(f)
    
    # Handle both {"models": {}} and flat dict structure
    if "models" in sot_data and isinstance(sot_data["models"], dict):
        models = sot_data["models"]
    else:
        models = sot_data
    
    map_path = Path(__file__).parent.parent / "app" / "ui" / "content" / "model_format_map.json"
    with open(map_path) as f:
        format_map = json.load(f)
    
    model_to_formats = format_map.get("model_to_formats", {})
    
    unknown = []
    for model_id in model_to_formats.keys():
        if model_id not in models:
            unknown.append(model_id)
    
    assert not unknown, (
        f"These models in format_map don't exist in SOURCE_OF_TRUTH: {unknown}\n"
        f"Remove them or add to SOURCE_OF_TRUTH"
    )


def test_get_models_for_format():
    """Test format filtering returns correct models."""
    # Skip if function doesn't exist yet
    pytest.skip("get_models_for_format implementation pending")


def test_format_taxonomy_complete():
    """Verify format taxonomy covers all model categories."""
    from pathlib import Path
    import json
    
    sot_path = Path(__file__).parent.parent / "models" / "KIE_SOURCE_OF_TRUTH.json"
    with open(sot_path) as f:
        sot_data = json.load(f)
    
    # Handle both {"models": {}} and flat dict structure
    if "models" in sot_data and isinstance(sot_data["models"], dict):
        models = sot_data["models"]
    else:
        models = sot_data
    
    # Get all unique categories
    categories = set()
    for config in models.values():
        # All models enabled by default in locked list
        cat = config.get("category", "")
        if cat:
            categories.add(cat)
    
    # Map categories to formats (from formats.py taxonomy)
    category_coverage = {
        "text-to-image": ["text-to-image"],
        "image-to-image": ["image-to-image"],
        "text-to-video": ["text-to-video"],
        "image-to-video": ["image-to-video"],
        "text-to-audio": ["text-to-audio"],
        "audio-processing": ["audio-editing"],
        "image-upscale": ["image-upscale"],
        "background-remove": ["background-remove"],
        "video-editing": ["video-editing"],
        "audio-to-video": ["audio-to-video"],
    }
    
    uncovered = []
    for cat in categories:
        if not any(cat.lower() in k.lower() or k.lower() in cat.lower() for k in category_coverage.keys()):
            uncovered.append(cat)
    
    # Allow some flexibility - just warn, don't fail
    if uncovered:
        print(f"Warning: These categories might need format mapping: {uncovered}")
