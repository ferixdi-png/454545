"""
Background task for syncing models from KIE API.

Runs every 24 hours to:
- Fetch latest model list from KIE API
- Update model descriptions and metadata
- Sync pricing information
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


async def sync_models_once() -> dict:
    """
    Sync models from KIE API once.
    
    Returns:
        dict: Sync results with stats
    """
    # Check if sync is enabled
    import os
    if os.getenv("MODEL_SYNC_ENABLED", "0") != "1":
        logger.debug("Model sync disabled (MODEL_SYNC_ENABLED=0)")
        return {
            "status": "disabled",
            "models_count": 0,
            "message": "MODEL_SYNC_ENABLED=0"
        }
    
    try:
        from app.kie.fetch import fetch_models_list
        
        logger.info("🔄 Starting model sync from KIE API...")
        start_time = datetime.now()
        
        # Fetch latest models
        models = await fetch_models_list()
        
        if not models:
            logger.warning("⚠️ No models received from KIE API")
            return {
                "status": "warning",
                "models_count": 0,
                "error": "Empty response from API"
            }
        
        # Update SOURCE_OF_TRUTH if needed
        from pathlib import Path
        import json
        
        # Use relative path from this file
        sot_path = Path(__file__).resolve().parent.parent.parent / "models" / "KIE_SOURCE_OF_TRUTH.json"
        
        # Read current SOT
        with open(sot_path, "r", encoding="utf-8") as f:
            current_sot = json.load(f)
        
        current_models = current_sot.get("models", {})
        updated_count = 0
        new_count = 0
        
        # Merge new models
        for model in models:
            model_id = model.get("model_id")
            if not model_id:
                continue
            
            if model_id in current_models:
                # Update existing
                current_models[model_id].update({
                    "display_name": model.get("display_name", current_models[model_id].get("display_name")),
                    "description": model.get("description", current_models[model_id].get("description")),
                })
                updated_count += 1
            else:
                # New model
                current_models[model_id] = model
                new_count += 1
        
        # Save updated SOT
        current_sot["models"] = current_models
        current_sot["last_sync"] = datetime.now().isoformat()
        
        with open(sot_path, "w", encoding="utf-8") as f:
            json.dump(current_sot, f, indent=2, ensure_ascii=False)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(
            f"✅ Model sync complete: {updated_count} updated, {new_count} new "
            f"(total: {len(current_models)}) in {duration:.2f}s"
        )
        
        return {
            "status": "success",
            "models_count": len(models),
            "updated_count": updated_count,
            "new_count": new_count,
            "duration_seconds": duration,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Model sync failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def model_sync_loop(interval_hours: int = 24):
    """
    Background loop that syncs models every N hours.
    
    Args:
        interval_hours: Hours between sync runs
    """
    logger.info(f"🔄 Model sync loop started (interval: {interval_hours}h)")
    
    while True:
        try:
            result = await sync_models_once()
            logger.info(f"Model sync result: {result['status']}")
            
        except Exception as e:
            logger.error(f"Model sync loop error: {e}", exc_info=True)
        
        # Wait for next sync
        await asyncio.sleep(interval_hours * 3600)
