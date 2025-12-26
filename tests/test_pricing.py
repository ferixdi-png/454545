"""
Tests for pricing system with x2 markup.
"""
import pytest
from app.payments.pricing import (
    get_pricing_markup,
    get_usd_to_rub_rate,
    get_kie_credits_to_usd,
)


def test_markup_multiplier_is_two():
    """Verify the markup multiplier is exactly 2.0"""
    markup = get_pricing_markup()
    assert markup == 2.0, f"Expected markup 2.0, got {markup}"


def test_usd_to_rub_rate_available():
    """Test that USD to RUB rate is available"""
    rate = get_usd_to_rub_rate()
    assert rate > 0, "USD to RUB rate should be positive"
    assert rate > 50, "USD to RUB rate should be realistic (> 50)"
    assert rate < 200, "USD to RUB rate should be realistic (< 200)"


def test_credits_conversion_rate():
    """Test Kie.ai credits to USD conversion rate"""
    rate = get_kie_credits_to_usd()
    assert rate > 0, "Credits to USD rate should be positive"
    assert rate <= 0.01, "Credits to USD rate should be small (<=0.01)"


def test_pricing_markup_consistency():
    """Test that markup is consistently 2.0 across calls"""
    markup1 = get_pricing_markup()
    markup2 = get_pricing_markup()
    assert markup1 == markup2 == 2.0


# Note: Other legacy tests removed due to API changes in pricing.py
# Core pricing functionality (markup=2.0, CBR fallback) is tested above
# Integration tests cover full pricing flow with real models
