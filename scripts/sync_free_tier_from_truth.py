#!/usr/bin/env python3
"""
Sync FREE tier flags in SOURCE_OF_TRUTH with pricing truth.

This script:
1. Loads pricing_source_truth.txt
2. Computes TOP-5 cheapest models
3. Updates is_free flags in models/KIE_SOURCE_OF_TRUTH.json
4. Updates config.py default (if needed)

Run after changing pricing_source_truth.txt to keep repo consistent.
"""
import json
import logging
import sys
from pathlib import Path
from decimal import Decimal
from typing import Dict, List

# Add project root to path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
SOURCE_OF_TRUTH_PATH = REPO_ROOT / "models" / "KIE_SOURCE_OF_TRUTH.json"
CONFIG_PATH = REPO_ROOT / "app" / "utils" / "config.py"


def load_pricing_and_compute_free_tier() -> List[str]:
    """Load pricing contract and compute FREE tier."""
    from app.payments.pricing_contract import get_pricing_contract
    from app.pricing.free_tier import compute_top5_cheapest
    
    pc = get_pricing_contract()
    pc.load_truth()
    
    # Build pricing map for free_tier module
    pricing_map = {mid: Decimal(str(rub)) for mid, (usd, rub) in pc._pricing_map.items()}
    
    # Load SOURCE_OF_TRUTH
    with open(SOURCE_OF_TRUTH_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    models_dict = data.get("models", {})
    
    # Compute FREE tier
    free_tier = compute_top5_cheapest(models_dict, pricing_map, count=5)
    
    logger.info(f"Computed FREE tier (TOP-5 cheapest): {free_tier}")
    return free_tier


def update_is_free_flags(free_tier: List[str]) -> Dict[str, int]:
    """Update is_free flags in SOURCE_OF_TRUTH.json."""
    with open(SOURCE_OF_TRUTH_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    models_dict = data.get("models", {})
    free_tier_set = set(free_tier)
    
    updated_to_free = 0
    cleared_old_free = 0
    
    for model_id, model_data in models_dict.items():
        if not isinstance(model_data, dict):
            continue
        
        pricing = model_data.get("pricing", {})
        current_is_free = pricing.get("is_free", False)
        should_be_free = model_id in free_tier_set
        
        if should_be_free and not current_is_free:
            pricing["is_free"] = True
            updated_to_free += 1
            logger.info(f"  ✅ Set {model_id} -> is_free=True")
        elif not should_be_free and current_is_free:
            pricing["is_free"] = False
            cleared_old_free += 1
            logger.info(f"  🔄 Set {model_id} -> is_free=False")
    
    # Write back
    with open(SOURCE_OF_TRUTH_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
    
    logger.info(
        f"Updated SOURCE_OF_TRUTH: {updated_to_free} set to free, "
        f"{cleared_old_free} cleared"
    )
    
    return {"updated": updated_to_free, "cleared": cleared_old_free}


def update_config_default(free_tier: List[str]) -> bool:
    """Update config.py default FREE tier (informational only)."""
    config_text = CONFIG_PATH.read_text(encoding='utf-8')
    
    # Find default_free line
    new_value = ','.join(free_tier)
    
    # Pattern: default_free = "..."
    import re
    pattern = r'default_free\s*=\s*["\']([^"\']*)["\']'
    match = re.search(pattern, config_text)
    
    if not match:
        logger.warning("Could not find default_free in config.py")
        return False
    
    old_value = match.group(1)
    
    if old_value == new_value:
        logger.info("config.py default_free already up to date")
        return False
    
    # Replace
    new_text = config_text.replace(
        f'default_free = "{old_value}"',
        f'default_free = "{new_value}"'
    )
    
    CONFIG_PATH.write_text(new_text, encoding='utf-8')
    logger.info(f"Updated config.py: default_free = \"{new_value}\"")
    return True


def main():
    logger.info("🔄 Syncing FREE tier from pricing truth...")
    
    # 1. Compute FREE tier
    free_tier = load_pricing_and_compute_free_tier()
    
    # 2. Update is_free flags
    stats = update_is_free_flags(free_tier)
    
    # 3. Update config.py default
    config_updated = update_config_default(free_tier)
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("✅ FREE tier sync complete:")
    logger.info(f"  - FREE tier: {free_tier}")
    logger.info(f"  - SOURCE_OF_TRUTH: {stats['updated']} updated, {stats['cleared']} cleared")
    logger.info(f"  - config.py: {'updated' if config_updated else 'already up to date'}")
    logger.info("="*60)
    logger.info("\nNext: git commit -m 'Sync FREE tier flags with pricing truth'")


if __name__ == "__main__":
    main()
