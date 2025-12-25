#!/usr/bin/env python3
"""
Скрапинг моделей с kie.ai для построения source of truth.
Так как API Market недоступен, парсим официальный сайт.
"""
import httpx
import json
import re
from pathlib import Path
from typing import Dict, List, Any

# Базовые модели из документации и скриншотов
KNOWN_MODELS = [
    # Из документации
    {
        "model_id": "z-image",
        "display_name": "Z-Image",
        "category": "image-generation",
        "modality": "text-to-image",
        "description": "Tongyi-MAI's efficient image generation model",
        "pricing": {
            "credits_per_run": 0.8,
            "usd_per_run": 0.004
        },
        "input_schema": {
            "type": "object",
            "required": ["prompt", "aspect_ratio"],
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "A text description of the image you want to generate",
                    "max_length": 1000
                },
                "aspect_ratio": {
                    "type": "string",
                    "enum": ["1:1", "4:3", "3:4", "16:9", "9:16"],
                    "default": "1:1",
                    "description": "Aspect ratio for the generated image"
                }
            }
        },
        "output_type": "image",
        "examples": [
            {
                "prompt": "A hyper-realistic portrait of a woman drinking coffee",
                "aspect_ratio": "1:1"
            }
        ]
    },
]

# Дополним список моделями из других источников
# TODO: Добавить автопарсинг со страницы https://kie.ai/models


def fetch_model_page(model_slug: str) -> Dict[str, Any]:
    """Попытка получить информацию о модели со страницы."""
    url = f"https://kie.ai/{model_slug}"
    
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                # Здесь можно парсить HTML для извлечения:
                # - display_name
                # - description
                # - pricing
                # - input parameters
                # Но это сложно без BeautifulSoup
                
                # Для начала просто проверяем доступность
                return {"status": "available", "url": url}
    except Exception as e:
        print(f"❌ Failed to fetch {model_slug}: {e}")
    
    return {"status": "unavailable"}


def build_registry() -> List[Dict[str, Any]]:
    """Построение registry из известных моделей."""
    registry = []
    
    print("📋 Building model registry from known sources...")
    print()
    
    for model in KNOWN_MODELS:
        model_id = model["model_id"]
        print(f"✅ {model_id}: {model['display_name']}")
        print(f"   Category: {model['category']}")
        print(f"   Pricing: {model['pricing']['credits_per_run']} credits (${model['pricing']['usd_per_run']})")
        print()
        
        registry.append(model)
    
    return registry


def save_registry(registry: List[Dict[str, Any]], output_path: Path):
    """Сохранение registry в JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Registry saved to: {output_path}")
    print(f"📊 Total models: {len(registry)}")


def main():
    output_path = Path(__file__).parent.parent / "models" / "kie_models_source_of_truth.json"
    
    registry = build_registry()
    save_registry(registry, output_path)
    
    print()
    print("="*60)
    print("✅ Registry build complete!")
    print()
    print("Next steps:")
    print("1. Manually add more models from https://kie.ai/models")
    print("2. For each model, copy input parameters from API documentation")
    print("3. Verify pricing from official Kie pricing page")
    print("="*60)


if __name__ == "__main__":
    main()
