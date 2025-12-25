#!/usr/bin/env python3
"""
ПАРСИНГ РЕАЛЬНЫХ ЦЕН С KIE.AI
Единственный источник правды - страницы моделей на kie.ai
Парсим ОДИН РАЗ и фиксируем навсегда
"""
import json
import httpx
import re
import time
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Dict, Optional


# ФОРМУЛА ЦЕНООБРАЗОВАНИЯ (как требует пользователь)
# RUB = USD × КУРС × 2
EXCHANGE_RATE = 79.0  # RUB/USD
MARKUP = 2.0  # Наценка ×2


def parse_pricing_from_page(url: str) -> Optional[Dict]:
    """
    Парсим цену со страницы модели на kie.ai
    
    Ищем паттерны:
    - "X Kie credits per image (≈ $Y)"
    - "$X per generation"
    - "X credits/gen"
    """
    print(f"  Fetching: {url}")
    
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        
        # Паттерн 1: "X Kie credits per image (≈ $Y)"
        pattern1 = re.search(
            r'([\d.]+)\s+Kie\s+credits\s+per\s+\w+\s*\(≈\s*\$\s*([\d.]+)\)',
            text,
            re.IGNORECASE
        )
        
        if pattern1:
            credits = float(pattern1.group(1))
            usd = float(pattern1.group(2))
            print(f"    ✅ Found: {credits} credits ≈ ${usd}")
            return {
                'credits_per_gen': credits,
                'usd_per_gen': usd,
                'source': 'kie.ai_page_credits_usd'
            }
        
        # Паттерн 2: "$X per generation/image/video"
        pattern2 = re.search(
            r'\$\s*([\d.]+)\s+per\s+(generation|image|video|audio)',
            text,
            re.IGNORECASE
        )
        
        if pattern2:
            usd = float(pattern2.group(1))
            credits = usd * 200  # 1 USD = 200 credits
            print(f"    ✅ Found: ${usd} per {pattern2.group(2)}")
            return {
                'credits_per_gen': credits,
                'usd_per_gen': usd,
                'source': 'kie.ai_page_usd'
            }
        
        # Паттерн 3: "X credits per generation"
        pattern3 = re.search(
            r'([\d.]+)\s+credits?\s+per\s+(generation|image|video|audio)',
            text,
            re.IGNORECASE
        )
        
        if pattern3:
            credits = float(pattern3.group(1))
            usd = credits / 200
            print(f"    ✅ Found: {credits} credits per {pattern3.group(2)}")
            return {
                'credits_per_gen': credits,
                'usd_per_gen': usd,
                'source': 'kie.ai_page_credits'
            }
        
        # Паттерн 4: Free model
        if 'free' in text.lower() and ('generation' in text.lower() or 'no cost' in text.lower()):
            print(f"    ✅ Found: FREE model")
            return {
                'credits_per_gen': 0,
                'usd_per_gen': 0,
                'is_free': True,
                'source': 'kie.ai_page_free'
            }
        
        print(f"    ⚠️  No pricing found")
        return None
        
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return None


def build_model_url(model_id: str, slug: str = None) -> list:
    """
    Строим возможные URL страницы модели
    Возвращаем список вариантов для проверки
    """
    urls = []
    
    if slug:
        # Вариант 1: С market/
        urls.append(f"https://kie.ai/{slug}")
        
        # Вариант 2: Без market/
        clean_slug = slug.replace('market/', '')
        urls.append(f"https://kie.ai/{clean_slug}")
    
    # Вариант 3: Прямо model_id
    urls.append(f"https://kie.ai/{model_id}")
    
    # Вариант 4: Последняя часть model_id (для z-image)
    if '/' in model_id:
        last_part = model_id.split('/')[-1]
        urls.append(f"https://kie.ai/{last_part}")
    
    return list(dict.fromkeys(urls))  # Убираем дубликаты


