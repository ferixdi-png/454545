"""
Tests for FREE tier auto-derivation logic.

Ensures that FREE tier is always derived correctly from pricing truth.
"""
import pytest
from decimal import Decimal
from app.pricing.free_tier import (
    compute_top5_cheapest,
    validate_free_tier_override,
    get_free_tier_models
)


def test_compute_top5_cheapest_basic():
    """Test basic TOP-5 computation."""
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
    
    result = compute_top5_cheapest(model_registry, pricing_map, count=5)
    
    # Should be sorted by price ASC
    assert result == ["model-e", "model-f", "model-c", "model-b", "model-d"]


def test_compute_top5_cheapest_with_ties():
    """Test tie-breaking with alphabetical ordering."""
    model_registry = {
        "zebra": {"enabled": True},
        "apple": {"enabled": True},
        "banana": {"enabled": True},
        "cherry": {"enabled": True},
        "date": {"enabled": True},
    }
    
    pricing_map = {
        "zebra": Decimal("3.80"),
        "apple": Decimal("3.80"),
        "banana": Decimal("0.95"),
        "cherry": Decimal("3.80"),
        "date": Decimal("0.76"),
    }
    
    result = compute_top5_cheapest(model_registry, pricing_map, count=5)
    
    # date (0.76), banana (0.95), then alphabetical: apple, cherry, zebra
    assert result == ["date", "banana", "apple", "cherry", "zebra"]


def test_compute_top5_cheapest_skips_disabled():
    """Test that disabled models are excluded."""
    model_registry = {
        "model-a": {"enabled": True},
        "model-b": {"enabled": False},  # Disabled
        "model-c": {"enabled": True},
        "model-d": {"enabled": True},
        "model-e": {"enabled": True},
        "model-f": {"enabled": True},
    }
    
    pricing_map = {
        "model-a": Decimal("10.00"),
        "model-b": Decimal("0.10"),  # Cheapest but disabled
        "model-c": Decimal("5.00"),
        "model-d": Decimal("8.00"),
        "model-e": Decimal("3.00"),
        "model-f": Decimal("2.00"),
    }
    
    result = compute_top5_cheapest(model_registry, pricing_map, count=5)
    
    # model-b excluded
    assert "model-b" not in result
    assert result == ["model-f", "model-e", "model-c", "model-d", "model-a"]


def test_compute_top5_cheapest_skips_no_pricing():
    """Test that models without pricing are excluded."""
    model_registry = {
        "model-a": {"enabled": True},
        "model-b": {"enabled": True},  # No pricing
        "model-c": {"enabled": True},
        "model-d": {"enabled": True},
        "model-e": {"enabled": True},
        "model-f": {"enabled": True},
    }
    
    pricing_map = {
        "model-a": Decimal("10.00"),
        # model-b not in pricing_map
        "model-c": Decimal("5.00"),
        "model-d": Decimal("8.00"),
        "model-e": Decimal("3.00"),
        "model-f": Decimal("2.00"),
    }
    
    result = compute_top5_cheapest(model_registry, pricing_map, count=5)
    
    assert "model-b" not in result
    assert result == ["model-f", "model-e", "model-c", "model-d", "model-a"]


def test_compute_top5_cheapest_insufficient_models():
    """Test error when not enough eligible models."""
    model_registry = {
        "model-a": {"enabled": True},
        "model-b": {"enabled": True},
    }
    
    pricing_map = {
        "model-a": Decimal("10.00"),
        "model-b": Decimal("5.00"),
    }
    
    with pytest.raises(ValueError, match="Insufficient eligible models"):
        compute_top5_cheapest(model_registry, pricing_map, count=5)


def test_validate_free_tier_override_valid():
    """Test validation of valid override."""
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
    
    override = ["model-a", "model-b", "model-c", "model-d", "model-e"]
    
    is_valid, issues = validate_free_tier_override(
        override, model_registry, pricing_map, expected_count=5
    )
    
    assert is_valid
    assert len(issues) == 0


def test_validate_free_tier_override_wrong_count():
    """Test validation fails with wrong count."""
    model_registry = {
        "model-a": {"enabled": True},
        "model-b": {"enabled": True},
    }
    
    pricing_map = {
        "model-a": Decimal("10.00"),
        "model-b": Decimal("5.00"),
    }
    
    override = ["model-a", "model-b"]  # Only 2, need 5
    
    is_valid, issues = validate_free_tier_override(
        override, model_registry, pricing_map, expected_count=5
    )
    
    assert not is_valid
    assert any("exactly 5 models" in issue for issue in issues)


