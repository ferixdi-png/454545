"""
Tests for production-level pricing fixes (no double markup).
"""

import pytest


def test_no_double_markup_in_pricing_contract():
    """Ensure pricing_contract computes BASE RUB without markup"""
    from app.payments.pricing_contract import PricingContract
    
    pc = PricingContract(markup=2.0, fx_rate=100.0)
    
    # Test USD -> BASE RUB (should NOT apply markup)
    base_rub = pc.compute_rub_price(usd=1.0)
    
    # Expected: 1.0 USD * 100 FX = 100 RUB (no markup)
    assert float(base_rub) == 100.0, \
        f"BASE RUB should be 100₽, got {base_rub}₽ (markup should NOT be applied)"


def test_markup_applied_in_user_price():
    """Ensure markup is applied when showing user prices"""
    from app.payments.pricing import calculate_user_price
    import os
    
    # Set markup to 2.0
    os.environ["PRICING_MARKUP"] = "2.0"
    
    base_rub = 100.0
    user_price = calculate_user_price(base_rub)
    
    # Expected: 100 * 2.0 = 200
    assert user_price == 200.0, \
        f"User price should be 200₽ (100 * 2.0), got {user_price}₽"


def test_free_tier_uses_base_rub():
    """Ensure FREE tier is computed from BASE RUB (no markup)"""
    from app.pricing.free_tier import compute_top5_cheapest
    from decimal import Decimal
    
    model_registry = {
        "cheap-1": {"enabled": True},
        "cheap-2": {"enabled": True},
        "expensive-1": {"enabled": True},
    }
    
    # Pricing map should contain BASE RUB (no markup)
    pricing_map = {
        "cheap-1": Decimal("0.50"),    # BASE: 0.50₽
        "cheap-2": Decimal("0.75"),    # BASE: 0.75₽
        "expensive-1": Decimal("10.0"), # BASE: 10₽
    }
    
    top2 = compute_top5_cheapest(model_registry, pricing_map, count=2)
    
    assert top2 == ["cheap-1", "cheap-2"], \
        f"TOP-2 should be sorted by BASE RUB, got {top2}"


def test_pricing_contract_normalize_saves_base_rub():
    """Ensure normalized registry contains BASE RUB in rub_per_use"""
    from app.payments.pricing_contract import PricingContract
    import json
    import tempfile
    from pathlib import Path
    
    # Create temp truth file
    truth_content = "test-model: 1.00 USD\n"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tf:
        tf.write(truth_content)
        truth_path = Path(tf.name)
    
    # Create temp registry
    registry_content = {
        "models": {
            "test-model": {
                "model_id": "test-model",
                "enabled": True,
                "pricing": {}
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as rf:
        json.dump(registry_content, rf)
        registry_path = Path(rf.name)
    
    try:
        # Init contract with known values
        pc = PricingContract(markup=2.0, fx_rate=100.0, 
                            truth_file=truth_path, 
                            registry_file=registry_path)
        pc.load_truth()
        pc.normalize_registry()
        
        # Read normalized registry
        with open(registry_path, 'r') as f:
            normalized = json.load(f)
        
        pricing = normalized["models"]["test-model"]["pricing"]
        
        # Expected: 1.00 USD * 100 FX = 100 RUB (no markup)
        assert pricing["rub_per_use"] == 100.0, \
            f"rub_per_use should be BASE 100₽, got {pricing['rub_per_use']}₽"
        assert pricing["rub_per_gen"] == 100.0, \
            f"rub_per_gen should be BASE 100₽, got {pricing['rub_per_gen']}₽"
        
    finally:
        truth_path.unlink()
        registry_path.unlink()


def test_no_local_import_os_in_main_render():
    """Ensure no local 'import os' inside main() that shadows global"""
    from pathlib import Path
    
    main_render_path = Path(__file__).parent.parent / "main_render.py"
    
    with open(main_render_path, 'r') as f:
        content = f.read()
    
    # Check for global import at top
    lines = content.split('\n')
    has_global_import = any('import os' in line and not line.strip().startswith('#') 
                           for line in lines[:20])
    
    assert has_global_import, "main_render.py should have 'import os' at module level"
    
    # Check for local import inside async def main()
    # This would cause UnboundLocalError
    in_main_function = False
    for line in lines:
        if 'async def main(' in line:
            in_main_function = True
        elif in_main_function and 'import os' in line and not line.strip().startswith('#'):
            pytest.fail(
                f"Found local 'import os' inside main() at: {line.strip()}\n"
                "This shadows the global 'os' and causes UnboundLocalError"
            )
        elif in_main_function and line.strip().startswith('def ') and 'main' not in line:
            # Reached another function definition
            break


def test_model_sync_disabled_by_default():
    """Ensure model_sync returns 'disabled' when MODEL_SYNC_ENABLED=0"""
    import asyncio
    import os
    
    # Set disabled
    os.environ["MODEL_SYNC_ENABLED"] = "0"
    
    from app.tasks.model_sync import sync_models_once
    
    result = asyncio.run(sync_models_once())
    
    assert result["status"] == "disabled", \
        f"sync_models_once() should return status='disabled', got {result}"
    assert result["models_count"] == 0, \
        f"Should have 0 models when disabled, got {result['models_count']}"
