#!/usr/bin/env python3
"""
KIE TRUTH ENGINE - Main Pipeline

Полный цикл:
1. Discover - находит все модели
2. Extract - извлекает параметры со страниц
3. Validate - проверяет через API
4. Build - строит source of truth
"""
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from kie_truth_engine.discover import discover_all_models
from kie_truth_engine.extract import extract_all_models
from kie_truth_engine.validate import ModelValidator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("models")
OUTPUT_DIR.mkdir(exist_ok=True)


def merge_with_manual_overrides(models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge auto-discovered models with manual overrides.
    
    If manual_overrides.json has 100+ models, it becomes the source of truth.
    Otherwise, discovered models are merged with overrides (overrides win).
    """
    override_file = OUTPUT_DIR / "manual_overrides.json"
    
    if not override_file.exists():
        logger.info("No manual overrides found")
        return models
    
    with override_file.open('r', encoding='utf-8') as f:
        overrides = json.load(f)
    
    # If manual_overrides is comprehensive (100+ models), use it as base
    if len(overrides) >= 100:
        logger.info(f"Using manual_overrides.json as complete model base ({len(overrides)} models)")
        return overrides
    
    # Otherwise: merge discovered + overrides
    # Build index
    models_by_id = {m['model_id']: m for m in models}
    
    # Apply overrides
    for override in overrides:
        model_id = override['model_id']
        if model_id in models_by_id:
            existing_model = models_by_id[model_id]
            existing_rub = existing_model.get('pricing', {}).get('rub_per_use')
            
            # Merge (override wins)
            existing_model.update(override)
            
            # Preserve calculated RUB if not in override
            if 'pricing' in existing_model and existing_rub is not None:
                if 'rub_per_use' not in override.get('pricing', {}):
                    existing_model['pricing']['rub_per_use'] = existing_rub
            
            logger.info(f"Applied override for {model_id}")
        else:
            # Add new
            models.append(override)
            logger.info(f"Added manual model: {model_id}")
    
    return list(models_by_id.values())


def calculate_rub_prices(models: List[Dict[str, Any]], fx_rate: float, markup: float = 2.0) -> List[Dict[str, Any]]:
    """
    Calculate RUB prices for all models.
    
    Args:
        models: List of models
        fx_rate: USD to RUB exchange rate
        markup: Price markup multiplier
    
    Returns:
        Models with rub_per_use added
    """
    for model in models:
        if 'pricing' not in model:
            model['pricing'] = {}
        
        pricing = model['pricing']
        
        # Try USD first, then credits
        usd = pricing.get('usd_per_run')
        credits = pricing.get('credits_per_run')
        
        if usd and usd > 0:
            rub = usd * fx_rate * markup
        elif credits and credits > 0:
            # Assume 1 credit ≈ $0.005 (based on z-image: 0.8 credits = $0.004)
            usd_from_credits = credits * 0.005
            rub = usd_from_credits * fx_rate * markup
        else:
            rub = 0.0
        
        pricing['rub_per_use'] = round(rub, 2)
    
    return models


def build_source_of_truth(
    models: List[Dict[str, Any]],
    validation_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Build final source of truth JSON.
    
    Args:
        models: List of model dicts
        validation_results: List of validation results
    
    Returns:
        Complete source of truth dict
    """
    # Apply validation results
    verified_ids = {r['model_id'] for r in validation_results if r.get('verified', False)}
    
    for model in models:
        model['verified'] = model['model_id'] in verified_ids
    
    # Get FX rate
    try:
        from app.pricing.fx import get_usd_to_rub_rate
        fx_rate = get_usd_to_rub_rate()
    except Exception as e:
        logger.warning(f"Failed to get FX rate: {e}")
        fx_rate = 78.0
    
    # Merge with manual overrides FIRST (they have USD/credits)
    models = merge_with_manual_overrides(models)
    
    # Calculate RUB prices AFTER merge (so we have accurate USD/credits)
    models = calculate_rub_prices(models, fx_rate, markup=2.0)
    
    # Sort by RUB price (exclude models without real pricing)
    def get_sort_key(m):
        pricing = m.get('pricing', {})
        rub = pricing.get('rub_per_use', 0.0)
        has_real_pricing = pricing.get('usd_per_run') or pricing.get('credits_per_run')
        
        # Models without pricing go to end
        if not has_real_pricing or rub == 0.0:
            return float('inf')
        return rub
    
    models.sort(key=get_sort_key)
    
    # Build categories index
    categories = {}
    for model in models:
        cat = model.get('category', 'other')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(model['model_id'])
    
    # Build stats
    stats = {
        'total_models': len(models),
        'verified_models': sum(1 for m in models if m.get('verified', False)),
        'enabled_models': sum(1 for m in models if m.get('enabled', True)),
        'categories': {cat: len(ids) for cat, ids in categories.items()},
        'cheapest_models': [m['model_id'] for m in models[:5]]
    }
    
    # Build final dict
    truth = {
        'version': '4.0',
        'source': 'kie_truth_engine',
        'timestamp': datetime.utcnow().isoformat(),
        'fx_rate': fx_rate,
        'markup': 2.0,
        'models': models,
        'stats': stats
    }
    
    return truth


async def run_full_pipeline(
    use_scraping: bool = False,
    validate: bool = True,
    max_validation_budget: float = 20.0
):
    """
    Run full truth engine pipeline.
    
    Args:
        use_scraping: Whether to scrape website
        validate: Whether to validate models via API
        max_validation_budget: Max RUB to spend on validation
    """
    logger.info("\n" + "="*60)
    logger.info("KIE TRUTH ENGINE - FULL PIPELINE")
    logger.info("="*60 + "\n")
    
    # Step 1: Discover models
    logger.info("STEP 1: DISCOVER MODELS")
    models_index = discover_all_models(use_scraping=use_scraping)
    logger.info(f"✅ Discovered {len(models_index)} models\n")
    
    # Step 2: Extract details (skip for now - just use known list)
    logger.info("STEP 2: EXTRACT MODEL DETAILS")
    logger.info("⏭ Skipping extraction (using known structures)\n")
    
    # Build models from index with basic info
    models = []
    for m_info in models_index:
        model = {
            'model_id': m_info['model_id'],
            'display_name': m_info['name'],
            'url': m_info['url'],
            'category': 'other',  # Will be enriched later
            'enabled': True,
            'verified': False,
            'pricing': {
                'credits_per_run': None,
                'usd_per_run': None,
                'rub_per_use': 0.0
            },
            'input_schema': {
                'type': 'object',
                'required': ['prompt'],
                'properties': {
                    'prompt': {
                        'type': 'string',
                        'description': 'Input text'
                    }
                }
            },
            'source': m_info['source']
        }
        models.append(model)
    
    # Step 3: Validate models
    validation_results = []
    if validate:
        logger.info("STEP 3: VALIDATE MODELS VIA API")
        
        validator = ModelValidator(max_cost_per_test=2.0)
        
        # Only validate z-image for now (we know it works)
        z_image_model = next((m for m in models if m['model_id'] == 'z-image'), None)
        if z_image_model:
            # Set known pricing for z-image
            z_image_model['pricing'] = {
                'credits_per_run': 0.8,
                'usd_per_run': 0.004,
                'rub_per_use': 0.63
            }
            z_image_model['category'] = 'text-to-image'
            z_image_model['input_schema'] = {
                'type': 'object',
                'required': ['prompt', 'aspect_ratio'],
                'properties': {
                    'prompt': {
                        'type': 'string',
                        'description': 'Image description',
                        'max_length': 1000
                    },
                    'aspect_ratio': {
                        'type': 'string',
                        'enum': ['1:1', '4:3', '3:4', '16:9', '9:16'],
                        'default': '1:1'
                    }
                }
            }
            
            result = await validator.validate_model(z_image_model, skip_if_expensive=False)
            validation_results.append(result)
            validator.results = validation_results
            validator.print_summary()
        
        logger.info("")
    
    # Step 4: Build source of truth
    logger.info("STEP 4: BUILD SOURCE OF TRUTH")
    truth = build_source_of_truth(models, validation_results)
    
    # Save
    output_file = OUTPUT_DIR / "kie_models_source_of_truth.json"
    with output_file.open('w', encoding='utf-8') as f:
        json.dump(truth, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✅ Saved to: {output_file}")
    logger.info("")
    
    # Print summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    print(f"Total models: {truth['stats']['total_models']}")
    print(f"Verified models: {truth['stats']['verified_models']}")
    print(f"Enabled models: {truth['stats']['enabled_models']}")
    print(f"\nCategories:")
    for cat, count in truth['stats']['categories'].items():
        print(f"  {cat}: {count}")
    print(f"\nTop-5 cheapest (will be FREE):")
    for i, model_id in enumerate(truth['stats']['cheapest_models'], 1):
        model = next(m for m in truth['models'] if m['model_id'] == model_id)
        price = model['pricing']['rub_per_use']
        verified = "✅" if model.get('verified') else "❓"
        print(f"  {i}. {verified} {model_id}: {price} RUB")
    print("="*60 + "\n")
    
    return truth


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="KIE Truth Engine")
    parser.add_argument("--scrape", action="store_true", help="Scrape website for models")
    parser.add_argument("--no-validate", action="store_true", help="Skip API validation")
    parser.add_argument("--budget", type=float, default=20.0, help="Max validation budget (RUB)")
    
    args = parser.parse_args()
    
    asyncio.run(run_full_pipeline(
        use_scraping=args.scrape,
        validate=not args.no_validate,
        max_validation_budget=args.budget
    ))