def test_validate_free_tier_override_missing_model():
    """Test validation fails with non-existent model."""
    model_registry = {
        "model-a": {"enabled": True},
        "model-b": {"enabled": True},
        "model-c": {"enabled": True},
    }
    
    pricing_map = {
        "model-a": Decimal("10.00"),
        "model-b": Decimal("5.00"),
        "model-c": Decimal("3.00"),
    }
    
    override = ["model-a", "model-b", "model-c", "model-d", "model-e"]
    
    is_valid, issues = validate_free_tier_override(
        override, model_registry, pricing_map, expected_count=5
    )
    
    assert not is_valid
    assert any("model-d" in issue and "not in registry" in issue for issue in issues)


def test_validate_free_tier_override_disabled_model():
    """Test validation fails with disabled model."""
    model_registry = {
        "model-a": {"enabled": True},
        "model-b": {"enabled": False},  # Disabled
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
    
    override = ["model-a", "model-b", "model-c", "model-d", "model-e"]
    
    is_valid, issues = validate_free_tier_override(
        override, model_registry, pricing_map, expected_count=5
    )
    
    assert not is_valid
    assert any("model-b" in issue and "disabled" in issue for issue in issues)


def test_get_free_tier_models_auto():
    """Test auto-computation when no override."""
    model_registry = {
        "model-a": {"enabled": True},
        "model-b": {"enabled": True},
        "model-c": {"enabled": True},
        "model-d": {"enabled": True},
        "model-e": {"enabled": True},
        "model-f": {"enabled": True},
    }
    
    pricing_map = {
        "model-a": Decimal("10.00"),
        "model-b": Decimal("5.00"),
        "model-c": Decimal("3.00"),
        "model-d": Decimal("8.00"),
        "model-e": Decimal("1.00"),
        "model-f": Decimal("2.00"),
    }
    
    result, is_override = get_free_tier_models(
        model_registry, pricing_map, override_env=None, count=5
    )
    
    assert not is_override
    assert result == ["model-e", "model-f", "model-c", "model-b", "model-d"]


def test_get_free_tier_models_with_override():
    """Test override usage."""
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
    
    override_env = "model-a,model-b,model-c,model-d,model-e"
    
    result, is_override = get_free_tier_models(
        model_registry, pricing_map, override_env=override_env, count=5
    )
    
    assert is_override
    assert result == ["model-a", "model-b", "model-c", "model-d", "model-e"]


def test_get_free_tier_models_invalid_override():
    """Test that invalid override raises error."""
    model_registry = {
        "model-a": {"enabled": True},
        "model-b": {"enabled": True},
        "model-c": {"enabled": True},
        "model-d": {"enabled": True},
        "model-e": {"enabled": True},
        "model-f": {"enabled": True},
    }
    
    pricing_map = {
        "model-a": Decimal("10.00"),
        "model-b": Decimal("5.00"),
        "model-c": Decimal("3.00"),
        "model-d": Decimal("8.00"),
        "model-e": Decimal("1.00"),
        "model-f": Decimal("2.00"),
    }
    
    override_env = "model-a,model-b"  # Only 2, need 5
    
    with pytest.raises(ValueError, match="FREE_TIER_MODEL_IDS override is invalid"):
        get_free_tier_models(
            model_registry, pricing_map, override_env=override_env, count=5
        )


def test_real_world_scenario():
    """Test with real pricing data scenario from logs."""
    model_registry = {
        "z-image": {"enabled": True},
        "recraft/remove-background": {"enabled": True},
        "infinitalk/from-audio": {"enabled": True},
        "google/imagen4": {"enabled": True},
        "google/imagen4-fast": {"enabled": True},
        "grok-imagine/text-to-image": {"enabled": True},
        "google/nano-banana": {"enabled": True},
    }
    
    pricing_map = {
        "z-image": Decimal("0.76"),
        "recraft/remove-background": Decimal("0.95"),
        "infinitalk/from-audio": Decimal("2.85"),
        "google/imagen4": Decimal("3.80"),
        "google/imagen4-fast": Decimal("3.80"),
        "grok-imagine/text-to-image": Decimal("3.80"),
        "google/nano-banana": Decimal("3.80"),
    }
    
    result = compute_top5_cheapest(model_registry, pricing_map, count=5)
    
    # Expected: z-image, recraft, infinitalk, then alphabetical tie at 3.80
    # google/imagen4, google/imagen4-fast (alphabet), NOT grok-imagine/text-to-image
    expected = [
        "z-image",
        "recraft/remove-background",
        "infinitalk/from-audio",
        "google/imagen4",
        "google/imagen4-fast",
    ]
    
    assert result == expected
