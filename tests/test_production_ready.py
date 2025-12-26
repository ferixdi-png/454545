"""Production-ready smoke tests.

Tests critical production requirements:
- FREE tier has exactly 5 models
- Pricing validation (no zero prices for paid models)
- Startup validation passes
- Source of truth integrity
"""
import json
import pytest
from pathlib import Path


def test_free_tier_count():
    """FREE tier must have exactly 5 models."""
    sot_path = Path("models/KIE_SOURCE_OF_TRUTH.json")
    assert sot_path.exists(), "KIE_SOURCE_OF_TRUTH.json not found"
    
    data = json.loads(sot_path.read_text(encoding="utf-8"))
    models = data.get("models", {})
    
    free_models = [mid for mid, m in models.items() if m.get("is_free") is True]
    
    assert len(free_models) == 5, f"FREE tier must have exactly 5 models, found {len(free_models)}: {free_models}"


def test_free_tier_has_pricing():
    """FREE tier models must have valid pricing (not all zeros)."""
    sot_path = Path("models/KIE_SOURCE_OF_TRUTH.json")
    data = json.loads(sot_path.read_text(encoding="utf-8"))
    models = data.get("models", {})
    
    free_models = [mid for mid, m in models.items() if m.get("is_free") is True]
    
    for mid in free_models:
        model = models[mid]
        pricing = model.get("pricing", {})
        
        # Must have at least one pricing field > 0
        has_pricing = (
            pricing.get("rub_per_use", 0) > 0 or
            pricing.get("credits_per_gen", 0) > 0 or
            pricing.get("usd_per_use", 0) > 0
        )
        
        assert has_pricing, f"FREE model '{mid}' has no valid pricing (all zeros)"


def test_paid_models_have_pricing():
    """Paid models (not FREE, not truly_free) must have pricing > 0."""
    sot_path = Path("models/KIE_SOURCE_OF_TRUTH.json")
    data = json.loads(sot_path.read_text(encoding="utf-8"))
    models = data.get("models", {})
    
    # Models that are truly free on Kie.ai (not part of monetization)
    truly_free_models = {
        "infinitalk/from-audio",
        "flux-2/pro-image-to-image",
        "flux-2/flex-image-to-image",
        "flux-2/flex-text-to-image",
        "elevenlabs/audio-isolation"
    }
    
    zero_price_paid = []
    
    for mid, model in models.items():
        if model.get("is_free") is True:
            continue  # Skip FREE tier
        
        if mid in truly_free_models:
            continue  # Skip truly free Kie.ai models
        
        pricing = model.get("pricing", {})
        
        rub = pricing.get("rub_per_use", 0)
        usd = pricing.get("usd_per_use", 0)
        credits = pricing.get("credits_per_gen", 0) or pricing.get("credits_per_use", 0)
        
        if rub == 0 and usd == 0 and credits == 0:
            zero_price_paid.append(mid)
    
    assert len(zero_price_paid) == 0, f"PAID models with zero pricing: {zero_price_paid}"


def test_source_of_truth_schema():
    """Source of truth must have required structure."""
    sot_path = Path("models/KIE_SOURCE_OF_TRUTH.json")
    assert sot_path.exists(), "KIE_SOURCE_OF_TRUTH.json not found"
    
    data = json.loads(sot_path.read_text(encoding="utf-8"))
    
    assert "models" in data, "Source of truth must have 'models' key"
    assert isinstance(data["models"], dict), "models must be dict"
    
    models = data["models"]
    
    # Check sample model structure
    for mid, model in list(models.items())[:5]:  # Check first 5 models
        assert "model_id" in model, f"{mid}: missing model_id"
        assert "endpoint" in model, f"{mid}: missing endpoint"
        assert "pricing" in model, f"{mid}: missing pricing"
        assert "input_schema" in model, f"{mid}: missing input_schema"
        assert "category" in model, f"{mid}: missing category"


def test_free_tier_matches_config():
    """FREE tier in source_of_truth should match default config."""
    import os
    import sys
    
    # Set minimal env for config import
    os.environ.setdefault("KIE_API_KEY", "test")
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:test")
    
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    # Load source_of_truth
    sot_path = Path("models/KIE_SOURCE_OF_TRUTH.json")
    data = json.loads(sot_path.read_text(encoding="utf-8"))
    models = data.get("models", {})
    
    sot_free_ids = {mid for mid, m in models.items() if m.get("pricing", {}).get("is_free") is True}
    
    # Expected FREE tier from pricing truth
    from app.payments.pricing_contract import get_pricing_contract
    from app.pricing.free_tier import compute_top5_cheapest
    from decimal import Decimal
    
    pc = get_pricing_contract()
    pc.load_truth()
    pricing_map = {mid: Decimal(str(rub)) for mid, (usd, rub) in pc._pricing_map.items()}
    expected_free = set(compute_top5_cheapest(models, pricing_map, count=5))
    
    assert sot_free_ids == expected_free, (
        f"FREE tier mismatch:\n"
        f"SOT is_free flags: {sorted(sot_free_ids)}\n"
        f"Expected (TOP-5): {sorted(expected_free)}"
    )


def test_startup_validation_passes():
    """Startup validation must pass (critical for Render deployment)."""
    import os
    import sys
    
    # Set minimal env
    os.environ.setdefault("KIE_API_KEY", "test")
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:test")
    
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from app.utils.startup_validation import validate_startup
    
    # Should not raise any exception
    try:
        validate_startup()
    except Exception as e:
        pytest.fail(f"Startup validation failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
