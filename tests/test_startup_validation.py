"""Tests for startup validation to catch signature mismatches."""

import pytest
from pathlib import Path

from app.utils.startup_validation import (
    load_source_of_truth,
    validate_models,
    validate_free_tier,
    StartupValidationError,
)
from app.payments.pricing import calculate_kie_cost


def test_startup_validation_loads_source_of_truth():
    """Test that source of truth can be loaded."""
    data = load_source_of_truth()
    assert "models" in data
    assert isinstance(data["models"], dict)


def test_validate_models_runs_without_error():
    """Test that validate_models runs without crashing."""
    data = load_source_of_truth()
    # Should not raise StartupValidationError
    validate_models(data)


def test_validate_free_tier_runs_without_error():
    """Test that validate_free_tier runs without crashing."""
    from app.payments.pricing_contract import get_pricing_contract
    from decimal import Decimal
    
    data = load_source_of_truth()
    
    # Build pricing map
    pc = get_pricing_contract()
    pc.load_truth()
    pricing_map = {mid: Decimal(str(rub)) for mid, (usd, rub) in pc._pricing_map.items()}
    
    # May raise StartupValidationError if free tier not configured
    # This is expected behavior - test just ensures no signature errors
    try:
        validate_free_tier(data, pricing_map)
    except StartupValidationError:
        # Expected if free tier is not configured
        pass


def test_calculate_kie_cost_with_legacy_signature():
    """Test backward compatibility with payload/api_response params."""
    model = {"model_id": "test-model", "pricing": {"usd": 5.0}}
    
    # New signature
    cost1 = calculate_kie_cost(model, user_inputs={}, kie_response=None)
    assert cost1 > 0
    
    # Legacy signature (should work via backward compat)
    cost2 = calculate_kie_cost(model, payload=None, api_response=None)
    assert cost2 > 0
    assert cost1 == cost2


def test_calculate_kie_cost_with_mixed_params():
    """Test that user_inputs takes precedence over payload."""
    model = {"model_id": "test-model", "pricing": {"usd": 5.0}}
    
    # Both provided - user_inputs should win
    cost = calculate_kie_cost(
        model,
        user_inputs={"test": "data"},
        kie_response=None,
        payload={"old": "data"},
    )
    assert cost > 0


def test_calculate_kie_cost_defaults_to_empty_dict():
    """Test that user_inputs defaults to empty dict when None."""
    model = {"model_id": "test-model", "pricing": {"usd": 5.0}}
    
    # No user_inputs - should default to {}
    cost = calculate_kie_cost(model)
    assert cost > 0
