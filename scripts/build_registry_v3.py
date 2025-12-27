#!/usr/bin/env python3
"""
ПОЛНЫЙ ПАРСИНГ МОДЕЛЕЙ KIE.AI
Строит source of truth на основе:
1. Официальной документации API
2. Pricing таблицы (kie_pricing_raw.txt)
3. Известных model_id с сайта kie.ai
"""
import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

# ВАЖНО: model_id должны точно совпадать с тем, что принимает Kie API
# Формат: простое название модели (без "vendor/model"), как в документации

# Категории моделей для UI/UX
CATEGORIES = {
    "text-to-image": {
        "name": "🖼 Генерация изображений",
        "description": "Создание картинок из текста",
        "emoji": "🖼"
    },
    "image-to-image": {
        "name": "✨ Редактирование изображений",
        "description": "Модификация существующих картинок",
        "emoji": "✨"
    },
    "text-to-video": {
        "name": "🎬 Генерация видео",
        "description": "Создание видео из текста",
        "emoji": "🎬"
    },
    "image-to-video": {
        "name": "🎞 Анимация изображений",
        "description": "Превращение картинок в видео",
        "emoji": "🎞"
    },
    "video-to-video": {
        "name": "🎥 Обработка видео",
        "description": "Редактирование видео",
        "emoji": "🎥"
    },
    "text-to-speech": {
        "name": "🎙 Озвучка текста",
        "description": "Преобразование текста в речь",
        "emoji": "🎙"
    },
    "speech-to-text": {
        "name": "📝 Распознавание речи",
        "description": "Преобразование речи в текст",
        "emoji": "📝"
    },
    "audio": {
        "name": "🎵 Работа с аудио",
        "description": "Генерация и обработка звука",
        "emoji": "🎵"
    },
    "upscale": {
        "name": "🔍 Улучшение качества",
        "description": "Апскейл и реставрация",
        "emoji": "🔍"
    },
}

# БАЗОВЫЕ МОДЕЛИ (минимальный набор с точными model_id)
BASE_MODELS = [
    {
        "model_id": "z-image",
        "display_name": "Z-Image (Qwen)",
        "vendor": "Qwen",
        "category": "text-to-image",
        "description": "Эффективная генерация фотореалистичных изображений с быстрым Turbo режимом и точным билингвальным рендерингом текста.",
        "pricing": {
            "credits_per_run": 0.8,
            "usd_per_run": 0.004
        },
        "enabled": True,
        "commercial_use": True,
        "input_schema": {
            "type": "object",
            "required": ["prompt", "aspect_ratio"],
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Текстовое описание изображения, которое вы хотите создать",
                    "max_length": 1000,
                    "example": "Гиперреалистичный портрет женщины за 30 лет, пьющей кофе"
                },
                "aspect_ratio": {
                    "type": "string",
                    "enum": ["1:1", "4:3", "3:4", "16:9", "9:16"],
                    "default": "1:1",
                    "description": "Соотношение сторон для генерируемого изображения"
                }
            }
        },
        "output_type": "image",
        "estimated_time": "10-15 секунд"
    },
]

# РАСШИРЕННЫЕ МОДЕЛИ (на основе pricing таблицы)
# TODO: Добавить все ~80 моделей с правильными model_id после получения tech names с API/сайта


def normalize_model_id(raw_name: str) -> str:
    """
    Нормализация имени модели в tech model_id.
    ВАЖНО: Это предположительная логика, нужно проверить на реальных примерах!
    """
    # Удаляем спецсимволы
    clean = raw_name.lower().strip()
    # Заменяем пробелы на дефисы
    clean = clean.replace(" ", "-")
    # Удаляем запятые и точки
    clean = clean.replace(",", "").replace(".", "")
    return clean


