"""
Free Tier Auto-Derivation - Single Source of Truth

FREE tier = TOP-5 cheapest ENABLED models by BASE RUB price (without markup).

INVARIANTS:
- Source: models/pricing_source_truth.txt (USD prices, no markup)
- Computation: BASE_RUB = USD × FX_RATE (no markup applied)
- User sees: USER_RUB = BASE_RUB × PRICING_MARKUP (applied separately)
- Eligibility: model.enabled == True AND model_id in pricing_map
- Sorting: base_rub ASC, then model_id ASC (deterministic tie-breaking)
- Count: Exactly 5 models

USAGE:
    from app.pricing.free_tier import compute_top5_cheapest
    
    free_models = compute_top5_cheapest(model_registry, pricing_map)
    # Returns: ['z-image', 'recraft/remove-background', ...]
    # pricing_map contains BASE RUB prices (before markup)
"""
import logging
from typing import Dict, List, Any
from decimal import Decimal

logger = logging.getLogger(__name__)


def compute_top5_cheapest(
    model_registry: Dict[str, Any],
    pricing_map: Dict[str, Decimal],
    count: int = 5
) -> List[str]:
    """
    Compute TOP-N cheapest ENABLED models by BASE RUB price (no markup).
    
    Args:
        model_registry: Dict of model_id -> model_data (from SOURCE_OF_TRUTH)
        pricing_map: Dict of model_id -> BASE_price_rub (no markup applied)
        count: Number of models in FREE tier (default: 5)
    
    Returns:
        List of model_ids, sorted by (base_price_rub ASC, model_id ASC)
    
    Raises:
        ValueError: If insufficient models to form FREE tier
    """
    # Collect eligible models
    eligible = []
    
    for model_id, model_data in model_registry.items():
        # Check if model is enabled
        if not isinstance(model_data, dict):
            continue
        
        if not model_data.get('enabled', True):
            continue
        
        # Check if model has pricing
        if model_id not in pricing_map:
            logger.warning(f"Model {model_id} enabled but no price in pricing_map")
            continue
        
        price_rub = pricing_map[model_id]
        eligible.append((model_id, price_rub))
    
    if len(eligible) < count:
        raise ValueError(
            f"Insufficient eligible models for FREE tier: "
            f"need {count}, got {len(eligible)}"
        )
    
    # Sort by (price, model_id) for deterministic ordering
    eligible.sort(key=lambda x: (x[1], x[0]))
    
    # Return top N model IDs
    top_n = [model_id for model_id, _ in eligible[:count]]
    
    logger.info(
        f"Computed TOP-{count} cheapest models: {top_n} "
        f"(prices: {[float(eligible[i][1]) for i in range(count)]})"
    )
    
    return top_n


def validate_free_tier_override(
    override_ids: List[str],
    model_registry: Dict[str, Any],
    pricing_map: Dict[str, Decimal],
    expected_count: int = 5
) -> tuple[bool, List[str]]:
    """
    Validate FREE_TIER_MODEL_IDS override.
    
    Args:
        override_ids: List of model_ids from ENV
        model_registry: Model registry
        pricing_map: Pricing map
        expected_count: Expected count (default: 5)
    
    Returns:
        (is_valid, issues_list)
    """
    issues = []
    
    # Check count
    if len(override_ids) != expected_count:
        issues.append(
            f"FREE_TIER_MODEL_IDS must have exactly {expected_count} models, "
            f"got {len(override_ids)}"
        )
    
    # Check all models exist and are enabled
    for model_id in override_ids:
        if model_id not in model_registry:
            issues.append(f"Model '{model_id}' not in registry")
            continue
        
        model_data = model_registry[model_id]
        if not model_data.get('enabled', True):
            issues.append(f"Model '{model_id}' is disabled")
        
        if model_id not in pricing_map:
            issues.append(f"Model '{model_id}' has no price")
    
    return len(issues) == 0, issues


def get_free_tier_models(
    model_registry: Dict[str, Any],
    pricing_map: Dict[str, Decimal],
    override_env: str = None,
    count: int = 5
) -> tuple[List[str], bool]:
    """
    Get FREE tier models (auto-computed or from ENV override).
    
    Args:
        model_registry: Model registry
        pricing_map: Pricing map
        override_env: Value from FREE_TIER_MODEL_IDS env (or None)
        count: Expected count
    
    Returns:
        (free_tier_ids, is_override)
    
    Raises:
        ValueError: If override is invalid or cannot compute FREE tier
    """
    # If no override, compute and return
    if not override_env or not override_env.strip():
        expected = compute_top5_cheapest(model_registry, pricing_map, count)
        logger.info(f"FREE tier: auto-computed (TOP-{count} cheapest)")
        return expected, False
    
    # Parse override
    override_ids = [x.strip() for x in override_env.split(',') if x.strip()]
    
    # Validate override FIRST (before computing expected)
    is_valid, issues = validate_free_tier_override(
        override_ids, model_registry, pricing_map, count
    )
    
    if not is_valid:
        error_msg = "FREE_TIER_MODEL_IDS override is invalid:\n"
        for issue in issues:
            error_msg += f"  - {issue}\n"
        
        # Try to compute expected for helpful error message
        try:
            expected = compute_top5_cheapest(model_registry, pricing_map, count)
            error_msg += f"\nExpected (TOP-{count} cheapest): {expected}\n"
        except ValueError:
            error_msg += f"\n(Cannot compute TOP-{count} cheapest - insufficient models)\n"
        
        error_msg += f"Got: {override_ids}"
        raise ValueError(error_msg)
    
    # Compute expected for comparison logging
    try:
        expected = compute_top5_cheapest(model_registry, pricing_map, count)
    except ValueError as e:
        # If we can't compute expected, but override is valid, use override
        logger.warning(f"Cannot compute expected FREE tier: {e}")
        logger.info(f"Using override: {override_ids}")
        return override_ids, True
    
    # Check if override differs from expected
    if set(override_ids) != set(expected):
        logger.warning(
            f"FREE_TIER_MODEL_IDS override differs from TOP-{count} cheapest:\n"
            f"  Expected: {expected}\n"
            f"  Override: {override_ids}"
        )
    else:
        logger.info(f"FREE_TIER_MODEL_IDS override matches TOP-{count} cheapest")
    
    return override_ids, True