def parse_all_models_prices():
    """Парсим цены для ВСЕХ моделей"""
    
    # Загружаем registry
    with open('models/KIE_SOURCE_OF_TRUTH.json', 'r') as f:
        registry = json.load(f)
    
    models = registry['models']
    
    print("=" * 80)
    print("💰 PARSING REAL PRICES FROM KIE.AI")
    print("=" * 80)
    print(f"\nTotal models: {len(models)}")
    print(f"Exchange rate: {EXCHANGE_RATE} RUB/USD")
    print(f"Markup: ×{MARKUP}")
    print(f"Formula: RUB = USD × {EXCHANGE_RATE} × {MARKUP} = USD × {EXCHANGE_RATE * MARKUP}")
    
    parsed_prices = {}
    success = 0
    failed = 0
    
    for model_id, model_data in models.items():
        print(f"\n📦 {model_id}")
        
        # Строим возможные URLs
        slug = model_data.get('slug', '')
        urls = build_model_url(model_id, slug)
        
        # Пробуем все варианты URL
        pricing_data = None
        for url in urls:
            pricing_data = parse_pricing_from_page(url)
            if pricing_data:
                break  # Нашли цену - прекращаем поиск
        
        if pricing_data:
            # Применяем формулу ценообразования
            usd = pricing_data['usd_per_gen']
            credits = pricing_data['credits_per_gen']
            
            # RUB = USD × курс × 2
            rub = usd * EXCHANGE_RATE * MARKUP
            
            parsed_prices[model_id] = {
                'credits_per_gen': credits,
                'usd_per_gen': usd,
                'rub_per_gen': rub,
                'is_free': pricing_data.get('is_free', False),
                'source': pricing_data['source'],
                'parsed_at': time.time()
            }
            
            print(f"    💵 ${usd} → {rub}₽")
            success += 1
        else:
            failed += 1
        
        # Rate limiting
        time.sleep(1.5)
    
    print(f"\n" + "=" * 80)
    print(f"📊 PARSING COMPLETE")
    print(f"=" * 80)
    print(f"✅ Success: {success}/{len(models)}")
    print(f"❌ Failed: {failed}/{len(models)}")
    
    # Сохраняем результаты
    output_file = Path('artifacts/real_prices_from_kie.json')
    with open(output_file, 'w') as f:
        json.dump(parsed_prices, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Saved: {output_file}")
    
    return parsed_prices


def apply_prices_to_registry(parsed_prices: Dict):
    """Применяем спарсенные цены к registry"""
    
    with open('models/KIE_SOURCE_OF_TRUTH.json', 'r') as f:
        registry = json.load(f)
    
    print("\n" + "=" * 80)
    print("🔄 APPLYING PRICES TO REGISTRY")
    print("=" * 80)
    
    updated = 0
    
    for model_id, pricing in parsed_prices.items():
        if model_id in registry['models']:
            registry['models'][model_id]['pricing'] = pricing
            updated += 1
    
    # Сохраняем
    with open('models/KIE_SOURCE_OF_TRUTH.json', 'w') as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Updated {updated} models in registry")
    
    # Показываем Top-5 cheapest
    print(f"\n💰 TOP-5 CHEAPEST (after parsing):")
    
    models_with_price = [
        (mid, m['pricing'])
        for mid, m in registry['models'].items()
        if m.get('pricing') and not m['pricing'].get('is_free')
    ]
    
    cheapest = sorted(models_with_price, key=lambda x: x[1]['usd_per_gen'])[:5]
    
    for i, (mid, pricing) in enumerate(cheapest, 1):
        print(f"{i}. {mid}")
        print(f"   USD: ${pricing['usd_per_gen']}")
        print(f"   RUB: {pricing['rub_per_gen']}₽")
        print(f"   Credits: {pricing['credits_per_gen']}")


def main():
    # Парсим цены
    parsed_prices = parse_all_models_prices()
    
    # Применяем к registry
    if parsed_prices:
        apply_prices_to_registry(parsed_prices)
    
    print("\n✅ DONE! Prices are now FIXED from kie.ai")


if __name__ == '__main__':
    main()
