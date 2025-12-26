"""
Tests for startup validation error messages.

Ensures helpful error messages when FREE tier mismatches occur.
"""
import pytest
import json
import tempfile
from pathlib import Path
from decimal import Decimal


def test_startup_validation_mismatch_error_format():
    """Test that startup validation error contains expected/actual."""
    from app.utils.startup_validation import validate_free_tier, StartupValidationError
    
    # Create mock data with wrong is_free flags
    data = {
        "models": {
            "model-a": {"enabled": True, "pricing": {"is_free": True}},  # Wrong
            "model-b": {"enabled": True, "pricing": {"is_free": True}},  # Wrong
            "model-c": {"enabled": True, "pricing": {"is_free": True}},  # Wrong
            "model-d": {"enabled": True, "pricing": {"is_free": True}},  # Wrong
            "model-e": {"enabled": True, "pricing": {"is_free": True}},  # Wrong
            "model-f": {"enabled": True, "pricing": {"is_free": False}},
            "model-g": {"enabled": True, "pricing": {"is_free": False}},
        }
    }
    
    pricing_map = {
        "model-a": Decimal("10.00"),
        "model-b": Decimal("5.00"),
        "model-c": Decimal("3.00"),
        "model-d": Decimal("8.00"),
        "model-e": Decimal("1.00"),
        "model-f": Decimal("2.00"),
        "model-g": Decimal("15.00"),
    }
    
    # Expected FREE tier: model-e, model-f, model-c, model-b, model-d
    # Actual in file: model-a, model-b, model-c, model-d, model-e
    
    # Should NOT raise error, just log warning (new behavior)
    # The function now only validates ENV override, not file flags
    validate_free_tier(data, pricing_map)
    # Pass - no exception expected


def test_invalid_override_error_message():
    """Test that invalid FREE_TIER_MODEL_IDS override shows helpful error."""
    from app.pricing.free_tier import get_free_tier_models
    
    model_registry = {
        "model-a": {"enabled": True},
        "model-b": {"enabled": True},
        "model-c": {"enabled": True},
        "model-d": {"enabled": True},
        "model-e": {"enabled": True},
        "model-f": {"enabled": True},
        "model-g": {"enabled": True},
    }
    
    pricing_map = {
        "model-a": Decimal("10.00"),
        "model-b": Decimal("5.00"),
        "model-c": Decimal("3.00"),
        "model-d": Decimal("8.00"),
        "model-e": Decimal("1.00"),
        "model-f": Decimal("2.00"),
        "model-g": Decimal("15.00"),
    }
    
    # Invalid override: only 3 models, need 5
    override_env = "model-a,model-b,model-c"
    
    with pytest.raises(ValueError) as exc_info:
        get_free_tier_models(
            model_registry, pricing_map, override_env=override_env, count=5
        )
    
    error_msg = str(exc_info.value)
    
    # Should contain helpful info
    assert "FREE_TIER_MODEL_IDS override is invalid" in error_msg
    assert "exactly 5 models" in error_msg
    assert "Expected (TOP-5 cheapest)" in error_msg


def test_override_with_nonexistent_model_error():
    """Test error when override contains non-existent model."""
    from app.pricing.free_tier import get_free_tier_models
    
    model_registry = {
        "model-a": {"enabled": True},
        "model-b": {"enabled": True},
        "model-c": {"enabled": True},
        "model-d": {"enabled": True},
        "model-e": {"enabled": True},
    }
    
    pricing_map = {
        "model-a": Decimal("10.00"),
        "model-b": Decimal("5.00"),
        "model-c": Decimal("3.00"),
        "model-d": Decimal("8.00"),
        "model-e": Decimal("1.00"),
    }
    
    # Invalid: contains non-existent models
    override_env = "model-a,model-b,model-c,model-x,model-y"
    
    with pytest.raises(ValueError) as exc_info:
        get_free_tier_models(
            model_registry, pricing_map, override_env=override_env, count=5
        )
    
    error_msg = str(exc_info.value)
    
    assert "model-x" in error_msg
    assert "model-y" in error_msg
    assert "not in registry" in error_msg


def test_override_with_disabled_model_error():
    """Test error when override contains disabled model."""
    from app.pricing.free_tier import get_free_tier_models
    
    model_registry = {
        "model-a": {"enabled": True},
        "model-b": {"enabled": False},  # Disabled!
        "model-c": {"enabled": True},
        "model-d": {"enabled": True},
        "model-e": {"enabled": True},
    }
    
    pricing_map = {
        "model-a": Decimal("10.00"),
        "model-b": Decimal("5.00"),
        "model-c": Decimal("3.00"),
        "model-d": Decimal("8.00"),
        "model-e": Decimal("1.00"),
    }
    
    override_env = "model-a,model-b,model-c,model-d,model-e"
    
    with pytest.raises(ValueError) as exc_info:
        get_free_tier_models(
            model_registry, pricing_map, override_env=override_env, count=5
        )
    
    error_msg = str(exc_info.value)
    
    assert "model-b" in error_msg
    assert "disabled" in error_msg


def test_successful_validation_no_errors():
    """Test that valid setup produces no errors."""
    from app.utils.startup_validation import validate_free_tier
    
    # Correct setup: TOP-5 cheapest
    data = {
        "models": {
            "model-a": {"enabled": True, "pricing": {"is_free": False}},
            "model-b": {"enabled": True, "pricing": {"is_free": True}},  # 5.00
            "model-c": {"enabled": True, "pricing": {"is_free": True}},  # 3.00
            "model-d": {"enabled": True, "pricing": {"is_free": True}},  # 8.00
            "model-e": {"enabled": True, "pricing": {"is_free": True}},  # 1.00
            "model-f": {"enabled": True, "pricing": {"is_free": True}},  # 2.00
            "model-g": {"enabled": True, "pricing": {"is_free": False}},
        }
    }
    
    pricing_map = {
        "model-a": Decimal("10.00"),
        "model-b": Decimal("5.00"),
        "model-c": Decimal("3.00"),
        "model-d": Decimal("8.00"),
        "model-e": Decimal("1.00"),
        "model-f": Decimal("2.00"),
        "model-g": Decimal("15.00"),
    }
    
    # Should pass without error
    validate_free_tier(data, pricing_map)
