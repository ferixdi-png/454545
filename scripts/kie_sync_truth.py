#!/usr/bin/env python3
"""
Kie.ai Source of Truth Synchronization.

ARCHITECTURE DECISION:
- Kie.ai API не предоставляет публичный endpoint /models с полной информацией
- Kie.ai tech_id НЕ СТАБИЛЬНЫ и могут меняться
- models/kie_models_source_of_truth.json уже содержит 80 моделей с валидными ценами/схемами
- РЕШЕНИЕ: Source of Truth остаётся ручным/репозиторным, НЕ автоматическим

This script:
1. Validates existing source of truth
2. Optionally attempts to fetch models from Kie.ai API (if KIE_API_KEY set)
3. Reports discrepancies
4. Does NOT auto-overwrite - only reports

CRITICAL: Kie.ai pricing может меняться. Автоматическая синхронизация ОПАСНА.
         Любые изменения требуют ручной проверки и коммита.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import httpx
except ImportError:
    print("⚠️  httpx not installed, API sync disabled")
    print("   Run: pip install httpx")
    httpx = None


SOURCE_OF_TRUTH = Path("models/kie_models_source_of_truth.json")
USD_TO_RUB = 78.0  # Exchange rate
MARKUP = 2  # Price markup for users


def load_source_of_truth() -> Dict[str, Any]:
    """Load current source of truth."""
    if not SOURCE_OF_TRUTH.exists():
        raise FileNotFoundError(f"{SOURCE_OF_TRUTH} not found")
    
    with open(SOURCE_OF_TRUTH, 'r', encoding='utf-8') as f:
        return json.load(f)


async def fetch_kie_models_if_possible() -> Optional[List[Dict[str, Any]]]:
    """
    Try to fetch models from Kie.ai API if KIE_API_KEY is set.
    Returns None if API is unavailable or fails.
    """
    if not httpx:
        return None
    
    api_key = os.getenv("KIE_API_KEY")
    if not api_key:
        print("ℹ️  KIE_API_KEY not set, skipping API sync")
        return None
    
    base_url = os.getenv("KIE_BASE_URL", "https://api.kie.ai").rstrip("/")
    
    # Try multiple possible endpoints
    endpoints = [
        f"{base_url}/v1/models",
        f"{base_url}/api/v1/models",
        f"{base_url}/models",
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for endpoint in endpoints:
            try:
                print(f"   Trying {endpoint}...")
                response = await client.get(
                    endpoint,
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # API might return {"models": [...]} or just [...]
                    if isinstance(data, dict):
                        models = data.get("models", data.get("data", []))
                    else:
                        models = data
                    
                    if models:
                        print(f"   ✅ Fetched {len(models)} models from {endpoint}")
                        return models
                    
            except Exception as e:
                print(f"   ❌ {endpoint}: {e}")
                continue
    
    print("   ⚠️  No working API endpoint found")
    return None


def validate_source_of_truth(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate source of truth structure and data quality.
    Returns statistics.
    """
    models = data.get("models", [])
    
    stats = {
        "total": len(models),
        "with_tech_id": 0,
        "with_price": 0,
        "with_schema": 0,
        "pricing_static": 0,
        "pricing_quote": 0,
        "pricing_missing": 0,
        "schema_valid": 0,
        "disabled": 0,
    }
    
    issues = []
    
    for model in models:
        model_id = model.get("model_id", "unknown")
        
        # Check tech_id format
        if "/" in model_id:
            stats["with_tech_id"] += 1
        
        # Check price
        price = model.get("price")
        if price is not None and price > 0:
            stats["with_price"] += 1
            stats["pricing_static"] += 1
        elif model.get("pricing_mode") == "quote":
            stats["pricing_quote"] += 1
        else:
            stats["pricing_missing"] += 1
            if "/" in model_id:  # Only report for tech models
                issues.append(f"⚠️  {model_id}: No price")
        
        # Check schema
        schema = model.get("input_schema", {})
        if schema:
            stats["with_schema"] += 1
            
            # Validate schema structure
            if "required" in schema or "properties" in schema:
                stats["schema_valid"] += 1
            else:
                issues.append(f"⚠️  {model_id}: Invalid schema structure")
        else:
            if "/" in model_id:
                issues.append(f"⚠️  {model_id}: No schema")
        
        # Check disabled
        if model.get("disabled_reason"):
            stats["disabled"] += 1
    
    return stats, issues


