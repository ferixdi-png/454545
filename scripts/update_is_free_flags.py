#!/usr/bin/env python3
"""
Update is_free flags in SOURCE_OF_TRUTH based on TOP-5 cheapest models.

Uses pricing_contract to derive FREE tier deterministically.
"""

import json
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.payments.pricing_contract import PricingContract

# Paths
SOURCE_OF_TRUTH = Path("models/KIE_SOURCE_OF_TRUTH.json")


def update_is_free_flags():
    """Update is_free flags in SOURCE_OF_TRUTH."""
    print("🔄 Updating is_free flags...")
    
    # Derive FREE tier from pricing truth
    pc = PricingContract()
    pc.load_truth()
    free_models = set(pc.derive_free_tier(count=5))
    
    print(f"\n🆓 FREE tier (TOP-5 cheapest):")
    for i, mid in enumerate(sorted(free_models), 1):
        price = pc.get_price_rub(mid)
        print(f"  {i}. {mid}: {price}₽")
    
    if not SOURCE_OF_TRUTH.exists():
        print(f"❌ SOURCE_OF_TRUTH not found: {SOURCE_OF_TRUTH}")
        return
    
    with open(SOURCE_OF_TRUTH, "r", encoding="utf-8") as f:
        sot = json.load(f)
    
    models = sot.get("models", {})
    if not models:
        print("❌ No models found in SOURCE_OF_TRUTH")
        return
    
    updated_count = 0
    cleared_count = 0
    
    for model_id, model_data in models.items():
        # Set is_free for TOP-5 cheapest
        if model_id in free_models:
            if "pricing" not in model_data:
                model_data["pricing"] = {}
            model_data["pricing"]["is_free"] = True
            updated_count += 1
            print(f"✅ {model_id}: is_free = True")
        else:
            # Clear is_free for others
            if "pricing" in model_data and "is_free" in model_data["pricing"]:
                if model_data["pricing"]["is_free"]:
                    model_data["pricing"]["is_free"] = False
                    cleared_count += 1
                    print(f"🔄 {model_id}: is_free = False (was True)")
    
    # Save back
    with open(SOURCE_OF_TRUTH, "w", encoding="utf-8") as f:
        json.dump(sot, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Updated {updated_count} models as free")
    print(f"🔄 Cleared {cleared_count} old free flags")
    print(f"📝 Saved: {SOURCE_OF_TRUTH}")


if __name__ == "__main__":
    update_is_free_flags()
