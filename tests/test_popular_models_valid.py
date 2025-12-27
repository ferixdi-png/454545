"""Test popular models validity."""
import pytest
import json
from pathlib import Path


def test_popular_models_json_exists():
    """Ensure model_marketing_tags.json exists."""
    tags_file = Path(__file__).parent.parent / "app" / "ui" / "content" / "model_marketing_tags.json"
    assert tags_file.exists(), "model_marketing_tags.json not found"


def test_popular_models_are_listed():
    """Ensure popular_models list exists and is not empty."""
    tags_file = Path(__file__).parent.parent / "app" / "ui" / "content" / "model_marketing_tags.json"
    
    if not tags_file.exists():
        pytest.skip("model_marketing_tags.json not found")
    
    data = json.loads(tags_file.read_text(encoding="utf-8"))
    
    assert "popular_models" in data, "Missing 'popular_models' list"
    assert isinstance(data["popular_models"], list)
    assert len(data["popular_models"]) >= 5, "Need at least 5 popular models"


def test_popular_models_have_tags():
    """Ensure each popular model has marketing tags defined."""
    tags_file = Path(__file__).parent.parent / "app" / "ui" / "content" / "model_marketing_tags.json"
    
    if not tags_file.exists():
        pytest.skip("model_marketing_tags.json not found")
    
    data = json.loads(tags_file.read_text(encoding="utf-8"))
    
    popular_models = data.get("popular_models", [])
    model_tags = data.get("model_tags", {})
    
    for model_id in popular_models:
        assert model_id in model_tags, f"Popular model {model_id} has no marketing tags"


def test_model_tags_schema():
    """Validate model_tags structure."""
    tags_file = Path(__file__).parent.parent / "app" / "ui" / "content" / "model_marketing_tags.json"
    
    if not tags_file.exists():
        pytest.skip("model_marketing_tags.json not found")
    
    data = json.loads(tags_file.read_text(encoding="utf-8"))
    
    model_tags = data.get("model_tags", {})
    
    for model_id, tag_data in model_tags.items():
        assert isinstance(tag_data, dict), f"Model {model_id} tags must be dict"
        
        # Check required fields
        assert "tags" in tag_data, f"Model {model_id} missing 'tags'"
        assert "perfect_for" in tag_data, f"Model {model_id} missing 'perfect_for'"
        assert "difficulty" in tag_data, f"Model {model_id} missing 'difficulty'"
        assert "description" in tag_data, f"Model {model_id} missing 'description'"
        
        # Validate types
        assert isinstance(tag_data["tags"], list)
        assert isinstance(tag_data["perfect_for"], list)
        assert isinstance(tag_data["difficulty"], str)
        assert isinstance(tag_data["description"], str)
        
        # Validate difficulty values
        assert tag_data["difficulty"] in ["Легко", "Средне", "Сложно"], \
            f"Model {model_id} has invalid difficulty: {tag_data['difficulty']}"


def test_no_duplicate_popular_models():
    """Ensure no duplicates in popular models list."""
    tags_file = Path(__file__).parent.parent / "app" / "ui" / "content" / "model_marketing_tags.json"
    
    if not tags_file.exists():
        pytest.skip("model_marketing_tags.json not found")
    
    data = json.loads(tags_file.read_text(encoding="utf-8"))
    
    popular_models = data.get("popular_models", [])
    assert len(popular_models) == len(set(popular_models)), "Duplicate popular models found"


def test_popularity_module():
    """Test popularity.py module functions."""
    from app.ui.popularity import get_popular_models, is_popular
    
    popular = get_popular_models()
    
    assert isinstance(popular, list)
    assert len(popular) >= 5, "Should have at least 5 popular models"
    
    # Test is_popular function
    if popular:
        first_model = popular[0]
        assert is_popular(first_model), f"First popular model should return True: {first_model}"
        
        # Test non-popular
        assert not is_popular("non-existent-model-xyz-123")
