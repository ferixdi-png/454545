"""
Model sync from KIE API (optional, controlled by ENV).

By default DISABLED to avoid unnecessary API calls and errors in production.
Enable via: MODEL_SYNC_ENABLED=1
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Check if model sync is enabled
MODEL_SYNC_ENABLED = os.getenv("MODEL_SYNC_ENABLED", "0") == "1"


async def fetch_models_list() -> List[Dict]:
    """
    Fetch models list (from file by default, optionally from API).
    
    Returns:
        List of model dictionaries
    
    Note:
        By default loads from models/kie_models_final_truth.json (offline mode).
        API fetching can be enabled in future if needed.
    """
    if not MODEL_SYNC_ENABLED:
        # Silent when disabled - no logs needed
        return []
    
    # API mode (future implementation)
    logger.info("🔄 Model sync enabled, loading local truth")
    return await _load_local_models()


async def _load_local_models() -> List[Dict]:
    """
    Load models from local kie_models_final_truth.json.
    
    Supports 3 formats:
    1) {"models": {"model_id": {...}, ...}}  (dict)
    2) {"models": [{...}, {...}]}            (list)
    3) [{...}, {...}]                         (top-level list)
    
    Returns:
        List of models from truth file
    """
    truth_path = Path(__file__).parent.parent.parent / "models" / "kie_models_final_truth.json"
    
    if not truth_path.exists():
        logger.warning(f"⚠️ Truth file not found: {truth_path}")
        return []
    
    try:
        with open(truth_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Normalize to list
        models_list = []
        
        if isinstance(data, list):
            # Format 3: top-level list
            models_list = data
        elif isinstance(data, dict):
            if "models" in data:
                models_data = data["models"]
                if isinstance(models_data, dict):
                    # Format 1: models as dict
                    models_list = list(models_data.values())
                elif isinstance(models_data, list):
                    # Format 2: models as list
                    models_list = models_data
                else:
                    logger.warning(f"⚠️ Unexpected models format in {truth_path}")
                    return []
            else:
                # Single model dict at top level
                models_list = [data]
        else:
            logger.warning(f"⚠️ Unexpected root format in {truth_path}")
            return []
        
        # Ensure each model has model_id or id
        normalized = []
        for model in models_list:
            if not isinstance(model, dict):
                continue
            # Normalize: ensure model_id exists
            if "model_id" not in model and "id" in model:
                model["model_id"] = model["id"]
            if "model_id" in model:
                normalized.append(model)
        
        logger.info(f"✅ Loaded {len(normalized)} models from local truth")
        return normalized
        
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ Invalid JSON in {truth_path}: {e}")
        return []
    except Exception as e:
        logger.warning(f"⚠️ Failed to load local models: {e}")
        return []


async def sync_models_to_sot(models: List[Dict]) -> Dict:
    """
    Sync models to SOURCE_OF_TRUTH (if needed).
    
    Args:
        models: List of models from fetch
    
    Returns:
        Sync statistics
    """
    if not models:
        return {"updated": 0, "added": 0, "skipped": 0}
    
    logger.info(f"📝 Syncing {len(models)} models to SOURCE_OF_TRUTH...")
    
    # For now just return stats without modifying SOT
    # Real sync logic would compare and update models
    
    return {
        "updated": 0,
        "added": 0,
        "skipped": len(models),
        "note": "Sync to SOT currently disabled (manual process)"
    }
