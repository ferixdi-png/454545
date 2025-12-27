"""Test presets.json schema and integrity."""
import pytest
import json
from pathlib import Path


@pytest.fixture
def presets_data():
    """Load presets.json."""
    presets_file = Path(__file__).parent.parent / "app" / "ui" / "content" / "presets.json"
    
    if not presets_file.exists():
        pytest.skip("presets.json not found")
    
    return json.loads(presets_file.read_text(encoding="utf-8"))


def test_presets_schema(presets_data):
    """Validate presets.json structure."""
    assert "presets" in presets_data, "Missing 'presets' key"
    assert "categories" in presets_data, "Missing 'categories' key"
    
    assert isinstance(presets_data["presets"], list), "presets must be list"
    assert isinstance(presets_data["categories"], dict), "categories must be dict"


def test_preset_required_fields(presets_data):
    """Ensure each preset has required fields."""
    required_fields = [
        "id",
        "category",
        "title",
        "description",
        "what_you_get",
        "what_you_need",
        "perfect_for",
        "example_prompt",
        "format",
    ]
    
    for preset in presets_data["presets"]:
        for field in required_fields:
            assert field in preset, f"Preset {preset.get('id', 'unknown')} missing field: {field}"
        
        # Validate types
        assert isinstance(preset["id"], str)
        assert isinstance(preset["title"], str)
        assert isinstance(preset["perfect_for"], list)
        assert len(preset["perfect_for"]) >= 2, f"Preset {preset['id']}: need at least 2 'perfect_for' items"


def test_preset_categories_exist(presets_data):
    """Ensure all preset categories are defined."""
    categories = presets_data["categories"]
    
    for preset in presets_data["presets"]:
        category = preset["category"]
        assert category in categories, f"Preset {preset['id']} references undefined category: {category}"


def test_preset_formats_valid(presets_data):
    """Ensure preset formats are valid."""
    valid_formats = [
        "text-to-image",
        "image-to-image",
        "image-to-video",
        "text-to-video",
        "text-to-audio",
        "audio-to-audio",
        "audio-to-text",
        "image-upscale",
        "background-remove",
        "video-editing",
        "audio-editing",
    ]
    
    for preset in presets_data["presets"]:
        format_id = preset["format"]
        assert format_id in valid_formats, f"Preset {preset['id']} has invalid format: {format_id}"


def test_preset_example_prompts_not_empty(presets_data):
    """Ensure all example prompts are meaningful."""
    for preset in presets_data["presets"]:
        example = preset["example_prompt"]
        assert len(example) > 20, f"Preset {preset['id']}: example_prompt too short"
        assert not example.startswith("TODO"), f"Preset {preset['id']}: example_prompt is placeholder"


def test_category_icons(presets_data):
    """Ensure categories have icons."""
    for cat_id, cat_data in presets_data["categories"].items():
        assert "icon" in cat_data, f"Category {cat_id} missing icon"
        assert "title" in cat_data, f"Category {cat_id} missing title"
        assert "description" in cat_data, f"Category {cat_id} missing description"


def test_no_duplicate_preset_ids(presets_data):
    """Ensure preset IDs are unique."""
    preset_ids = [p["id"] for p in presets_data["presets"]]
    assert len(preset_ids) == len(set(preset_ids)), "Duplicate preset IDs found"


def test_presets_have_variety():
    """Ensure we have presets across different categories."""
    presets_file = Path(__file__).parent.parent / "app" / "ui" / "content" / "presets.json"
    
    if not presets_file.exists():
        pytest.skip("presets.json not found")
    
    data = json.loads(presets_file.read_text(encoding="utf-8"))
    
    categories_used = set(p["category"] for p in data["presets"])
    assert len(categories_used) >= 3, "Should have presets in at least 3 categories"
