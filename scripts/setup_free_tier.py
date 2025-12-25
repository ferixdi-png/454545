#!/usr/bin/env python3
"""
Auto-configure 5 cheapest models as free tier.
Run this during initialization to setup free models automatically.
"""
import asyncio
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def setup_free_tier():
    """Setup 5 cheapest models as free tier."""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        logger.error("DATABASE_URL not set")
        return False
    
    # Load registry
    registry_path = "models/kie_models_final_truth.json"
    if not os.path.exists(registry_path):
        logger.error(f"Registry not found: {registry_path}")
        return False
    
    with open(registry_path, 'r') as f:
        sot = json.load(f)
    
    # Use pre-identified free_tier_models from v6.2
    free_tier_ids = sot.get('free_tier_models', [])
    
    if not free_tier_ids:
        logger.error("No free_tier_models in registry v6.2")
        return False
    
    logger.info(f"Found {len(free_tier_ids)} FREE tier models from registry:")
    
    # Get full model data
    models_map = {m['model_id']: m for m in sot.get('models', [])}
    cheapest_5 = [models_map[mid] for mid in free_tier_ids if mid in models_map]
    
    for m in cheapest_5:
        price_rub = m.get('pricing', {}).get('rub_per_generation', 0)
        logger.info(f"  - {m['model_id']:40} {price_rub:6.2f} RUB")
    
    # Initialize services
    from app.database.services import DatabaseService
    from app.free.manager import FreeModelManager
    
    db_service = DatabaseService(database_url)
    await db_service.initialize()
    
    free_manager = FreeModelManager(db_service)
    
    # Configure each as free
    for model in cheapest_5:
        model_id = model['model_id']
        
        # Check if already free
        is_free = await free_manager.is_model_free(model_id)
        
        if is_free:
            logger.info(f"✓ {model_id} already free")
            continue
        
        # Add as free with generous limits
        await free_manager.add_free_model(
            model_id=model_id,
            daily_limit=10,   # 10 per day
            hourly_limit=3    # 3 per hour
        )
        logger.info(f"✅ {model_id} configured as free (10/day, 3/hour)")
    
    await db_service.close()
    logger.info("✅ Free tier setup complete!")
    return True


if __name__ == "__main__":
    success = asyncio.run(setup_free_tier())
    sys.exit(0 if success else 1)
