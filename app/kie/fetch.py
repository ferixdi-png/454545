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
        logger.info("📁 Model sync DISABLED (MODEL_SYNC_ENABLED=0), using local truth")
        return await _load_local_models()
    
    # API mode (future implementation)
    logger.warning("⚠️ API model sync not implemented yet, falling back to local")
    return await _load_local_models()


async def _load_local_models() -> List[Dict]:
    """
    Load models from local kie_models_final_truth.json.
    
    Returns:
        List of models from truth file
    """
    truth_path = Path(__file__).parent.parent.parent / "models" / "kie_models_final_truth.json"
    
    if not truth_path.exists():
        logger.error(f"❌ Truth file not found: {truth_path}")
        return []
    
    try:
        with open(truth_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Extract models list
        if isinstance(data, dict) and "models" in data:
            models_list = list(data["models"].values())
        elif isinstance(data, list):
            models_list = data
        else:
            logger.error(f"❌ Unexpected format in {truth_path}")
            return []
        
        logger.info(f"✅ Loaded {len(models_list)} models from local truth")
        return models_list
        
    except Exception as e:
        logger.exception(f"❌ Failed to load local models: {e}")
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
