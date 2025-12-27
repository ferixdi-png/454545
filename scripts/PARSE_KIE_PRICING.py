#!/usr/bin/env python3
"""
🎯 KIE.AI PRICING PARSER - ПОЛНЫЙ СПИСОК МОДЕЛЕЙ

Парсит kie.ai/pricing чтобы получить:
1. ВСЕ модели с их названиями
2. Цены в credits
3. Категории моделей

Затем мапит их на endpoints из docs.kie.ai

ЦЕЛЬ: Создать ПОЛНЫЙ SOURCE OF TRUTH со всеми моделями + endpoints + pricing
"""
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Dict, List, Any
from datetime import datetime


def parse_pricing_page() -> Dict[str, Any]:
    """Парсить kie.ai/pricing"""
    html_file = Path("cache/kie_pricing_page.html")
    
    if not html_file.exists():
        print("❌ Pricing page not cached")
        return {}
    
    html = html_file.read_text(encoding='utf-8')
    soup = BeautifulSoup(html, 'lxml')
    
    models = []
    
    # Ищем таблицы с pricing
    tables = soup.find_all('table')
    
    print(f"📊 Found {len(tables)} tables")
    
    for table_idx, table in enumerate(tables):
        rows = table.find_all('tr')
        
        for row in rows[1:]:  # Skip header
            cells = row.find_all(['td', 'th'])
            
            if len(cells) >= 2:
                # Извлекаем название модели
                model_name = cells[0].get_text(strip=True)
                
                # Извлекаем цену
                price_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                
                # Парсим credits
                credits_match = re.search(r'([\d.]+)\s*credits?', price_text, re.IGNORECASE)
                usd_match = re.search(r'\$\s*([\d.]+)', price_text)
                
                if model_name and (credits_match or usd_match):
                    model_data = {
                        'display_name': model_name,
                        'table_index': table_idx,
                        'pricing': {}
                    }
                    
                    if credits_match:
                        model_data['pricing']['credits_per_gen'] = float(credits_match.group(1))
                    
                    if usd_match:
                        model_data['pricing']['usd_per_gen'] = float(usd_match.group(1))
                    
                    models.append(model_data)
    
    # Также ищем через React data (Next.js)
    scripts = soup.find_all('script', id='__NEXT_DATA__')
    for script in scripts:
        try:
            data = json.loads(script.string)
            # Извлекаем модели из Next.js data если есть
            props = data.get('props', {}).get('pageProps', {})
            # Здесь может быть pricing data
        except:
            pass
    
    return {
        'total_models': len(models),
        'models': models
    }


def load_docs_structure():
    """Загрузить спарсенную структуру docs"""
    docs_file = Path("models/kie_docs_deep_parse.json")
    
    if docs_file.exists():
        with open(docs_file) as f:
            return json.load(f)
    return {}


def map_pricing_to_docs(pricing_data: Dict, docs_data: Dict) -> List[Dict]:
    """
    Мапим модели из pricing на endpoints из docs
    
    Логика:
    1. Для каждой модели из pricing
    2. Пытаемся найти соответствующий API в docs
    3. Мапим на правильный endpoint
    """
    models = []
    
    # Категории API из docs
    api_categories = {
        'veo': {
            'endpoint': '/api/v1/veo/generate',
            'keywords': ['veo', 'google veo', 'veo3'],
            'models': ['veo3', 'veo3_fast']
        },
        'runway': {
            'endpoint': '/api/v1/runway/generate',
            'keywords': ['runway', 'gen-3', 'gen-2'],
            'models': []
        },
        'suno': {
            'endpoint': '/api/v1/generate',
            'keywords': ['suno', 'music', 'audio'],
            'models': ['V3_5', 'V4']
        },
        'flux': {
            'endpoint': '/api/v1/flux/kontext/generate',
            'keywords': ['flux', 'kontext'],
            'models': ['flux-kontext-pro', 'flux-kontext-max']
        },
        '4o-image': {
            'endpoint': '/api/v1/gpt4o-image/generate',
            'keywords': ['4o', 'gpt-4o', 'openai'],
            'models': []
        }
    }
    
    for model in pricing_data.get('models', []):
        display_name = model['display_name'].lower()
        
        # Пытаемся определить категорию
        matched_category = None
        
        for cat_name, cat_data in api_categories.items():
            for keyword in cat_data['keywords']:
                if keyword.lower() in display_name:
                    matched_category = cat_name
                    break
            if matched_category:
                break
        
        if matched_category:
            model['api_category'] = matched_category
            model['endpoint'] = api_categories[matched_category]['endpoint']
            model['possible_model_ids'] = api_categories[matched_category]['models']
        else:
            model['api_category'] = 'unknown'
            model['endpoint'] = None
        
        models.append(model)
    
    return models


def main():
    print("="*80)
    print("🎯 PARSING KIE.AI PRICING")
    print("="*80)
    
    # Step 1: Parse pricing
    print("\n📖 Step 1: Parsing pricing page...")
    pricing_data = parse_pricing_page()
    
    print(f"   Found {pricing_data.get('total_models', 0)} models with pricing")
    
    # Step 2: Load docs structure
    print("\n📖 Step 2: Loading docs structure...")
    docs_data = load_docs_structure()
    
    # Step 3: Map pricing to docs
    print("\n📖 Step 3: Mapping pricing → docs...")
    mapped_models = map_pricing_to_docs(pricing_data, docs_data)
    
    # Stats
    by_category = {}
    for model in mapped_models:
        cat = model.get('api_category', 'unknown')
        by_category[cat] = by_category.get(cat, 0) + 1
    
    print(f"\n📊 Models by category:")
    for cat, count in sorted(by_category.items()):
        print(f"   {cat}: {count} models")
    
    # Step 4: Save results
    output = {
        'version': 'PRICING_MAPPED_1.0',
        'parsed_at': datetime.now().isoformat(),
        'source': 'kie.ai/pricing + docs.kie.ai',
        'total_models': len(mapped_models),
        'models': mapped_models,
        'summary': {
            'by_category': by_category,
            'with_endpoint': len([m for m in mapped_models if m.get('endpoint')]),
            'without_endpoint': len([m for m in mapped_models if not m.get('endpoint')])
        }
    }
    
    output_file = Path("models/kie_pricing_mapped.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Saved: {output_file}")
    print(f"\n📊 Summary:")
    print(f"   Total models: {output['total_models']}")
    print(f"   With endpoint: {output['summary']['with_endpoint']}")
    print(f"   Without endpoint: {output['summary']['without_endpoint']}")
    
    # Show samples
    print(f"\n📋 Sample mapped models:")
    for model in mapped_models[:5]:
        print(f"\n   {model['display_name']}")
        print(f"      Category: {model.get('api_category', 'N/A')}")
        print(f"      Endpoint: {model.get('endpoint', 'N/A')}")
        print(f"      Credits: {model.get('pricing', {}).get('credits_per_gen', 'N/A')}")


if __name__ == "__main__":
    main()
