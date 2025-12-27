#!/usr/bin/env python3
"""
РЕАЛЬНЫЕ ТЕСТЫ KIE.AI API на самых дешевых моделях
Проверяет что endpoint работает, кредиты списываются, результаты приходят
"""
import os
import sys
import json
import time
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional

# Добавим путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class KieRealTester:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.kie.ai"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.results: List[Dict[str, Any]] = []
        
    def get_balance(self) -> Optional[float]:
        """Получить текущий баланс кредитов"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/users/me",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            # Пробуем разные варианты структуры ответа
            balance = data.get('credits') or data.get('balance') or data.get('data', {}).get('credits')
            
            print(f"📊 Текущий баланс: {balance} credits")
            return balance
        except Exception as e:
            print(f"⚠️  Не удалось получить баланс: {e}")
            return None
    
    def test_model(self, model_id: str, model_data: Dict[str, Any], test_num: int) -> Dict[str, Any]:
        """Протестировать одну модель"""
        print(f"\n{'='*80}")
        print(f"ТЕСТ #{test_num}: {model_id}")
        print(f"{'='*80}")
        
        result = {
            'test_num': test_num,
            'model_id': model_id,
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'error': None,
            'task_id': None,
            'status': None,
            'credits_cost': model_data.get('pricing', {}).get('usd_per_gen', 0) / 0.005
        }
        
        try:
            # Берем первый пример из модели
            examples = model_data.get('examples', [])
            if not examples:
                result['error'] = "No examples in model data"
                print(f"❌ Нет примеров для {model_id}")
                return result
            
            example_payload = examples[0]
            
            # Endpoint из модели
            endpoint = model_data.get('endpoint', '/api/v1/jobs/createTask')
            if endpoint.endswith('\\'):
                endpoint = endpoint[:-1]
            
            full_url = f"{self.base_url}{endpoint}"
            
            print(f"🔧 Endpoint: {endpoint}")
            print(f"💰 Стоимость: ${model_data.get('pricing', {}).get('usd_per_gen', 0):.4f}")
            print(f"📝 Payload preview: {json.dumps(example_payload, ensure_ascii=False)[:200]}...")
            
            # Отправляем запрос
            print(f"\n⏳ Отправка запроса...")
            response = requests.post(
                full_url,
                headers=self.headers,
                json=example_payload,
                timeout=30
            )
            
            print(f"📡 Status: {response.status_code}")
            
            response_data = response.json()
            print(f"📦 Response: {json.dumps(response_data, ensure_ascii=False)[:300]}...")
            
            # Проверяем успешность
            if response.status_code in [200, 201]:
                # Извлекаем task_id из разных вариантов структуры
                task_id = (
                    response_data.get('task_id') or 
                    response_data.get('taskId') or 
                    response_data.get('data', {}).get('task_id') or
                    response_data.get('data', {}).get('taskId')
                )
                
                if task_id:
                    result['task_id'] = task_id
                    result['success'] = True
                    print(f"✅ SUCCESS! Task ID: {task_id}")
                    
                    # Опционально: проверить статус задачи
                    time.sleep(2)
                    status = self.check_task_status(task_id)
                    result['status'] = status
                    print(f"📊 Task status: {status}")
                else:
                    result['error'] = "No task_id in response"
                    print(f"⚠️  Задача создана но нет task_id в ответе")
            else:
                result['error'] = f"HTTP {response.status_code}: {response_data}"
                print(f"❌ FAILED: HTTP {response.status_code}")
                
        except Exception as e:
            result['error'] = str(e)
            print(f"❌ EXCEPTION: {e}")
        
        self.results.append(result)
        return result
    
    def check_task_status(self, task_id: str) -> Optional[str]:
        """Проверить статус задачи"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/jobs/task/{task_id}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status') or data.get('data', {}).get('status')
                return status
        except Exception as e:
            print(f"⚠️  Не удалось проверить статус: {e}")
        
        return None
    
    def save_results(self, filename: str = "test_results.json"):
        """Сохранить результаты тестов"""
        filepath = os.path.join(os.path.dirname(__file__), '..', 'artifacts', filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'total_tests': len(self.results),
                'successful': sum(1 for r in self.results if r['success']),
                'failed': sum(1 for r in self.results if not r['success']),
                'results': self.results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Результаты сохранены: {filepath}")
    
    def print_summary(self):
        """Вывести итоговую статистику"""
        print(f"\n{'='*80}")
        print("📊 ИТОГОВАЯ СТАТИСТИКА")
        print(f"{'='*80}")
        
        total = len(self.results)
        successful = sum(1 for r in self.results if r['success'])
        failed = total - successful
        
        print(f"Всего тестов: {total}")
        print(f"✅ Успешных: {successful} ({successful/total*100:.1f}%)")
        print(f"❌ Провалено: {failed} ({failed/total*100:.1f}%)")
        
        if failed > 0:
            print(f"\n❌ ОШИБКИ:")
            for r in self.results:
                if not r['success']:
                    print(f"  - {r['model_id']}: {r['error']}")
        
        # Подсчитываем потраченные кредиты
        total_credits = sum(r.get('credits_cost', 0) for r in self.results if r['success'])
        total_usd = total_credits * 0.005
        print(f"\n💰 Потрачено:")
        print(f"  - Кредиты: ~{total_credits:.1f} credits")
        print(f"  - USD: ~${total_usd:.3f}")


def main():
    """Основная функция тестирования"""
    
    # Получаем API ключ
    api_key = os.getenv('KIE_API_KEY')
    if not api_key:
        print("❌ Ошибка: KIE_API_KEY не найден в environment")
        sys.exit(1)
    
    print("🚀 ЗАПУСК РЕАЛЬНЫХ ТЕСТОВ KIE.AI API")
    print("="*80)
    
    # Загружаем registry
    registry_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'KIE_SOURCE_OF_TRUTH.json')
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry = json.load(f)
    
    models = registry['models']
    
    # Сортируем по цене
    sorted_models = sorted(
        models.items(),
        key=lambda x: x[1].get('pricing', {}).get('usd_per_gen', 999999)
    )
    
    # Берем топ-12 самых дешевых
    test_models = sorted_models[:12]
    
    print(f"\n📋 Будет протестировано {len(test_models)} самых дешевых моделей:")
    for i, (model_id, model_data) in enumerate(test_models, 1):
        price = model_data.get('pricing', {}).get('usd_per_gen', 0)
        print(f"  {i:2d}. {model_id:50s} ${price:.4f}")
    
    # Создаем тестер
    tester = KieRealTester(api_key)
    
    # Проверяем баланс до тестов
    print(f"\n{'='*80}")
    balance_before = tester.get_balance()
    
    # Запускаем тесты
    print(f"\n{'='*80}")
    print("🧪 НАЧАЛО ТЕСТИРОВАНИЯ")
    print(f"{'='*80}")
    
    for i, (model_id, model_data) in enumerate(test_models, 1):
        tester.test_model(model_id, model_data, i)
        
        # Небольшая пауза между тестами
        if i < len(test_models):
            time.sleep(1)
    
    # Проверяем баланс после тестов
    print(f"\n{'='*80}")
    balance_after = tester.get_balance()
    
    if balance_before is not None and balance_after is not None:
        spent = balance_before - balance_after
        print(f"💸 Реально потрачено кредитов: {spent:.2f}")
    
    # Выводим статистику
    tester.print_summary()
    
    # Сохраняем результаты
    tester.save_results('real_kie_tests_results.json')
    
    print(f"\n{'='*80}")
    print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
