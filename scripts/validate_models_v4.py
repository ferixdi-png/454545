#!/usr/bin/env python3
"""
AI Model System Validation v4.0

Проверяет доступность всех 42 моделей через Kie.ai API.
Генерирует отчёт о статусе и предлагает fallback для недоступных.
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

# Load environment (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not required

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class ModelValidator:
    """Валидатор моделей Kie.ai"""
    
    def __init__(self):
        self.api_key = os.getenv("KIE_API_KEY", "")
        self.base_url = os.getenv("KIE_BASE_URL", "https://api.kie.ai").rstrip("/")
        self.timeout = 10.0
        
        if not self.api_key:
            logger.warning("⚠️  KIE_API_KEY not set, validation will be limited")
        
        # Load models from allowlist
        self.allowed_models = self._load_allowed_models()
        
        # Load registry
        self.registry = self._load_registry()
        
        # Results
        self.results: Dict[str, Dict] = {}
    
    def _load_allowed_models(self) -> List[str]:
        """Загрузка списка разрешённых моделей"""
        file_path = Path(__file__).parent.parent / "models" / "ALLOWED_MODEL_IDS.txt"
        
        if not file_path.exists():
            logger.error(f"❌ ALLOWED_MODEL_IDS.txt not found: {file_path}")
            return []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            models = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        logger.info(f"✅ Loaded {len(models)} models from allowlist")
        return models
    
    def _load_registry(self) -> Dict:
        """Загрузка registry с моделями"""
        file_path = Path(__file__).parent.parent / "models" / "KIE_SOURCE_OF_TRUTH.json"
        
        if not file_path.exists():
            logger.warning(f"⚠️  Registry not found: {file_path}")
            return {"models": {}}
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data
    
    async def check_model_availability(self, model_id: str) -> Tuple[bool, str]:
        """
        Проверяет доступность модели через API.
        
        Returns:
            (is_available, status_message)
        """
        if not self.api_key:
            # Offline check - based on registry
            if model_id in self.registry.get("models", {}):
                return True, "Registry OK (offline check)"
            return False, "Not in registry"
        
        # Online check - попытка получить info о модели
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Check if model exists in Kie.ai marketplace
                # Note: actual endpoint depends on Kie.ai API structure
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                # Try to get model info (adjust endpoint as needed)
                response = await client.get(
                    f"{self.base_url}/models/{model_id}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    return True, "API OK"
                elif response.status_code == 404:
                    return False, "Not found in API"
                else:
                    return False, f"API error: {response.status_code}"
                    
            except httpx.TimeoutException:
                return False, "Timeout"
            except httpx.RequestError as e:
                return False, f"Request error: {str(e)[:50]}"
            except Exception as e:
                return False, f"Error: {str(e)[:50]}"
    
    def get_model_info(self, model_id: str) -> Dict:
        """Получить информацию о модели из registry"""
        return self.registry.get("models", {}).get(model_id, {})
    
    def suggest_fallback(self, model_id: str) -> Optional[str]:
        """Предложить fallback модель для недоступной"""
        # Fallback map based on category/provider
        fallbacks = {
            # Video generation
            "sora-2-text-to-video": "wan/2-6-text-to-video",
            "sora-2-image-to-video": "wan/2-6-image-to-video",
            "kling-2.6/text-to-video": "wan/2-6-text-to-video",
            "kling-2.6/image-to-video": "wan/2-6-image-to-video",
            
            # Image generation
            "flux-2/pro-text-to-image": "flux-2/flex-text-to-image",
            "google/imagen4-ultra": "google/imagen4-fast",
            "seedream/4.5-text-to-image": "z-image",
            
            # Audio
            "elevenlabs/text-to-speech-turbo-2-5": "elevenlabs/text-to-speech-multilingual-v2",
        }
        
        # Try direct mapping
        if model_id in fallbacks:
            return fallbacks[model_id]
        
        # Try category-based fallback
        model_info = self.get_model_info(model_id)
        category = model_info.get("category", "")
        
        # Find another model in same category
        for mid, info in self.registry.get("models", {}).items():
            if info.get("category") == category and mid != model_id and mid in self.allowed_models:
                return mid
        
        return None
    
    async def validate_all(self):
        """Валидация всех моделей"""
        logger.info(f"🔍 Starting validation of {len(self.allowed_models)} models...")
        
        tasks = []
        for model_id in self.allowed_models:
            tasks.append(self._validate_model(model_id))
        
        await asyncio.gather(*tasks)
        
        logger.info("✅ Validation complete")
    
    async def _validate_model(self, model_id: str):
        """Валидация одной модели"""
        logger.info(f"Checking: {model_id}")
        
        # Check availability
        is_available, status = await self.check_model_availability(model_id)
        
        # Get model info
        model_info = self.get_model_info(model_id)
        
        # Find fallback if needed
        fallback = None
        if not is_available:
            fallback = self.suggest_fallback(model_id)
        
        # Store results
        self.results[model_id] = {
            "status": "✅ OK" if is_available else "❌ DOWN",
            "available": is_available,
            "status_message": status,
            "category": model_info.get("category", "unknown"),
            "provider": model_info.get("provider", "unknown"),
            "has_pricing": bool(model_info.get("pricing")),
            "has_schema": bool(model_info.get("input_schema")),
            "fallback": fallback
        }
    
    def generate_report(self) -> str:
        """Генерация отчёта о валидации"""
        report = []
        report.append("=" * 80)
        report.append("AI MODEL SYSTEM VALIDATION v4.0")
        report.append("=" * 80)
        report.append(f"Timestamp: {datetime.now().isoformat()}")
        report.append(f"Total models: {len(self.allowed_models)}")
        report.append("")
        
        # Statistics
        available = sum(1 for r in self.results.values() if r["available"])
        unavailable = len(self.results) - available
        
        report.append(f"Available:   {available} / {len(self.results)}")
        report.append(f"Unavailable: {unavailable} / {len(self.results)}")
        report.append("")
        
        # Table
        report.append("MODEL STATUS TABLE:")
        report.append("-" * 80)
        report.append(f"{'Model ID':<40} {'Status':<10} {'Category':<20}")
        report.append("-" * 80)
        
        for model_id in sorted(self.results.keys()):
            result = self.results[model_id]
            status = result["status"]
            category = result["category"][:18]
            
            report.append(f"{model_id:<40} {status:<10} {category:<20}")
            
            if not result["available"] and result["fallback"]:
                report.append(f"  └─ Fallback: {result['fallback']}")
        
        report.append("-" * 80)
        report.append("")
        
        # Unavailable models detail
        if unavailable > 0:
            report.append("UNAVAILABLE MODELS DETAIL:")
            report.append("-" * 80)
            
            for model_id, result in self.results.items():
                if not result["available"]:
                    report.append(f"❌ {model_id}")
                    report.append(f"   Reason: {result['status_message']}")
                    if result["fallback"]:
                        report.append(f"   Suggested fallback: {result['fallback']}")
                    report.append("")
        
        # Registry status
        report.append("REGISTRY STATUS:")
        report.append("-" * 80)
        
        with_pricing = sum(1 for r in self.results.values() if r["has_pricing"])
        with_schema = sum(1 for r in self.results.values() if r["has_schema"])
        
        report.append(f"Models with pricing: {with_pricing} / {len(self.results)}")
        report.append(f"Models with schema:  {with_schema} / {len(self.results)}")
        report.append("")
        
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def save_results(self, output_file: str = "model_validation_results.json"):
        """Сохранить результаты в JSON"""
        output_path = Path(__file__).parent.parent / "artifacts" / output_file
        output_path.parent.mkdir(exist_ok=True)
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "total_models": len(self.allowed_models),
            "available": sum(1 for r in self.results.values() if r["available"]),
            "unavailable": sum(1 for r in self.results.values() if not r["available"]),
            "results": self.results
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Results saved to: {output_path}")


async def main():
    """Main entry point"""
    validator = ModelValidator()
    
    # Run validation
    await validator.validate_all()
    
    # Generate and print report
    report = validator.generate_report()
    print(report)
    
    # Save results
    validator.save_results()
    
    # Export available models for registry
    available_models = [
        model_id for model_id, result in validator.results.items()
        if result["available"]
    ]
    
    logger.info(f"\n✅ {len(available_models)} models validated and ready for registry")


if __name__ == "__main__":
    asyncio.run(main())
