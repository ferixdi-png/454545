"""
SAFE TEST MODE configuration.

Prevents overspending during testing by limiting which models can be used.
"""
import os
import logging
from typing import List
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# ENV variable to enable/disable safe mode
SAFE_TEST_MODE = os.getenv("SAFE_TEST_MODE", "1") == "1"

# Maximum cost per single test run (in RUB)
MAX_TEST_COST_PER_RUN = float(os.getenv("MAX_TEST_COST_PER_RUN", "5.0"))

# Maximum total budget for all smoke tests (in RUB)
MAX_TOTAL_TEST_BUDGET = float(os.getenv("MAX_TOTAL_TEST_BUDGET", "50.0"))

# In safe mode, only test TOP-N cheapest models
SAFE_MODE_MAX_MODELS = int(os.getenv("SAFE_MODE_MAX_MODELS", "10"))

SOURCE_OF_TRUTH = Path("models/KIE_SOURCE_OF_TRUTH.json")


def is_safe_test_mode() -> bool:
    """Check if safe test mode is enabled."""
    return SAFE_TEST_MODE


def get_safe_test_models() -> List[str]:
    """
    Get list of models safe for testing.
    
    Returns:
        List of model_ids that are within safe budget limits
    """
    if not SAFE_TEST_MODE:
        logger.info("SAFE_TEST_MODE disabled, all models available")
        return []
    
    try:
        with open(SOURCE_OF_TRUTH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        models = data.get("models", [])
        
        if not models:
            logger.warning("No models in source of truth")
            return []
        
        # Filter by cost
        safe_models = [
            m for m in models
            if m.get("enabled", True)
            and m.get("pricing", {}).get("rub_per_gen", float('inf')) <= MAX_TEST_COST_PER_RUN
        ]
        
        # Sort by price (cheapest first)
        safe_models.sort(key=lambda m: m.get("pricing", {}).get("rub_per_gen", 0))
        
        # Take TOP-N
        safe_models = safe_models[:SAFE_MODE_MAX_MODELS]
        
        safe_model_ids = [m["model_id"] for m in safe_models]
        
        logger.info(f"SAFE_TEST_MODE enabled: {len(safe_model_ids)} models allowed")
        for m in safe_models:
            price = m.get("pricing", {}).get("rub_per_gen", 0)
            logger.info(f"  ✓ {m['model_id']}: {price} RUB")
        
        return safe_model_ids
    
    except Exception as e:
        logger.error(f"Failed to load safe test models: {e}")
        return []


def is_model_safe_for_testing(model_id: str) -> bool:
    """
    Check if model is safe to use in testing.
    
    Args:
        model_id: Model tech ID
    
    Returns:
        True if model can be used in tests, False otherwise
    """
    if not SAFE_TEST_MODE:
        return True
    
    safe_models = get_safe_test_models()
    is_safe = model_id in safe_models
    
    if not is_safe:
        logger.warning(
            f"Model {model_id} blocked by SAFE_TEST_MODE "
            f"(max cost: {MAX_TEST_COST_PER_RUN} RUB)"
        )
    
    return is_safe


def get_test_budget_info() -> dict:
    """
    Get current test budget configuration.
    
    Returns:
        {
            "safe_mode_enabled": bool,
            "max_cost_per_run": float (RUB),
            "max_total_budget": float (RUB),
            "max_models": int,
            "allowed_models": List[str]
        }
    """
    return {
        "safe_mode_enabled": SAFE_TEST_MODE,
        "max_cost_per_run": MAX_TEST_COST_PER_RUN,
        "max_total_budget": MAX_TOTAL_TEST_BUDGET,
        "max_models": SAFE_MODE_MAX_MODELS,
        "allowed_models": get_safe_test_models() if SAFE_TEST_MODE else ["ALL"]
    }


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    print("="*60)
    print("SAFE TEST MODE CONFIGURATION")
    print("="*60)
    print()
    
    info = get_test_budget_info()
    
    print(f"Safe mode enabled: {info['safe_mode_enabled']}")
    print(f"Max cost per run: {info['max_cost_per_run']} RUB")
    print(f"Max total budget: {info['max_total_budget']} RUB")
    print(f"Max models: {info['max_models']}")
    print()
    print(f"Allowed models ({len(info['allowed_models'])}):")
    for model_id in info['allowed_models']:
        print(f"  • {model_id}")
    print()
    print("="*60)
