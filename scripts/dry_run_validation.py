"""
Dry-run валидация: проверка payload формирования БЕЗ реальных запросов к API.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.kie.builder import load_source_of_truth, build_payload, get_model_schema
from app.payments.pricing import calculate_kie_cost, calculate_user_price
import json


def validate_schema_coverage():
    """Проверяет что у всех моделей есть input_schema."""
    print("\n" + "="*80)
    print("🔍 ПРОВЕРКА НАЛИЧИЯ input_schema У ВСЕХ МОДЕЛЕЙ")
    print("="*80)
    
    sot = load_source_of_truth()
    models = sot.get('models', {})
    
    missing_schema = []
    valid_schema = []
    
    for model_id, model in models.items():
        schema = model.get('input_schema')
        if not schema:
            missing_schema.append(model_id)
        else:
            valid_schema.append(model_id)
    
    print(f"\n✅ Модели с input_schema: {len(valid_schema)}/72")
    print(f"❌ Модели БЕЗ input_schema: {len(missing_schema)}/72")
    
    if missing_schema:
        print(f"\n⚠️  Модели без схемы (первые 10):")
        for mid in missing_schema[:10]:
            print(f"   • {mid}")
        if len(missing_schema) > 10:
            print(f"   ... и ещё {len(missing_schema) - 10}")
    
    return len(missing_schema) == 0


def validate_payload_building():
    """Проверяет что payload можно собрать для топ-10 дешёвых моделей."""
    print("\n" + "="*80)
    print("🔍 DRY-RUN: СБОРКА PAYLOAD ДЛЯ ДЕШЁВЫХ МОДЕЛЕЙ")
    print("="*80)
    
    sot = load_source_of_truth()
    models = sot.get('models', {})
    
    # Найти дешёвые модели
    cheap = []
    for model_id, model in models.items():
        pricing = model.get('pricing', {})
        rub = pricing.get('rub_per_gen', 99999)
        if rub < 5:  # дешевле 5 рублей
            cheap.append((model_id, rub, model))
    
    cheap.sort(key=lambda x: x[1])
    
    print(f"\n💰 Найдено {len(cheap)} моделей дешевле 5₽")
    print(f"\n🧪 Тестирую сборку payload для топ-10:")
    
    success = []
    failed = []
    
    for model_id, price, model in cheap[:10]:
        try:
            # Простейший input для теста
            user_inputs = {"prompt": "test"}
            
            # Попытка собрать payload
            payload = build_payload(model_id, user_inputs, sot)
            
            # Проверка что payload имеет нужные поля
            assert 'model' in payload, f"No 'model' in payload"
            assert 'input' in payload, f"No 'input' in payload"
            
            success.append(model_id)
            print(f"   ✅ {model_id} ({price}₽)")
            
        except Exception as e:
            failed.append((model_id, str(e)))
            print(f"   ❌ {model_id} ({price}₽): {e}")
    
    print(f"\n📊 Результат:")
    print(f"   ✅ Успешно собран payload: {len(success)}/10")
    print(f"   ❌ Ошибки: {len(failed)}/10")
    
    if failed:
        print(f"\n⚠️  Модели с ошибками:")
        for mid, err in failed:
            print(f"   • {mid}: {err[:60]}...")
    
    return len(failed) == 0


def validate_pricing_calculation():
    """Проверяет что ценообразование работает корректно."""
    print("\n" + "="*80)
    print("�� ПРОВЕРКА ЦЕНООБРАЗОВАНИЯ")
    print("="*80)
    
    sot = load_source_of_truth()
    models = sot.get('models', {})
    
    errors = []
    
    for model_id, model in list(models.items())[:10]:  # Проверяем первые 10
        try:
            # Вычисляем цену
            kie_cost = calculate_kie_cost(model, {})
            user_price = calculate_user_price(kie_cost)
            
            # Проверка формулы x2
            expected = round(kie_cost * 2, 2)
            if user_price != expected:
                errors.append(f"{model_id}: user_price={user_price} != kie_cost*2={expected}")
            
        except Exception as e:
            errors.append(f"{model_id}: {str(e)}")
    
    if errors:
        print(f"\n❌ Найдены ошибки ({len(errors)}):")
        for err in errors[:5]:
            print(f"   • {err}")
        return False
    else:
        print(f"\n✅ Все проверенные модели имеют корректное ценообразование (x2)")
        return True


def validate_free_models():
    """Проверяет что бесплатные модели определяются правильно."""
    print("\n" + "="*80)
    print("🔍 ПРОВЕРКА БЕСПЛАТНЫХ МОДЕЛЕЙ")
    print("="*80)
    
    sot = load_source_of_truth()
    models = sot.get('models', {})
    
    free_models = []
    for model_id, model in models.items():
        pricing = model.get('pricing', {})
        rub = pricing.get('rub_per_gen', 99999)
        is_free = pricing.get('is_free', False)
        
        if rub == 0 or is_free:
            free_models.append(model_id)
    
    print(f"\n💰 Найдено {len(free_models)} бесплатных моделей:")
    for mid in free_models:
        print(f"   • {mid}")
    
    # Проверка что это именно те 4 модели
    expected_free = ['z-image', 'qwen/text-to-image', 'qwen/image-to-image', 'qwen/image-edit']
    
    all_found = all(m in free_models for m in expected_free)
    if all_found:
        print(f"\n✅ Все ожидаемые бесплатные модели найдены")
        return True
    else:
        missing = [m for m in expected_free if m not in free_models]
        print(f"\n⚠️  Не найдены бесплатные модели: {missing}")
        return len(missing) == 0


if __name__ == "__main__":
    print("\n╔═══════════════════════════════════════════════════════════════════════╗")
    print("║           ШАГ 3A: DRY-RUN ВАЛИДАЦИЯ (БЕЗ ГЕНЕРАЦИЙ)                 ║")
    print("╚═══════════════════════════════════════════════════════════════════════╝")
    
    results = []
    results.append(("Наличие input_schema", validate_schema_coverage()))
    results.append(("Сборка payload", validate_payload_building()))
    results.append(("Ценообразование", validate_pricing_calculation()))
    results.append(("Бесплатные модели", validate_free_models()))
    
    print("\n" + "="*80)
    print("📊 ИТОГОВЫЙ ОТЧЁТ DRY-RUN")
    print("="*80)
    
    all_passed = True
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"   {status} {name}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 ВСЕ DRY-RUN ПРОВЕРКИ ПРОЙДЕНЫ!")
        print("✅ Готово к реальным генерациям на дешёвых моделях")
        sys.exit(0)
    else:
        print("\n⚠️  НЕКОТОРЫЕ ПРОВЕРКИ НЕ ПРОШЛИ")
        print("❌ Исправьте ошибки перед реальными генерациями")
        sys.exit(1)
