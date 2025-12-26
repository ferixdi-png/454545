#!/usr/bin/env python3
"""
Update is_free flags in SOURCE_OF_TRUTH based on TOP-5 cheapest models.

This ensures validation passes by marking exactly 5 cheapest models as free.
"""

import json
from pathlib import Path

# Paths
SOURCE_OF_TRUTH = Path("models/KIE_SOURCE_OF_TRUTH.json")

# Top-5 cheapest models (from pricing truth)
FREE_MODELS = [
    "z-image",
    "recraft/remove-background",
    "infinitalk/from-audio",
    "grok-imagine/text-to-image",
    "google/nano-banana"
]


def update_is_free_flags():
    """Update is_free flags in SOURCE_OF_TRUTH."""
    print("🔄 Updating is_free flags...")
    
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
        if model_id in FREE_MODELS:
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
