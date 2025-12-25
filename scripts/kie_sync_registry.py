#!/usr/bin/env python3
"""
Kie.ai Registry Sync - Source of Truth Builder.

ARCHITECTURE:
- Kie.ai API v1 provides model details through marketplace/search endpoints
- Each model has tech_id, display_name, pricing, and input_schema
- This script builds the SINGLE SOURCE OF TRUTH for all models

ENDPOINTS USED:
- GET /api/v1/marketplace/models - list all available models
- GET /api/v1/models/{model_id} - get specific model details
- Fallback: manual list of known model IDs to fetch individually

OUTPUT:
- models/kie_models_source_of_truth.json - complete registry with pricing

CRITICAL RULES:
1. NEVER hardcode prices - always fetch from API
2. NEVER use "marketing names" - use tech model_id only
3. NEVER mix USD/credits without conversion metadata
4. Price formula: price_rub = price_usd * fx_rate * markup (2x)
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed")
    print("Run: pip install httpx")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
SOURCE_OF_TRUTH = Path("models/kie_models_source_of_truth.json")
BACKUP_DIR = Path("models/backups")
KIE_API_BASE = os.getenv("KIE_BASE_URL", "https://api.kie.ai").rstrip("/")
DEFAULT_TIMEOUT = 30.0
USD_TO_RUB = float(os.getenv("FX_RUB_PER_USD", "78.0"))
PRICE_MARKUP = 2.0  # 2x markup for users

# Known model categories from Kie.ai marketplace
KNOWN_MODELS = [
    # Text-to-Video
    "google/veo-3.1-text-to-video-fast",
    "google/veo-3.1-text-to-video-standard", 
    "google/veo-2-text-to-video",
    "openai/sora-turbo",
    "minimax/video-01-live",
    "minimax/video-01",
    "runway/gen-3-alpha-turbo",
    "runway/gen-3-alpha",
    "kling/v1.6-pro",
    "kling/v1.6-standard",
    "kling/v1.5-pro",
    "kling/v1.5-standard",
    "luma/dream-machine-v1.6",
    "luma/dream-machine-v1.5",
    "haiper/v2.5",
    "haiper/v2.0",
    
    # Image-to-Video
    "google/veo-3.1-image-to-video-fast",
    "google/veo-3.1-image-to-video-standard",
    "minimax/video-01-live-image-to-video",
    "kling/v1.6-pro-image-to-video",
    "luma/dream-machine-image-to-video",
    
    # Text-to-Image
    "flux/pro-1.1-ultra",
    "flux/pro-1.1",
    "flux/pro",
    "flux/dev",
    "flux/schnell",
    "ideogram/v2-turbo",
    "ideogram/v2",
    "recraft/v3",
    "black-forest-labs/flux-1.1-pro-ultra",
    
    # Image-to-Image
    "flux/pro-1.1-depth",
    "flux/pro-1.1-fill",
    "flux/dev-redux",
    "fal/auraflow",
    
    # Upscale
    "clarity-ai/upscale",
    "magnific/upscale",
    "topaz/gigapixel",
    
    # Speech/Audio
    "openai/tts-1-hd",
    "openai/tts-1",
    "elevenlabs/turbo-v2.5",
    "elevenlabs/multilingual-v2",
    "playht/3.0-mini",
    "google/chirp-2",
    
    # Music
    "suno/v4",
    "suno/v3.5",
    "udio/v1.5",
    
    # OCR/Document
    "google/document-ai",
    "aws/textract",
]


class KieRegistrySync:
    """Sync Kie.ai model registry from API."""
    
    def __init__(self, api_key: str | None = None, dry_run: bool = False):
        self.api_key = api_key or os.getenv("KIE_API_KEY")
        if not self.api_key:
            raise ValueError("KIE_API_KEY required")
        
        self.dry_run = dry_run
        self.client = httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        await self.client.aclose()
    
    async def fetch_marketplace_models(self) -> List[Dict[str, Any]]:
        """
        Fetch models from Kie.ai marketplace API.
        
        Tries multiple endpoints:
        1. /api/v1/marketplace/models
        2. /api/v1/models
        3. /v1/models
        """
        endpoints = [
            f"{KIE_API_BASE}/api/v1/marketplace/models",
            f"{KIE_API_BASE}/api/v1/models",
            f"{KIE_API_BASE}/v1/models",
        ]
        
        for endpoint in endpoints:
            try:
                logger.info(f"Trying: {endpoint}")
                response = await self.client.get(endpoint)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Handle different response formats
                    if isinstance(data, list):
                        models = data
                    elif isinstance(data, dict):
                        models = (
                            data.get("models") or
                            data.get("data") or
                            data.get("items") or
                            []
                        )
                    else:
                        models = []
                    
                    if models:
                        logger.info(f"✅ Fetched {len(models)} models from {endpoint}")
                        return models
                else:
                    logger.warning(f"HTTP {response.status_code}: {endpoint}")
                    
            except Exception as e:
                logger.warning(f"Failed {endpoint}: {e}")
                continue
        
        logger.warning("No marketplace endpoint worked, falling back to known models")
        return []
    
    async def fetch_model_details(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed info for specific model.
        
        Args:
            model_id: Tech model ID (e.g., "google/veo-3.1-text-to-video-fast")
        
        Returns:
            Model details dict or None if failed
        """
        endpoints = [
            f"{KIE_API_BASE}/api/v1/models/{model_id}",
            f"{KIE_API_BASE}/v1/models/{model_id}",
            f"{KIE_API_BASE}/api/v1/marketplace/models/{model_id}",
        ]
        
        for endpoint in endpoints:
            try:
                response = await self.client.get(endpoint)
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ Fetched details for {model_id}")
                    return data
                    
            except Exception as e:
                logger.debug(f"Failed {endpoint}: {e}")
                continue
        
        logger.warning(f"❌ Could not fetch details for {model_id}")
        return None
    
    def normalize_model(self, raw_model: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Normalize raw API response to standard format.
        
        Standard format:
        {
            "model_id": str,
            "display_name": str,
            "category": str,
            "pricing": {
                "usd_per_use": float,
                "credits_per_use": float,
                "rub_per_use": float
            },
            "input_schema": {...},
            "output_type": str,
            "description": str,
            "enabled": bool
        }
        """
        try:
            # Extract model_id (tech id)
            model_id = (
                raw_model.get("id") or
                raw_model.get("model_id") or
                raw_model.get("technical_id") or
                raw_model.get("name")
            )
            
            if not model_id:
                logger.warning(f"Model missing ID: {raw_model}")
                return None
            
            # Extract display name
            display_name = (
                raw_model.get("display_name") or
                raw_model.get("name") or
                raw_model.get("title") or
                model_id
            )
            
            # Extract category
            category = (
                raw_model.get("category") or
                raw_model.get("type") or
                self._infer_category(model_id)
            )
            
            # Extract pricing - CRITICAL
            pricing = self._extract_pricing(raw_model)
            
            # Extract input schema
            input_schema = (
                raw_model.get("input_schema") or
                raw_model.get("schema") or
                raw_model.get("parameters") or
                {}
            )
            
            # Extract output type
            output_type = (
                raw_model.get("output_type") or
                raw_model.get("output") or
                self._infer_output_type(category)
            )
            
            # Description
            description = (
                raw_model.get("description") or
                raw_model.get("summary") or
                ""
            )
            
            # Enabled flag
            enabled = raw_model.get("enabled", True)
            
            return {
                "model_id": model_id,
                "display_name": display_name,
                "category": category,
                "pricing": pricing,
                "input_schema": input_schema,
                "output_type": output_type,
                "description": description,
                "enabled": enabled,
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to normalize model: {e}")
            logger.debug(f"Raw model: {raw_model}")
            return None
    
    def _extract_pricing(self, raw_model: Dict[str, Any]) -> Dict[str, float]:
        """
        Extract and normalize pricing from raw model.
        
        Returns:
            {
                "usd_per_use": float,
                "credits_per_use": float,
                "rub_per_use": float
            }
        """
        # Try to find USD price
        usd_price = None
        credits_price = None
        
        # Check pricing object
        pricing_obj = raw_model.get("pricing", {})
        if isinstance(pricing_obj, dict):
            usd_price = (
                pricing_obj.get("usd_per_use") or
                pricing_obj.get("price_usd") or
                pricing_obj.get("cost_usd") or
                pricing_obj.get("per_request")
            )
            credits_price = (
                pricing_obj.get("credits") or
                pricing_obj.get("credits_per_use") or
                pricing_obj.get("cost_credits")
            )
        
        # Check top-level fields
        if usd_price is None:
            usd_price = (
                raw_model.get("price_usd") or
                raw_model.get("cost_usd") or
                raw_model.get("price")
            )
        
        if credits_price is None:
            credits_price = (
                raw_model.get("credits") or
                raw_model.get("cost_credits")
            )
        
        # Convert to float
        try:
            usd_price = float(usd_price) if usd_price is not None else 0.0
        except (ValueError, TypeError):
            usd_price = 0.0
        
        try:
            credits_price = float(credits_price) if credits_price is not None else 0.0
        except (ValueError, TypeError):
            credits_price = 0.0
        
        # Calculate RUB price
        rub_price = usd_price * USD_TO_RUB * PRICE_MARKUP
        
        return {
            "usd_per_use": round(usd_price, 4),
            "credits_per_use": round(credits_price, 2),
            "rub_per_use": round(rub_price, 2)
        }
    
    def _infer_category(self, model_id: str) -> str:
        """Infer category from model_id."""
        mid_lower = model_id.lower()
        
        if "text-to-video" in mid_lower or "t2v" in mid_lower:
            return "text-to-video"
        elif "image-to-video" in mid_lower or "i2v" in mid_lower:
            return "image-to-video"
        elif "text-to-image" in mid_lower or "t2i" in mid_lower:
            return "text-to-image"
        elif "image-to-image" in mid_lower or "i2i" in mid_lower:
            return "image-to-image"
        elif "upscale" in mid_lower or "enhance" in mid_lower:
            return "upscale"
        elif "tts" in mid_lower or "speech" in mid_lower or "voice" in mid_lower:
            return "text-to-speech"
        elif "stt" in mid_lower or "transcribe" in mid_lower:
            return "speech-to-text"
        elif "music" in mid_lower or "audio" in mid_lower:
            return "audio-generation"
        elif "ocr" in mid_lower or "document" in mid_lower:
            return "ocr"
        else:
            return "other"
    
    def _infer_output_type(self, category: str) -> str:
        """Infer output type from category."""
        if "video" in category:
            return "video"
        elif "image" in category:
            return "image"
        elif "audio" in category or "speech" in category or "music" in category:
            return "audio"
        elif "text" in category or "ocr" in category:
            return "text"
        else:
            return "url"
    
    async def build_source_of_truth(self) -> Dict[str, Any]:
        """
        Build complete source of truth from Kie.ai API.
        
        Returns:
            {
                "version": "2.0",
                "source": "kie_api",
                "timestamp": ISO timestamp,
                "fx_rate": float,
                "markup": float,
                "models": [...]
            }
        """
        logger.info("Starting Kie.ai registry sync...")
        
        # Try marketplace endpoint first
        marketplace_models = await self.fetch_marketplace_models()
        
        # If marketplace failed, use known model list
        if not marketplace_models:
            logger.info(f"Fetching {len(KNOWN_MODELS)} known models individually...")
            marketplace_models = []
            
            for model_id in KNOWN_MODELS:
                details = await self.fetch_model_details(model_id)
                if details:
                    marketplace_models.append(details)
                await asyncio.sleep(0.1)  # Rate limiting
        
        # Normalize all models
        normalized_models = []
        for raw_model in marketplace_models:
            normalized = self.normalize_model(raw_model)
            if normalized:
                normalized_models.append(normalized)
        
        logger.info(f"✅ Normalized {len(normalized_models)} models")
        
        # Sort by price (cheapest first)
        normalized_models.sort(key=lambda m: m["pricing"]["rub_per_use"])
        
        # Build final structure
        source_of_truth = {
            "version": "2.0",
            "source": "kie_api",
            "timestamp": datetime.utcnow().isoformat(),
            "fx_rate": USD_TO_RUB,
            "markup": PRICE_MARKUP,
            "models": normalized_models,
            "stats": {
                "total_models": len(normalized_models),
                "enabled_models": sum(1 for m in normalized_models if m["enabled"]),
                "categories": list(set(m["category"] for m in normalized_models))
            }
        }
        
        return source_of_truth
    
    def backup_existing(self):
        """Backup existing source of truth."""
        if not SOURCE_OF_TRUTH.exists():
            logger.info("No existing source of truth to backup")
            return
        
        BACKUP_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"kie_models_{timestamp}.json"
        
        with open(SOURCE_OF_TRUTH, 'r') as src:
            with open(backup_path, 'w') as dst:
                dst.write(src.read())
        
        logger.info(f"✅ Backed up to {backup_path}")
    
    def save_source_of_truth(self, data: Dict[str, Any]):
        """Save source of truth to file."""
        if self.dry_run:
            logger.info("DRY RUN - would save to models/kie_models_source_of_truth.json")
            logger.info(json.dumps(data["stats"], indent=2))
            return
        
        # Backup existing
        self.backup_existing()
        
        # Save new
        SOURCE_OF_TRUTH.parent.mkdir(exist_ok=True)
        with open(SOURCE_OF_TRUTH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Saved {len(data['models'])} models to {SOURCE_OF_TRUTH}")


async def main():
    parser = argparse.ArgumentParser(description="Sync Kie.ai model registry")
    parser.add_argument("--dry-run", action="store_true", help="Don't save changes")
    parser.add_argument("--api-key", help="Kie.ai API key (or use KIE_API_KEY env)")
    args = parser.parse_args()
    
    try:
        async with KieRegistrySync(api_key=args.api_key, dry_run=args.dry_run) as syncer:
            source_of_truth = await syncer.build_source_of_truth()
            syncer.save_source_of_truth(source_of_truth)
            
            # Print summary
            print("\n" + "="*60)
            print("SYNC COMPLETE")
            print("="*60)
            print(f"Total models: {source_of_truth['stats']['total_models']}")
            print(f"Enabled: {source_of_truth['stats']['enabled_models']}")
            print(f"Categories: {', '.join(source_of_truth['stats']['categories'])}")
            print(f"\nTop 5 cheapest models:")
            for i, model in enumerate(source_of_truth['models'][:5], 1):
                print(f"  {i}. {model['model_id']}: {model['pricing']['rub_per_use']} RUB")
            print("="*60)
            
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
