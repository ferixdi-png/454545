#!/usr/bin/env python3
"""
Проверка актуальности registry - сравнение с live данными Kie.ai
"""
import json
import requests
from pathlib import Path

REGISTRY_PATH = Path(__file__).parent.parent / "models" / "kie_models_final_truth.json"
KIE_API_BASE = "https://api.kie.ai/v1"

def load_registry():
    """Загрузить текущий registry"""
    with open(REGISTRY_PATH) as f:
        data = json.load(f)
    return data

def fetch_live_models():
    """Получить актуальный список моделей из Kie.ai API"""
    try:
        response = requests.get(f"{KIE_API_BASE}/models", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️  Не удалось получить список моделей: {e}")
        return None

def compare_models(registry_data, live_data):
    """Сравнить модели в registry и live"""
    
    registry_models = {m['model_id'] for m in registry_data['models']}
    
    if live_data is None:
        print("❌ Нет live данных для сравнения")
        return
    
    # Предполагаем, что API возвращает список моделей
    if isinstance(live_data, dict) and 'data' in live_data:
        live_models_list = live_data['data']
    elif isinstance(live_data, list):
        live_models_list = live_data
    else:
        live_models_list = []
    
    # Извлекаем ID моделей из live данных
    live_models = set()
    for model in live_models_list:
        if isinstance(model, dict):
            model_id = model.get('id') or model.get('model_id') or model.get('name')
            if model_id:
                live_models.add(model_id)
    
    # Находим различия
    new_models = live_models - registry_models
    removed_models = registry_models - live_models
    common_models = registry_models & live_models
    
    print("=" * 80)
    print("🔍 ПРОВЕРКА АКТУАЛЬНОСТИ REGISTRY")
    print("=" * 80)
    print()
    
    print(f"📦 Registry v{registry_data.get('version', 'unknown')}")
    print(f"   Моделей в registry: {len(registry_models)}")
    print(f"   Моделей в Kie.ai:   {len(live_models)}")
    print(f"   Общих моделей:      {len(common_models)}")
    print()
    
    if new_models:
        print(f"🆕 НОВЫЕ МОДЕЛИ НА KIE.AI ({len(new_models)}):")
        for model_id in sorted(new_models):
            print(f"   + {model_id}")
        print()
    else:
        print("✅ Нет новых моделей на Kie.ai")
        print()
    
    if removed_models:
        print(f"🗑️  УДАЛЁННЫЕ МОДЕЛИ С KIE.AI ({len(removed_models)}):")
        for model_id in sorted(removed_models):
            print(f"   - {model_id}")
        print()
    else:
        print("✅ Нет удалённых моделей")
        print()
    
    # Проверка pricing для общих моделей
    pricing_changes = []
    for model in registry_data['models']:
        model_id = model['model_id']
        if model_id in live_models:
            # Найти соответствующую live модель
            live_model = next((m for m in live_models_list if 
                              (m.get('id') == model_id or 
                               m.get('model_id') == model_id or 
                               m.get('name') == model_id)), None)
            
            if live_model and 'pricing' in live_model:
                registry_price = model.get('pricing', {})
                live_price = live_model['pricing']
                
                if registry_price != live_price:
                    pricing_changes.append({
                        'model_id': model_id,
                        'registry': registry_price,
                        'live': live_price
                    })
    
    if pricing_changes:
        print(f"💰 ИЗМЕНЕНИЯ В PRICING ({len(pricing_changes)}):")
        for change in pricing_changes[:5]:  # Показать первые 5
            print(f"   ⚠️  {change['model_id']}")
            print(f"      Registry: {change['registry']}")
            print(f"      Live:     {change['live']}")
        if len(pricing_changes) > 5:
            print(f"   ... и ещё {len(pricing_changes) - 5} моделей")
        print()
    else:
        print("✅ Pricing актуален")
        print()
    
    # Итоговая оценка
    print("=" * 80)
    print("📊 ИТОГО:")
    print("=" * 80)
    
    if not new_models and not removed_models and not pricing_changes:
        print("✅ REGISTRY ПОЛНОСТЬЮ АКТУАЛЕН")
        print("   Нет необходимости в обновлении")
    else:
        print("⚠️  ТРЕБУЕТСЯ ОБНОВЛЕНИЕ REGISTRY:")
        if new_models:
            print(f"   - Добавить {len(new_models)} новых моделей")
        if removed_models:
            print(f"   - Удалить {len(removed_models)} устаревших моделей")
        if pricing_changes:
            print(f"   - Обновить pricing для {len(pricing_changes)} моделей")
    
    print()
    
    return {
        'new_models': list(new_models),
        'removed_models': list(removed_models),
        'pricing_changes': pricing_changes,
        'is_fresh': not new_models and not removed_models and not pricing_changes
    }

def main():
    print("🔄 Загрузка registry...")
    registry_data = load_registry()
    
    print(f"📡 Получение актуальных данных с Kie.ai...")
    live_data = fetch_live_models()
    
    if live_data:
        print(f"✅ Получено {len(live_data.get('data', live_data)) if isinstance(live_data, dict) else len(live_data)} моделей\n")
    
    result = compare_models(registry_data, live_data)
    
    # Сохранить результат
    result_path = Path(__file__).parent.parent / "artifacts" / "freshness_check.json"
    result_path.parent.mkdir(exist_ok=True)
    with open(result_path, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Результат сохранён: {result_path}")

if __name__ == "__main__":
    main()