def calculate_free_models(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Calculate top 5 cheapest models for free tier."""
    models_with_price = [
        m for m in data["models"]
        if m.get("price") and "/" in m.get("model_id", "")
    ]
    
    # Sort by RUB price
    models_sorted = sorted(
        models_with_price,
        key=lambda m: m["price"] * USD_TO_RUB * MARKUP
    )
    
    return models_sorted[:5]


async def main():
    parser = argparse.ArgumentParser(description="Validate and sync Kie.ai source of truth")
    parser.add_argument(
        "--check-api",
        action="store_true",
        help="Attempt to check Kie.ai API for updates"
    )
    args = parser.parse_args()
    
    print("=" * 80)
    print("KIE.AI SOURCE OF TRUTH VALIDATION")
    print("=" * 80)
    
    # Load source of truth
    print("\n1️⃣ Loading source of truth...")
    try:
        data = load_source_of_truth()
        print(f"   ✅ Loaded {SOURCE_OF_TRUTH}")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return 1
    
    # Validate
    print("\n2️⃣ Validating data quality...")
    stats, issues = validate_source_of_truth(data)
    
    print(f"\n   📊 STATISTICS:")
    print(f"      Total models:          {stats['total']}")
    print(f"      With tech_id (v/m):    {stats['with_tech_id']}")
    print(f"      With price:            {stats['with_price']}")
    print(f"      With valid schema:     {stats['schema_valid']}")
    print(f"      Disabled:              {stats['disabled']}")
    print(f"\n   💰 PRICING MODES:")
    print(f"      Static price:          {stats['pricing_static']}")
    print(f"      Quote mode:            {stats['pricing_quote']}")
    print(f"      Missing price:         {stats['pricing_missing']}")
    
    if issues:
        print(f"\n   ⚠️  ISSUES FOUND ({len(issues)}):")
        for issue in issues[:20]:  # Limit to first 20
            print(f"      {issue}")
        if len(issues) > 20:
            print(f"      ... and {len(issues) - 20} more")
    else:
        print(f"\n   ✅ No issues found")
    
    # Calculate free models
    print("\n3️⃣ Calculating free tier models...")
    free_models = calculate_free_models(data)
    print(f"\n   🆓 TOP 5 CHEAPEST (FREE TIER):")
    for idx, model in enumerate(free_models, 1):
        price_usd = model["price"]
        price_rub = price_usd * USD_TO_RUB * MARKUP
        print(f"      {idx}. {model['model_id']:<35} ${price_usd:<8.4f} → {price_rub:>8.2f}₽")
    
    # Optional API check
    if args.check_api:
        print("\n4️⃣ Checking Kie.ai API for updates...")
        kie_models = await fetch_kie_models_if_possible()
        
        if kie_models:
            print(f"   ✅ API returned {len(kie_models)} models")
            print(f"   ℹ️  Comparing with source of truth...")
            
            # Simple comparison by model_id
            kie_ids = {m.get("id") or m.get("model_id") for m in kie_models}
            our_ids = {m["model_id"] for m in data["models"] if "/" in m.get("model_id", "")}
            
            missing_in_api = our_ids - kie_ids
            new_in_api = kie_ids - our_ids
            
            if missing_in_api:
                print(f"\n   ⚠️  Models in our source but NOT in API ({len(missing_in_api)}):")
                for model_id in sorted(missing_in_api)[:10]:
                    print(f"      • {model_id}")
                if len(missing_in_api) > 10:
                    print(f"      ... and {len(missing_in_api) - 10} more")
            
            if new_in_api:
                print(f"\n   🆕 New models in API ({len(new_in_api)}):")
                for model_id in sorted(new_in_api)[:10]:
                    print(f"      • {model_id}")
                if len(new_in_api) > 10:
                    print(f"      ... and {len(new_in_api) - 10} more")
            
            if not missing_in_api and not new_in_api:
                print(f"   ✅ Source of truth is in sync with API")
        else:
            print(f"   ℹ️  API check skipped (no access or endpoint unavailable)")
    
    # Final summary
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    
    readiness = (
        stats["pricing_static"] >= 50 and
        stats["schema_valid"] >= 50 and
        stats["pricing_missing"] < 10
    )
    
    if readiness:
        print("✅ SOURCE OF TRUTH READY FOR PRODUCTION")
        print(f"\n   • {stats['pricing_static']} models with static pricing")
        print(f"   • {stats['schema_valid']} models with valid schemas")
        print(f"   • {len(free_models)} free tier models configured")
    else:
        print("⚠️  SOURCE OF TRUTH NEEDS ATTENTION")
        print(f"\n   Issues:")
        if stats["pricing_static"] < 50:
            print(f"   • Too few models with pricing: {stats['pricing_static']}")
        if stats["schema_valid"] < 50:
            print(f"   • Too few models with schemas: {stats['schema_valid']}")
        if stats["pricing_missing"] >= 10:
            print(f"   • Too many models without pricing: {stats['pricing_missing']}")
    
    print("\n" + "=" * 80)
    return 0 if readiness else 1


if __name__ == "__main__":
    import asyncio
    sys.exit(asyncio.run(main()))