def load_pricing_table(path: Path) -> Dict[str, float]:
    """Загрузка pricing из kie_pricing_raw.txt"""
    pricing = {}
    
    if not path.exists():
        print(f"⚠️ Pricing file not found: {path}")
        return pricing
    
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "|" not in line:
                continue
            
            parts = line.split("|")
            if len(parts) != 2:
                continue
            
            model_name = parts[0].strip()
            try:
                price_usd = float(parts[1].strip())
                pricing[model_name] = price_usd
            except ValueError:
                continue
    
    return pricing


def build_full_registry() -> Dict[str, Any]:
    """Построение полного registry."""
    
    print("="*60)
    print("📋 BUILDING FULL KIE.AI MODELS REGISTRY")
    print("="*60)
    print()
    
    # Загружаем FX курс
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from app.pricing.fx import get_usd_to_rub_rate, usd_to_rub
        
        fx_rate = get_usd_to_rub_rate()
        print(f"💱 FX Rate: {fx_rate:.2f} RUB/USD")
    except Exception as e:
        print(f"⚠️ Could not fetch FX rate: {e}")
        fx_rate = 78.0
        print(f"💱 Using fallback: {fx_rate} RUB/USD")
    
    print()
    
    # Загружаем pricing
    pricing_path = Path(__file__).parent.parent / "kie_pricing_raw.txt"
    pricing_table = load_pricing_table(pricing_path)
    
    print(f"💰 Loaded {len(pricing_table)} pricing entries")
    print()
    
    # Собираем модели
    models = []
    
    print("✅ Adding base models:")
    for model in BASE_MODELS:
        # Добавляем RUB pricing
        model["pricing"]["rub_per_use"] = round(
            model["pricing"]["usd_per_run"] * fx_rate * 2.0,  # 2x markup
            2
        )
        
        models.append(model)
        print(f"   • {model['model_id']}: {model['display_name']}")
        print(f"     ${model['pricing']['usd_per_run']} → {model['pricing']['rub_per_use']} RUB")
    
    print()
    print(f"📊 Total models in registry: {len(models)}")
    print()
    
    # Собираем статистику
    categories_count = {}
    for model in models:
        cat = model.get("category", "unknown")
        categories_count[cat] = categories_count.get(cat, 0) + 1
    
    # Сортируем по цене (RUB)
    models_sorted = sorted(models, key=lambda m: m["pricing"]["rub_per_use"])
    
    print("💵 TOP-10 CHEAPEST MODELS:")
    for i, model in enumerate(models_sorted[:10], 1):
        print(f"   {i}. {model['model_id']}: {model['pricing']['rub_per_use']} RUB")
    print()
    
    # Формируем итоговый registry
    registry = {
        "version": "3.0",
        "source": "manual_build_from_api_docs_and_pricing",
        "timestamp": datetime.now().isoformat(),
        "fx_rate": fx_rate,
        "markup": 2.0,
        "models": models,
        "categories": CATEGORIES,
        "stats": {
            "total_models": len(models),
            "enabled_models": sum(1 for m in models if m.get("enabled", True)),
            "categories": categories_count,
            "cheapest_models": [m["model_id"] for m in models_sorted[:5]],
        }
    }
    
    return registry


def save_registry(registry: Dict[str, Any], output_path: Path):
    """Сохранение registry в JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Registry saved to: {output_path}")


def main():
    output_path = Path(__file__).parent.parent / "models" / "kie_models_source_of_truth.json"
    
    registry = build_full_registry()
    save_registry(registry, output_path)
    
    print()
    print("="*60)
    print("✅ REGISTRY BUILD COMPLETE!")
    print()
    print("📋 Summary:")
    print(f"   Total models: {registry['stats']['total_models']}")
    print(f"   Enabled models: {registry['stats']['enabled_models']}")
    print(f"   Categories: {len(registry['categories'])}")
    print()
    print("🎯 Top-5 cheapest (will be FREE):")
    for model_id in registry['stats']['cheapest_models']:
        model = next(m for m in registry['models'] if m['model_id'] == model_id)
        print(f"   • {model_id}: ${model['pricing']['usd_per_run']}")
    print()
    print("="*60)


if __name__ == "__main__":
    main()
