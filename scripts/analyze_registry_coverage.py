#!/usr/bin/env python3
"""
Анализ покрытия моделей в registry v6.3.0
Проверяет полноту данных и выявляет проблемы
"""
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any

REGISTRY_PATH = Path(__file__).parent.parent / "models" / "kie_models_final_truth.json"

def analyze_coverage():
    """Анализ покрытия registry"""
    
    with open(REGISTRY_PATH) as f:
        data = json.load(f)
    
    models = data['models']
    version = data.get('version', 'unknown')
    
    print("=" * 80)
    print("🔍 АНАЛИЗ ПОКРЫТИЯ REGISTRY")
    print("=" * 80)
    print()
    print(f"📦 Registry v{version}")
    print(f"📊 Всего моделей: {len(models)}")
    print()
    
    # Анализ по категориям
    categories = defaultdict(list)
    for model in models:
        cat = model.get('category', 'unknown')
        categories[cat].append(model)
    
    print("📂 РАСПРЕДЕЛЕНИЕ ПО КАТЕГОРИЯМ:")
    for cat, cat_models in sorted(categories.items(), key=lambda x: -len(x[1])):
        print(f"   {cat:25} {len(cat_models):3} моделей")
    print()
    
    # Проверка полноты данных
    problems = {
        'no_description': [],
        'no_use_case': [],
        'no_example': [],
        'no_tags': [],
        'no_pricing': [],
        'no_schema': [],
        'enabled_but_no_tech_id': [],
        'technical_names': []
    }
    
    for model in models:
        mid = model['model_id']
        
        if not model.get('description'):
            problems['no_description'].append(mid)
        if not model.get('use_case'):
            problems['no_use_case'].append(mid)
        if not model.get('example'):
            problems['no_example'].append(mid)
        if not model.get('tags'):
            problems['no_tags'].append(mid)
        
        if not model.get('pricing'):
            problems['no_pricing'].append(mid)
        if not model.get('input_schema'):
            problems['no_schema'].append(mid)
        
        if model.get('enabled', True) and not model.get('tech_model_id'):
            problems['enabled_but_no_tech_id'].append(mid)
        
        # Проверка технических названий
        display_name = model.get('display_name', '')
        if '/' in display_name or display_name.islower():
            problems['technical_names'].append(mid)
    
    print("🔎 ПРОБЛЕМЫ В ДАННЫХ:")
    print()
    
    total_problems = 0
    
    if problems['no_description']:
        print(f"   ❌ Нет описаний: {len(problems['no_description'])} моделей")
        total_problems += len(problems['no_description'])
    else:
        print("   ✅ Описания: 100%")
    
    if problems['no_use_case']:
        print(f"   ❌ Нет use-case: {len(problems['no_use_case'])} моделей")
        total_problems += len(problems['no_use_case'])
    else:
        print("   ✅ Use-cases: 100%")
    
    if problems['no_example']:
        print(f"   ❌ Нет примеров: {len(problems['no_example'])} моделей")
        total_problems += len(problems['no_example'])
    else:
        print("   ✅ Примеры: 100%")
    
    if problems['no_tags']:
        print(f"   ❌ Нет тегов: {len(problems['no_tags'])} моделей")
        total_problems += len(problems['no_tags'])
    else:
        print("   ✅ Теги: 100%")
    
    if problems['no_pricing']:
        print(f"   ⚠️  Нет pricing: {len(problems['no_pricing'])} моделей")
        total_problems += len(problems['no_pricing'])
    else:
        print("   ✅ Pricing: 100%")
    
    if problems['no_schema']:
        print(f"   ⚠️  Нет input_schema: {len(problems['no_schema'])} моделей")
        total_problems += len(problems['no_schema'])
    else:
        print("   ✅ Input schemas: 100%")
    
    if problems['enabled_but_no_tech_id']:
        print(f"   ⚠️  Включены без tech_model_id: {len(problems['enabled_but_no_tech_id'])} моделей")
        for mid in problems['enabled_but_no_tech_id'][:5]:
            print(f"      - {mid}")
        total_problems += len(problems['enabled_but_no_tech_id'])
    else:
        print("   ✅ Tech IDs: все enabled модели настроены")
    
    if problems['technical_names']:
        print(f"   ⚠️  Технические названия: {len(problems['technical_names'])} моделей")
        for mid in problems['technical_names'][:5]:
            model = next(m for m in models if m['model_id'] == mid)
            print(f"      - {mid}: '{model.get('display_name')}'")
        if len(problems['technical_names']) > 5:
            print(f"      ... и ещё {len(problems['technical_names']) - 5}")
    else:
        print("   ✅ Display names: все улучшены")
    
    print()
    
    # Статистика по ценам
    prices = []
    for model in models:
        pricing = model.get('pricing', {})
        if 'rub_per_generation' in pricing:
            prices.append(pricing['rub_per_generation'])
    
    if prices:
        print("💰 СТАТИСТИКА ЦЕН:")
        print(f"   Минимум: {min(prices):.2f}₽")
        print(f"   Максимум: {max(prices):.2f}₽")
        print(f"   Средняя: {sum(prices)/len(prices):.2f}₽")
        print(f"   Моделей с ценами: {len(prices)}/{len(models)}")
        print()
    
    # TOP-5 самых дешёвых
    cheapest = sorted(
        [m for m in models if m.get('pricing', {}).get('rub_per_generation')],
        key=lambda m: m['pricing']['rub_per_generation']
    )[:5]
    
    print("💎 TOP-5 САМЫХ ДЕШЁВЫХ:")
    for i, model in enumerate(cheapest, 1):
        price = model['pricing']['rub_per_generation']
        name = model['display_name']
        print(f"   {i}. {name:30} {price:>6.2f}₽")
    print()
    
    # Итог
    print("=" * 80)
    print("📊 ИТОГО:")
    print("=" * 80)
    
    if total_problems == 0:
        print("✅ REGISTRY В ОТЛИЧНОМ СОСТОЯНИИ")
        print("   Все критические данные заполнены")
        print("   Готово к production")
    else:
        print(f"⚠️  НАЙДЕНО {total_problems} ПРОБЛЕМ")
        print("   Требуется дополнительная работа")
    
    print()
    
    # Следующие шаги
    print("🚀 РЕКОМЕНДУЕМЫЕ СЛЕДУЮЩИЕ ШАГИ:")
    print()
    
    next_steps = []
    
    if problems['enabled_but_no_tech_id']:
        next_steps.append({
            'priority': 'P0',
            'issue': f"{len(problems['enabled_but_no_tech_id'])} моделей включены без tech_model_id",
            'action': 'Добавить tech_model_id или выключить модели'
        })
    
    if problems['technical_names']:
        next_steps.append({
            'priority': 'P1',
            'issue': f"{len(problems['technical_names'])} моделей с техническими названиями",
            'action': 'Улучшить display_name для лучшей UX'
        })
    
    if not next_steps:
        next_steps.append({
            'priority': 'P1',
            'issue': 'Registry актуален',
            'action': 'Интегрировать UX данные в UI (показывать descriptions/examples)'
        })
        next_steps.append({
            'priority': 'P2',
            'issue': 'Нет smoke-тестов',
            'action': 'Протестировать 5 cheapest моделей с реальным API (~7₽)'
        })
    
    for i, step in enumerate(next_steps, 1):
        print(f"{i}. [{step['priority']}] {step['issue']}")
        print(f"   → {step['action']}")
        print()

if __name__ == "__main__":
    analyze_coverage()
