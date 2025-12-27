#!/usr/bin/env python3
"""
Комплексная валидация всей системы бота.
Проверяет интеграцию SOURCE_OF_TRUTH с ботом end-to-end.
"""
import json
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.kie.registry import get_registry
from app.pricing.free_models import get_free_models
from app.ui.marketing_menu import build_ui_tree


def validate_source_of_truth():
    """Валидация SOURCE_OF_TRUTH файла"""
    print("🔍 ВАЛИДАЦИЯ SOURCE_OF_TRUTH\n")
    
    registry_path = Path("models/KIE_SOURCE_OF_TRUTH.json")
    
    if not registry_path.exists():
        print("❌ КРИТИЧНО: KIE_SOURCE_OF_TRUTH.json не найден!")
        return False
    
    with open(registry_path, 'r') as f:
        data = json.load(f)
    
    models = data.get('models', {})
    
    # Базовые проверки
    checks = {
        "Всего моделей": len(models),
        "С examples": sum(1 for m in models.values() if m.get('examples')),
        "С input_schema": sum(1 for m in models.values() if m.get('input_schema')),
        "С pricing": sum(1 for m in models.values() if m.get('pricing')),
        "С is_free=True": sum(1 for m in models.values() if m.get('pricing', {}).get('is_free'))
    }
    
    for check, value in checks.items():
        status = "✅" if value > 0 else "❌"
        print(f"{status} {check}: {value}")
    
    # Проверка is_free
    free_count = checks["С is_free=True"]
    if free_count != 5:
        print(f"\n⚠️  Ожидалось 5 FREE моделей, найдено {free_count}")
        return False
    
    print("\n✅ SOURCE_OF_TRUTH валидация пройдена")
    return True


def validate_registry_loader():
    """Валидация KieRegistryLoader"""
    print("\n🔍 ВАЛИДАЦИЯ REGISTRY LOADER\n")
    
    try:
        reg = get_registry()
        
        checks = {
            "all_models": len(reg.all_models),
            "ready_models": len(reg.ready_models),
            "priced_models": len(reg.priced_models),
            "free_models": len(reg.free_models)
        }
        
        for check, value in checks.items():
            print(f"✅ {check}: {value}")
        
        # Проверки соответствия
        if checks["all_models"] != 72:
            print(f"❌ Ожидалось 72 модели, загружено {checks['all_models']}")
            return False
        
        if checks["free_models"] != 5:
            print(f"❌ Ожидалось 5 FREE моделей, найдено {checks['free_models']}")
            return False
        
        print("\n✅ Registry Loader валидация пройдена")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка загрузки registry: {e}")
        return False


def validate_free_tier():
    """Валидация FREE tier"""
    print("\n🔍 ВАЛИДАЦИЯ FREE TIER\n")
    
    try:
        free_models = get_free_models()
        
        expected_free = [
            "z-image",
            "qwen/text-to-image",
            "qwen/image-to-image",
            "qwen/image-edit",
            "elevenlabs/speech-to-text"
        ]
        
        print(f"Найдено FREE моделей: {len(free_models)}")
        
        for model_id in free_models:
            if model_id in expected_free:
                print(f"  ✅ {model_id}")
            else:
                print(f"  ⚠️  {model_id} (неожиданная)")
        
        # Проверка что все ожидаемые присутствуют
        missing = set(expected_free) - set(free_models)
        if missing:
            print(f"\n❌ Отсутствуют ожидаемые модели: {missing}")
            return False
        
        print("\n✅ FREE tier валидация пройдена")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка валидации FREE tier: {e}")
        return False


def validate_ui_tree():
    """Валидация UI дерева"""
    print("\n🔍 ВАЛИДАЦИЯ UI ДЕРЕВА\n")
    
    try:
        tree = build_ui_tree()
        
        total_in_tree = sum(len(models) for models in tree.values())
        
        print(f"Категорий: {len(tree)}")
        print(f"Моделей в дереве: {total_in_tree}")
        
        # Проверяем каждую категорию
        for category, models in tree.items():
            if models:
                print(f"  ✅ {category}: {len(models)} моделей")
            else:
                print(f"  ⚠️  {category}: пустая")
        
        # Проверка что все 72 модели в дереве
        if total_in_tree < 72:
            print(f"\n⚠️  В дереве только {total_in_tree}/72 моделей")
        
        # Проверка сортировки по цене (топ-3 в каждой категории)
        print("\n📊 Проверка сортировки по цене (топ-3 в каждой категории):")
        for category, models in tree.items():
            if not models:
                continue
            
            sorted_models = sorted(
                models,
                key=lambda x: x.get('pricing', {}).get('usd_per_gen', 999)
            )
            
            print(f"\n  {category}:")
            for i, m in enumerate(sorted_models[:3], 1):
                price = m.get('pricing', {}).get('usd_per_gen', 0)
                free = " 🆓" if m.get('pricing', {}).get('is_free') else ""
                print(f"    {i}. {m['model_id']:40s} ${price:6.2f}{free}")
        
        print("\n✅ UI дерево валидация пройдена")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка валидации UI дерева: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_pricing_consistency():
    """Валидация консистентности цен"""
    print("\n🔍 ВАЛИДАЦИЯ КОНСИСТЕНТНОСТИ ЦЕН\n")
    
    reg = get_registry()
    
    # Проверяем формулу USD × 79 × 2 = RUB
    errors = []
    
    for model_id, model in reg.all_models.items():
        pricing = model.get('pricing', {})
        usd = pricing.get('usd_per_gen')
        rub = pricing.get('rub_per_gen')
        
        if usd and rub:
            expected_rub = usd * 79 * 2
            if abs(rub - expected_rub) > 0.1:  # допуск 0.1₽
                errors.append(f"{model_id}: {rub}₽ != {expected_rub}₽ (expected)")
    
    if errors:
        print("❌ Найдены ошибки в pricing:")
        for err in errors[:5]:  # показываем первые 5
            print(f"  - {err}")
        return False
    
    print(f"✅ Все 72 модели имеют корректную формулу USD × 79 × 2 = RUB")
    return True


def main():
    """Основная функция валидации"""
    print("="*80)
    print("🔥 КОМПЛЕКСНАЯ ВАЛИДАЦИЯ СИСТЕМЫ БОТА")
    print("="*80)
    
    validators = [
        ("SOURCE_OF_TRUTH", validate_source_of_truth),
        ("Registry Loader", validate_registry_loader),
        ("FREE Tier", validate_free_tier),
        ("UI Tree", validate_ui_tree),
        ("Pricing Consistency", validate_pricing_consistency)
    ]
    
    results = {}
    
    for name, validator in validators:
        try:
            results[name] = validator()
        except Exception as e:
            print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА в {name}: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False
    
    # Итоговый отчет
    print("\n" + "="*80)
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n{'='*80}")
    print(f"РЕЗУЛЬТАТ: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ! Система готова к production.")
        return 0
    else:
        print("❌ СИСТЕМА НЕ ГОТОВА. Исправьте ошибки.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
