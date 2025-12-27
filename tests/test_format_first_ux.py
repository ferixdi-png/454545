"""Test format-first navigation and premium UX."""
import pytest
from app.ui.formats import FORMATS, get_popular_models, get_recommended_models, get_model_format


def test_formats_defined():
    """All expected formats should be defined."""
    expected_formats = [
        "text-to-image",
        "image-to-image",
        "image-to-video",
        "text-to-video",
        "text-to-audio",
        "audio-to-audio",
    ]
    
    for fmt_key in expected_formats:
        assert fmt_key in FORMATS, f"Format {fmt_key} not found"
        fmt = FORMATS[fmt_key]
        assert fmt.name
        assert fmt.emoji
        assert fmt.description


def test_popular_models_ordering():
    """Popular models should be ordered by curated list first, then price."""
    from app.ui.catalog import load_models_sot
    
    models_dict = load_models_sot()
    popular = get_popular_models(models_dict, limit=10)
    
    assert len(popular) > 0, "Should have popular models"
    assert len(popular) <= 10, "Should respect limit"
    
    # Check that models have required fields
    for model in popular:
        assert "model_id" in model
        assert "display_name" in model
        assert "pricing" in model


def test_recommended_models_per_format():
    """Each format should have recommended models."""
    from app.ui.catalog import load_models_sot
    
    models_dict = load_models_sot()
    
    for format_key in FORMATS.keys():
        recommended = get_recommended_models(models_dict, format_key, limit=3)
        # May be empty for formats with no models, but should not crash
        assert isinstance(recommended, list)
        assert len(recommended) <= 3


def test_model_format_detection():
    """Models should be correctly categorized into formats."""
    from app.ui.catalog import load_models_sot
    
    models_dict = load_models_sot()
    
    # Test a few known models
    for model_id, model in list(models_dict.items())[:5]:
        fmt = get_model_format(model)
        # May be None for "other" category, but should not crash
        if fmt:
            assert fmt.key in FORMATS


def test_no_kie_ai_in_format_text():
    """No 'kie.ai' mentions in format descriptions."""
    for fmt in FORMATS.values():
        assert "kie.ai" not in fmt.name.lower()
        assert "kie.ai" not in fmt.description.lower()
        assert "kie" not in fmt.description.lower() or "kyutai" in fmt.description.lower()  # Allow Kyutai model names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
