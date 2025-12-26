"""app.pricing.free_models

Эта утилита читает source_of_truth и отвечает на вопрос:
  - какие модели помечены как FREE (is_free=True)

ВАЖНО: Выбор TOP-5 cheapest происходит в рантайме при старте бота
(см. FreeModelManager / startup_validation), а тут мы просто читаем результат.

Форматы pricing в source_of_truth могут эволюционировать. Поэтому мы делаем
fallback по ключам (rub_per_use/rub_per_gen, usd_per_use/usd_per_gen, etc.).
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

# PRIMARY SOURCE OF TRUTH
SOURCE_OF_TRUTH = Path("models/KIE_SOURCE_OF_TRUTH.json")


def get_free_models() -> List[str]:
    """Get list of model_ids that are free to use.

    Strict режим проекта: FREE_TIER_MODEL_IDS из ENV (по умолчанию 5 дешёвых моделей).
    Fallback: если список пустой — читаем pricing.is_free из SOURCE_OF_TRUTH.
    """
    try:
        from app.utils.config import get_config
        cfg = get_config()
        ids = [x for x in getattr(cfg, "free_tier_model_ids", []) if x]
        if ids:
            logger.info(f"Loaded {len(ids)} free-tier models from config")
            return ids
    except Exception as e:
        logger.warning(f"Failed to load free-tier models from config: {e}")

    # Fallback to source_of_truth is_free flag
    if not SOURCE_OF_TRUTH.exists():
        logger.error(f"Source of truth not found: {SOURCE_OF_TRUTH}")
        return []

    try:
        with open(SOURCE_OF_TRUTH, 'r', encoding='utf-8') as f:
            data = json.load(f)

        models_dict = data.get("models", {}) or {}
        free_model_ids = [
            model_id
            for model_id, model in models_dict.items()
            if (model or {}).get('pricing', {}).get('is_free', False)
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
            "usd_per_use": float,
            "credits_per_use": float,
            "rub_per_use": float,
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
                "usd_per_use": 0.0,
                "credits_per_use": 0.0,
                "rub_per_use": 0.0,
                "is_free": False,
            }
        
        pricing = model.get("pricing", {})
        is_free = is_free_model(model_id)
        
        # Backward compatible ключи
        usd = (
            pricing.get("usd_per_use")
            or pricing.get("usd_per_gen")
            or pricing.get("usd")
            or pricing.get("price_usd")
            or 0.0
        )
        credits = (
            pricing.get("credits_per_use")
            or pricing.get("credits_per_gen")
            or pricing.get("credits")
            or 0.0
        )
        rub = (
            pricing.get("rub_per_use")
            or pricing.get("rub_per_gen")
            or pricing.get("rub")
            or 0.0
        )

        return {
            "usd_per_use": float(usd or 0.0),
            "credits_per_use": float(credits or 0.0),
            "rub_per_use": float(rub or 0.0),
            "is_free": is_free,
        }
    
    except Exception as e:
        logger.error(f"Failed to get price for {model_id}: {e}")
        return {
            "usd_per_use": 0.0,
            "credits_per_use": 0.0,
            "rub_per_use": 0.0,
            "is_free": False,
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
            
            pricing = model.get("pricing", {}) if isinstance(model.get("pricing", {}), dict) else {}
            rub = pricing.get("rub_per_use") or pricing.get("rub_per_gen") or pricing.get("rub") or 0.0

            by_category[category].append({
                "model_id": model["model_id"],
                "display_name": model.get("display_name", model["model_id"]),
                "price_rub": float(rub or 0.0),
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
    
    price_per_use = pricing["rub_per_use"]
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
