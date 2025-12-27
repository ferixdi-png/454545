#!/usr/bin/env python3
"""
Sync model pricing from Kie.ai API.

This script:
1. Fetches all models from Kie.ai API
2. Updates pricing information in source of truth
3. Marks models with confirmed pricing (is_pricing_known=True)
4. Removes disabled_reason for models with confirmed prices

Usage:
    python scripts/sync_kie_pricing.py [--dry-run]
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)


KIE_API_BASE = "https://api.kie.ai/v1"
SOURCE_OF_TRUTH = Path("models/kie_models_source_of_truth.json")


def get_kie_api_key() -> str:
    """Get Kie.ai API key from environment."""
    api_key = os.getenv("KIE_API_KEY")
    if not api_key:
        raise ValueError(
            "KIE_API_KEY environment variable not set. "
            "Set it with: export KIE_API_KEY='your-key-here'"
        )
    return api_key


async def fetch_kie_models(api_key: str) -> List[Dict[str, Any]]:
    """Fetch all models from Kie.ai API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{KIE_API_BASE}/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            response.raise_for_status()
            data = response.json()
            
            # API might return {"models": [...]} or just [...]
            if isinstance(data, dict):
                models = data.get("models", [])
            else:
                models = data
            
            print(f"✅ Fetched {len(models)} models from Kie.ai API")
            return models
        
        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP error: {e.response.status_code}")
            print(f"   Response: {e.response.text[:200]}")
            raise
        except Exception as e:
            print(f"❌ Error fetching models: {e}")
            raise


def load_source_of_truth() -> Dict[str, Any]:
    """Load current source of truth."""
    with open(SOURCE_OF_TRUTH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_source_of_truth(data: Dict[str, Any], dry_run: bool = False) -> None:
    """Save updated source of truth."""
    if dry_run:
        print("\n🔍 DRY RUN: Would save to", SOURCE_OF_TRUTH)
        return
    
    with open(SOURCE_OF_TRUTH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Saved to {SOURCE_OF_TRUTH}")


def sync_pricing(
    kie_models: List[Dict[str, Any]], 
    source_data: Dict[str, Any]
) -> tuple[int, int, int]:
    """
    Sync pricing from Kie.ai models to source of truth.
    
    Returns:
        (updated_count, confirmed_count, newly_enabled_count)
    """
    # Create lookup by model_id
    kie_by_id = {m.get("id") or m.get("model_id"): m for m in kie_models}
    
    updated_count = 0
    confirmed_count = 0
    newly_enabled_count = 0
    
    for model in source_data.get("models", []):
        model_id = model.get("model_id")
        if not model_id:
            continue
        
        # Find matching Kie.ai model
        kie_model = kie_by_id.get(model_id)
        if not kie_model:
            continue
        
        # Extract price from Kie.ai model
        kie_price = None
        
        # Try multiple price fields
        if "pricing" in kie_model:
            pricing = kie_model["pricing"]
            if isinstance(pricing, dict):
                kie_price = (
                    pricing.get("per_request") or
                    pricing.get("cost_usd") or
                    pricing.get("price_usd")
                )
            elif isinstance(pricing, (int, float)):
                kie_price = pricing
        
        if kie_price is None:
            kie_price = (
                kie_model.get("price_usd") or
                kie_model.get("price_per_use") or
                kie_model.get("cost")
            )
        
        if kie_price is None:
            continue  # No price in Kie.ai API
        
        # Update local model
        old_price = model.get("price")
        was_disabled = bool(model.get("disabled_reason"))
        
        if old_price != kie_price:
            print(f"  📝 {model_id}: ${old_price} → ${kie_price}")
            model["price"] = kie_price
            updated_count += 1
        
        # Mark as confirmed
        if not model.get("is_pricing_known"):
            model["is_pricing_known"] = True
            confirmed_count += 1
        
        # Remove disabled_reason if price is now confirmed
        if was_disabled and "disabled_reason" in model:
            del model["disabled_reason"]
            print(f"  ✅ {model_id}: ENABLED (price confirmed)")
            newly_enabled_count += 1
    
    return updated_count, confirmed_count, newly_enabled_count


async def main():
    parser = argparse.ArgumentParser(description="Sync model pricing from Kie.ai API")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without saving"
    )
    args = parser.parse_args()
    
    print("=" * 70)
    print("KIE.AI PRICING SYNC")
    print("=" * 70)
    
    # Load source of truth
    print("\n1. Loading source of truth...")
    source_data = load_source_of_truth()
    total_models = len(source_data.get("models", []))
    print(f"   ✅ Loaded {total_models} models")
    
    # Fetch Kie.ai models
    print("\n2. Fetching models from Kie.ai API...")
    try:
        api_key = get_kie_api_key()
        kie_models = await fetch_kie_models(api_key)
    except Exception as e:
        print(f"\n❌ Failed to fetch from Kie.ai: {e}")
        print("\nℹ️  Make sure KIE_API_KEY is set:")
        print("   export KIE_API_KEY='your-key-here'")
        return 1
    
    # Sync pricing
    print("\n3. Syncing pricing...")
    updated, confirmed, enabled = sync_pricing(kie_models, source_data)
    
    print("\n" + "=" * 70)
    print("SUMMARY:")
    print("=" * 70)
    print(f"  Prices updated:     {updated}")
    print(f"  Prices confirmed:   {confirmed}")
    print(f"  Models enabled:     {enabled}")
    
    # Save if not dry run
    save_source_of_truth(source_data, dry_run=args.dry_run)
    
    if args.dry_run:
        print("\n⚠️  DRY RUN - no changes saved")
        print("   Run without --dry-run to apply changes")
    else:
        print("\n✅ Sync complete!")
        print("\nNext steps:")
        print("  1. Review changes: git diff models/kie_models_source_of_truth.json")
        print("  2. Test: python scripts/audit_model_coverage.py")
        print("  3. Commit: git commit -m 'Sync pricing from Kie.ai API'")
    
    return 0


if __name__ == "__main__":
    import asyncio
    sys.exit(asyncio.run(main()))
