#!/usr/bin/env python3
"""
Merge and sync KIE model registries

Takes kie_parsed_models.json (77 models, good pricing) as base
Enriches with data from site scraper when available
Produces clean, validated source_of_truth.json
"""

import json
from pathlib import Path
from typing import Dict, List, Any

# Input files
PARSED_MODELS = Path("/workspaces/5656/models/kie_parsed_models.json")
SITE_SCRAPED = Path("/workspaces/5656/models/kie_models_source_of_truth.json")

# Output
OUTPUT_FILE = Path("/workspaces/5656/models/kie_models_final_truth.json")


def load_parsed_models() -> List[Dict]:
    """Load models from parse_kie_pricing.py (good pricing data)"""
    
    print("📂 Loading kie_parsed_models.json...")
    
    with open(PARSED_MODELS, 'r') as f:
        data = json.load(f)
    
    models = data.get('models', [])
    print(f"   ✅ {len(models)} models with correct pricing")
    
    return models


def load_site_scraped() -> Dict[str, Dict]:
    """Load models from site scraper (good API data)"""
    
    if not SITE_SCRAPED.exists():
        print("   ⚠️  No site scraper data found")
        return {}
    
    print("📂 Loading site scraped data...")
    
    with open(SITE_SCRAPED, 'r') as f:
        data = json.load(f)
    
    models = data.get('models', [])
    
    # Index by model_id for quick lookup
    indexed = {}
    for m in models:
        model_id = m.get('model_id') or m.get('tech_model_id')
        if model_id:
            indexed[model_id] = m
    
    print(f"   ✅ {len(indexed)} models from site")
    
    return indexed


def merge_models(parsed: List[Dict], site_data: Dict[str, Dict]) -> List[Dict]:
    """Merge parsed models (pricing) with site data (API details)"""
    
    print("\n🔄 Merging data...")
    
    merged = []
    enriched_count = 0
    
    for model in parsed:
        model_id = model.get('model_id')
        
        # Start with parsed model (has correct pricing)
        final_model = model.copy()
        
        # Enrich with site data if available
        if model_id in site_data:
            site_model = site_data[model_id]
            
            # Add API endpoint data
            if site_model.get('endpoint_create'):
                final_model['endpoint_create'] = site_model['endpoint_create']
            
            if site_model.get('endpoint_record'):
                final_model['endpoint_record'] = site_model['endpoint_record']
            
            # Add request schema if better
            if site_model.get('request_schema'):
                # Merge schemas
                existing_schema = final_model.get('input_schema', {})
                site_schema = site_model['request_schema']
                
                # If site has more specific schema, use it
                if site_schema and len(str(site_schema)) > len(str(existing_schema)):
                    final_model['input_schema'] = site_schema
            
            # Add output type
            if site_model.get('output_type'):
                final_model['output_type'] = site_model['output_type']
            
            enriched_count += 1
        
        merged.append(final_model)
    
    print(f"   ✅ {enriched_count}/{len(parsed)} models enriched with site data")
    
    return merged


def identify_free_tier_models(models: List[Dict], count: int = 5) -> List[str]:
    """Identify N cheapest models for FREE tier"""
    
    print(f"\n💎 Identifying {count} cheapest models...")
    
    # Sort by price
    models_with_price = []
    
    for model in models:
        model_id = model.get('model_id')
        pricing = model.get('pricing', {})
        
        # Get price in credits
        credits = pricing.get('credits_per_generation', 0)
        
        if credits > 0:
            models_with_price.append({
                'model_id': model_id,
                'credits': credits,
                'rub': pricing.get('rub_per_generation', 0)
            })
    
    # Sort by credits
    models_with_price.sort(key=lambda x: x['credits'])
    
    cheapest = models_with_price[:count]
    cheapest_ids = [m['model_id'] for m in cheapest]
    
    print(f"\n   🏆 FREE TIER MODELS:")
    for i, m in enumerate(cheapest, 1):
        print(f"   {i}. {m['model_id']:40s} {m['credits']:6.1f} credits ({m['rub']:6.2f}₽)")
    
    return cheapest_ids


def save_final_truth(models: List[Dict], free_tier_ids: List[str]):
    """Save merged and validated data"""
    
    print(f"\n💾 Saving to {OUTPUT_FILE}...")
    
    # Mark free tier models
    for model in models:
        model['is_free_tier'] = model.get('model_id') in free_tier_ids
    
    output_data = {
        "version": "6.2.0",
        "source": "merged: kie_parsed_models.json + site_scraper",
        "total_models": len(models),
        "free_tier_count": len(free_tier_ids),
        "free_tier_models": free_tier_ids,
        "api_endpoint": "/api/v1/jobs/createTask",
        "models": models
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"   ✅ Saved {len(models)} models")
    print(f"   📊 File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")


def print_summary(models: List[Dict]):
    """Print final summary"""
    
    print("\n" + "="*80)
    print("📊 FINAL SUMMARY")
    print("="*80)
    
    print(f"\n✅ Total models: {len(models)}")
    
    # Count by category
    categories = {}
    with_pricing = 0
    with_schema = 0
    with_endpoint = 0
    
    for m in models:
        cat = m.get('category', 'unknown')
        categories[cat] = categories.get(cat, 0) + 1
        
        if m.get('pricing'):
            with_pricing += 1
        
        if m.get('input_schema'):
            with_schema += 1
        
        if m.get('endpoint_create'):
            with_endpoint += 1
    
    print(f"\n📂 By category:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"   • {cat:30s}: {count:3d} models")
    
    print(f"\n📊 Data completeness:")
    print(f"   💰 With pricing: {with_pricing}/{len(models)} ({100*with_pricing//len(models)}%)")
    print(f"   📝 With input schema: {with_schema}/{len(models)} ({100*with_schema//len(models)}%)")
    print(f"   🔗 With API endpoint: {with_endpoint}/{len(models)} ({100*with_endpoint//len(models)}%)")


def main():
    """Main sync workflow"""
    
    print("="*80)
    print("🔄 KIE MODELS SYNC - MERGING DATA SOURCES")
    print("="*80)
    print()
    
    # Load data
    parsed_models = load_parsed_models()
    site_data = load_site_scraped()
    
    # Merge
    merged_models = merge_models(parsed_models, site_data)
    
    # Identify FREE tier
    free_tier_ids = identify_free_tier_models(merged_models, count=5)
    
    # Save
    save_final_truth(merged_models, free_tier_ids)
    
    # Summary
    print_summary(merged_models)
    
    print("\n" + "="*80)
    print("✅ SYNC COMPLETE")
    print("="*80)
    print()
    print(f"📁 Output: {OUTPUT_FILE}")
    print(f"🎯 Next: Update app/kie/builder.py to use this file")
    print()


if __name__ == "__main__":
    main()
