"""
Tests for marketing menu and registry coverage.
"""
import pytest
from app.ui.marketing_menu import (
    MARKETING_CATEGORIES,
    build_ui_tree,
    load_registry,
    map_model_to_marketing_category,
    count_models_by_category
)


def test_marketing_categories_defined():
    """Test marketing categories are defined."""
    assert len(MARKETING_CATEGORIES) == 7
    
    # Check required fields
    for cat_key, cat_data in MARKETING_CATEGORIES.items():
        assert "emoji" in cat_data
        assert "title" in cat_data
        assert "desc" in cat_data
        assert "kie_categories" in cat_data


def test_load_registry():
    """Test registry loading."""
    registry = load_registry()
    assert isinstance(registry, list)


def test_build_ui_tree():
    """Test UI tree building."""
    tree = build_ui_tree()
    assert isinstance(tree, dict)
    assert len(tree) == 7
    
    # All marketing categories present
    for cat_key in MARKETING_CATEGORIES.keys():
        assert cat_key in tree


def test_count_models():
    """Test model counting."""
    counts = count_models_by_category()
    assert isinstance(counts, dict)
    
    # All counts should be >= 0
    for count in counts.values():
        assert count >= 0


def test_model_mapping():
    """Test model to category mapping."""
    # Test model with known category
    model = {
        "model_id": "test/model",
        "category": "t2i",
        "type": "model"
    }
    
    cat = map_model_to_marketing_category(model)
    assert cat == "visuals"  # t2i maps to visuals


def test_category_info():
    """Test category info retrieval."""
    from app.ui.marketing_menu import get_category_info
    
    info = get_category_info("video_creatives")
    assert info["emoji"] == "🎥"
    assert info["title"] == "Видео-креативы"
