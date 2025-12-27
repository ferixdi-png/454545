#!/usr/bin/env python3
"""
Скрейп цен для моделей без pricing
"""
import json
import httpx
from pathlib import Path
from bs4 import BeautifulSoup
import time

# ФИКСИРОВАННЫЙ КУРС ДОЛЛАРА
FIXED_RATE = 79.0

MISSING_MODELS = [
    'z-image/z-image',
    'grok-imagine/upscale',
    'grok-imagine/text-to-image',
    'grok-imagine/image-to-image',
    'kling/text-to-video',
    'kling/image-to-video',
    'sora2/sora-2-image-to-video',
    'sora2/sora-2-text-to-video',
    'sora2/sora-2-pro-image-to-video',
    'sora2/sora-2-pro-text-to-video',
    'sora2/sora-watermark-remover',
    'sora-2-pro-storyboard/index',
    'qwen/image-to-image',
    'qwen/text-to-image',
    'google/nano-banana-edit',
]


def scrape_model_pricing(model_id: str) -> dict | None:
    """Скрейп pricing для одной модели с docs.kie.ai"""
    
    # Формируем URL
    slug = model_id.replace('/', '-')
    url = f"https://docs.kie.ai/{slug}"
    
    print(f"\n🌐 Fetching: {url}")
    
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.get(url, follow_redirects=True)
            resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Ищем pricing в тексте страницы
        # Обычно формат: "$X per generation" или "X credits per generation"
        
        text = soup.get_text()
        
        # Паттерны поиска
        import re
        
        # $X per generation
        usd_match = re.search(r'\$(\d+(?:\.\d+)?)\s*per\s+generation', text, re.IGNORECASE)
        # X credits per generation
        credits_match = re.search(r'(\d+(?:\.\d+)?)\s*credits?\s*per\s+generation', text, re.IGNORECASE)
        # Free model
        is_free = 'free' in text.lower() and 'generation' in text.lower()
        
        if usd_match:
            usd = float(usd_match.group(1))
            credits = usd * 200  # 1 USD = 200 credits
            print(f"  ✅ Found: ${usd} per generation")
            return {
                "credits_per_gen": credits,
                "usd_per_gen": usd,
                "rub_per_gen": usd * FIXED_RATE,
                "is_free": False,
                "source": "scraped_from_docs"
            }
        elif credits_match:
            credits = float(credits_match.group(1))
            usd = credits / 200
            print(f"  ✅ Found: {credits} credits per generation (${usd})")
            return {
                "credits_per_gen": credits,
                "usd_per_gen": usd,
                "rub_per_gen": usd * FIXED_RATE,
                "is_free": False,
                "source": "scraped_from_docs"
            }
        elif is_free:
            print(f"  ✅ Found: FREE model")
            return {
                "credits_per_gen": 0,
                "usd_per_gen": 0,
                "rub_per_gen": 0,
                "is_free": True,
                "source": "scraped_from_docs"
            }
        else:
            print(f"  ⚠️  No pricing found on page")
            return None
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def main():
    print("=" * 80)
    print("💰 SCRAPING MISSING MODEL PRICING")
    print("=" * 80)
    
    scraped_pricing = {}
    
    for model_id in MISSING_MODELS:
        pricing = scrape_model_pricing(model_id)
        
        if pricing:
            scraped_pricing[model_id] = pricing
        
        # Rate limiting
        time.sleep(1)
    
    # Сохраняем результаты
    output_file = Path("artifacts/scraped_pricing.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(scraped_pricing, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Saved: {output_file}")
    print(f"   Scraped: {len(scraped_pricing)}/{len(MISSING_MODELS)} models")
    
    # Мержим в registry
    print(f"\n🔄 Merging into registry...")
    
    registry_file = Path("models/KIE_SOURCE_OF_TRUTH.json")
    with open(registry_file, 'r', encoding='utf-8') as f:
        registry = json.load(f)
    
    merged = 0
    for model_id, pricing in scraped_pricing.items():
        if model_id in registry['models']:
            registry['models'][model_id]['pricing'] = pricing
            merged += 1
    
    # Сохраняем
    with open(registry_file, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    
    print(f"   ✅ Merged {merged} models into registry")
    
    # Финальная статистика
    with_pricing = sum(1 for m in registry['models'].values() if m.get('pricing'))
    total = len(registry['models'])
    
    print(f"\n📊 Final coverage:")
    print(f"   {with_pricing}/{total} models ({with_pricing*100//total}%)")


if __name__ == '__main__':
    main()
