"""
Free models management - automatic TOP-5 cheapest selection.

RULES:
1. Free models = 5 cheapest models by base cost
2. Selection is AUTOMATIC based on pricing
3. NO manual hardcoding of free model IDs
4. Re-calculated on every source_of_truth update
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

# PRIMARY SOURCE OF TRUTH
SOURCE_OF_TRUTH = Path("models/KIE_SOURCE_OF_TRUTH.json")


def get_free_models() -> List[str]:
    """
    Get list of model_ids that are free to use.
    
    Returns TOP-5 cheapest models by is_free=True flag.
    
    Returns:
        List of model_ids (tech IDs)
    """
    if not SOURCE_OF_TRUTH.exists():
        logger.error(f"Source of truth not found: {SOURCE_OF_TRUTH}")
        return []
    
    try:
        with open(SOURCE_OF_TRUTH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        models_dict = data.get("models", {})
        
        # Фильтруем модели с is_free=True
        free_model_ids = [
            model_id
            for model_id, model in models_dict.items()
            if model.get('pricing', {}).get('is_free', False)
        ]
        
        logger.info(f"Loaded {len(free_model_ids)} free models from {SOURCE_OF_TRUTH}")
        return free_model_ids
        
    except Exception as e:
        logger.error(f"Failed to load free models: {e}")
        return []


def is_free_model(model_id: str) -> bool:
    """
    Check if model is free.
    
    Args:
        model_id: Tech model ID
    
    Returns:
        True if model is in TOP-5 cheapest
    """
    free_ids = get_free_models()
    return model_id in free_ids


def get_model_price(model_id: str) -> Dict[str, float]:
    """
    Get pricing for specific model.
    
    Args:
        model_id: Tech model ID
    
    Returns:
        {
            "usd_per_gen": float,
            "credits_per_gen": float,
            "rub_per_gen": float,
            "is_free": bool
        }
    """
    try:
        with open(SOURCE_OF_TRUTH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        models_dict = data.get("models", {})
        
        # Find model
        model = models_dict.get(model_id)
        
        if not model:
            logger.warning(f"Model not found: {model_id}")
            return {
                "usd_per_gen": 0.0,
                "credits_per_gen": 0.0,
                "rub_per_gen": 0.0,
                "is_free": False
            }
        
        pricing = model.get("pricing", {})
        is_free = is_free_model(model_id)
        
        return {
            "usd_per_gen": pricing.get("usd_per_gen", 0.0),
            "credits_per_gen": pricing.get("credits_per_gen", 0.0),
            "rub_per_gen": pricing.get("rub_per_gen", 0.0),
            "is_free": is_free
        }
    
    except Exception as e:
        logger.error(f"Failed to get price for {model_id}: {e}")
        return {
            "usd_per_gen": 0.0,
            "credits_per_gen": 0.0,
            "rub_per_gen": 0.0,
            "is_free": False
        }


def get_all_models_by_category() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get all models grouped by category.
    
    Returns:
        {
            "category_name": [
                {
                    "model_id": str,
                    "display_name": str,
                    "price_rub": float,
                    "is_free": bool
                },
                ...
            ],
            ...
        }
    """
    try:
        with open(SOURCE_OF_TRUTH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        models_dict = data.get("models", {})
        free_ids = get_free_models()
        
        by_category: Dict[str, List[Dict[str, Any]]] = {}
        
        for model_id, model in models_dict.items():
            if not model.get("enabled", True):
                continue
            
            category = model.get("category", "other")
            
            if category not in by_category:
                by_category[category] = []
            
            by_category[category].append({
                "model_id": model["model_id"],
                "display_name": model.get("display_name", model["model_id"]),
                "price_rub": model.get("pricing", {}).get("rub_per_gen", 0.0),
                "is_free": model["model_id"] in free_ids,
                "description": model.get("description", "")
            })
        
        # Sort each category by price
        for category in by_category:
            by_category[category].sort(key=lambda m: m["price_rub"])
        
        return by_category
    
    except Exception as e:
        logger.error(f"Failed to get models by category: {e}")
        return {}


def calculate_cost(model_id: str, quantity: int = 1) -> Dict[str, Any]:
    """
    Calculate cost for running model N times.
    
    Args:
        model_id: Tech model ID
        quantity: Number of runs (default: 1)
    
    Returns:
        {
            "model_id": str,
            "quantity": int,
            "price_per_use_rub": float,
            "total_rub": float,
            "is_free": bool
        }
    """
    pricing = get_model_price(model_id)
    
    price_per_use = pricing["rub_per_gen"]
    is_free = pricing["is_free"]
    
    # Free models cost nothing
    if is_free:
        total = 0.0
    else:
        total = price_per_use * quantity
    
    return {
        "model_id": model_id,
        "quantity": quantity,
        "price_per_use_rub": price_per_use,
        "total_rub": round(total, 2),
        "is_free": is_free
    }
