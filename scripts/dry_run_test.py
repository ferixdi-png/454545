"""
Dry-run тестирование генераций БЕЗ трат реальных кредитов.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any
import sys

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.kie.builder import build_payload, load_source_of_truth
from app.kie.validator import ModelContractError


def test_model_payload(model_id: str, model_data: Dict[str, Any], sot: Dict) -> Dict[str, Any]:
    """Тест payload для одной модели (dry-run)."""
    result = {
        'model_id': model_id,
        'success': False,
        'error': None,
        'payload_keys': None,
        'input_keys': None
    }
    
    try:
        examples = model_data.get('examples', [])
        if not examples:
            result['error'] = "No examples available"
            return result
        
        first_example = examples[0]
        
        # Извлекаем user inputs из примера
        if 'input' in first_example and isinstance(first_example['input'], dict):
            user_inputs = first_example['input']
        else:
            user_inputs = {k: v for k, v in first_example.items() 
                          if k not in {'model', 'callBackUrl', 'callback', 'webhookUrl'}}
        
        if not user_inputs:
            result['error'] = "No user inputs in example"
            return result
        
        # Строим payload
        payload = build_payload(
            model_id=model_id,
            user_inputs=user_inputs,
            source_of_truth=sot
        )
        
        # Проверяем структуру
        if 'model' not in payload:
            result['error'] = "Missing 'model' field in payload"
            return result
        
        if 'input' not in payload:
            result['error'] = "Missing 'input' field in payload"
            return result
        
        if not isinstance(payload['input'], dict):
            result['error'] = "'input' is not a dict"
            return result
        
        # Успех!
        result['success'] = True
        result['payload_keys'] = list(payload.keys())
        result['input_keys'] = list(payload['input'].keys())
        
    except ModelContractError as e:
        result['error'] = f"Validation error: {str(e)}"
    except Exception as e:
        result['error'] = f"Unexpected error: {type(e).__name__}: {str(e)}"
    
    return result


def main():
    print("="*100)
    print("🧪 DRY-RUN ТЕСТИРОВАНИЕ ВСЕХ МОДЕЛЕЙ")
    print("="*100)
    print("\n⚠️  БЕЗ РЕАЛЬНЫХ API ЗАПРОСОВ - НЕ ТРАТИМ КРЕДИТЫ!\n")
    
    sot = load_source_of_truth()
    models = sot.get("models", {})
    total = len(models)
    
    print(f"📊 Всего моделей: {total}\n")
    
    results = []
    success_count = 0
    failed_count = 0
    
    for i, (model_id, model_data) in enumerate(models.items(), 1):
        if i % 10 == 0 or i == 1:
            print(f"[{i}/{total}] Тестирование...")
        
        result = test_model_payload(model_id, model_data, sot)
        results.append(result)
        
        if result['success']:
            success_count += 1
        else:
            failed_count += 1
            print(f"\n❌ [{i}/{total}] {model_id}")
            print(f"   Ошибка: {result['error']}")
    
    print("\n" + "="*100)
    print("📊 ФИНАЛЬНЫЙ ОТЧЕТ")
    print("="*100)
    
    print(f"\n✅ Успешно: {success_count}/{total} ({success_count*100//total}%)")
    print(f"❌ Провалено: {failed_count}/{total} ({failed_count*100//total}%)")
    
    if success_count > 0:
        print(f"\n✅ ПРИМЕРЫ УСПЕШНЫХ PAYLOAD:")
        shown = 0
        for result in results:
            if result['success'] and shown < 3:
                print(f"\n   {result['model_id']}:")
                print(f"      Payload keys: {result['payload_keys']}")
                print(f"      Input keys: {result['input_keys']}")
                shown += 1
    
    output_path = Path("artifacts/dry_run_test_results.json")
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'total_models': total,
            'success_count': success_count,
            'failed_count': failed_count,
            'results': results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Результаты: {output_path}")
    print("\n" + "="*100)
    
    if failed_count == 0:
        print("\n🎉 ВСЕ МОДЕЛИ ПРОШЛИ ТЕСТЫ!\n")
        return 0
    else:
        print(f"\n⚠️  {failed_count} моделей провалили тест!\n")
        return 1


if __name__ == "__main__":
    exit(main())
