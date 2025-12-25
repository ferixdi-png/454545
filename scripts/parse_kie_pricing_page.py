#!/usr/bin/env python3
"""
Парсинг ВСЕХ цен с https://kie.ai/pricing
ЕДИНСТВЕННЫЙ ИСТОЧНИК ИСТИНЫ ДЛЯ ЦЕН
"""
import httpx
from bs4 import BeautifulSoup
import json
import re
from pathlib import Path


def scrape_pricing_page():
    """Парсинг pricing page"""
    
    url = "https://kie.ai/pricing"
    
    print("=" * 80)
    print("💰 SCRAPING KIE.AI PRICING PAGE")
    print("=" * 80)
    print(f"\n🌐 URL: {url}")
    
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Сохраняем HTML для анализа
        cache_dir = Path('cache')
        cache_dir.mkdir(exist_ok=True)
        
        with open(cache_dir / 'kie_pricing_page.html', 'w', encoding='utf-8') as f:
            f.write(resp.text)
        
        print(f"✅ HTML saved to cache/kie_pricing_page.html")
        
        # Парсим pricing таблицу
        pricing_data = {}
        
        # Ищем все модели и цены
        # Вариант 1: Таблицы
        tables = soup.find_all('table')
        print(f"\n📊 Found {len(tables)} tables")
        
        for i, table in enumerate(tables):
            rows = table.find_all('tr')
            print(f"\n  Table {i+1}: {len(rows)} rows")
            
            for row in rows[:5]:  # Показываем первые 5
                cells = row.find_all(['td', 'th'])
                if cells:
                    text = ' | '.join(c.get_text(strip=True) for c in cells)
                    print(f"    {text[:100]}")
        
        # Вариант 2: Карточки/блоки с ценами
        # Ищем все элементы с $ или credits
        price_elements = soup.find_all(string=re.compile(r'\$\d+|\d+\s*credits?', re.IGNORECASE))
        print(f"\n💵 Found {len(price_elements)} price mentions")
        
        for elem in price_elements[:10]:
            parent = elem.parent
            # Ищем model name рядом
            siblings = parent.find_all(string=True)
            context = ' '.join(s.strip() for s in siblings if s.strip())
            print(f"  {context[:150]}")
        
        # Вариант 3: JSON data в script tags
        scripts = soup.find_all('script')
        print(f"\n📜 Found {len(scripts)} script tags")
        
        for script in scripts:
            if script.string and ('pricing' in script.string.lower() or 'models' in script.string.lower()):
                # Пытаемся извлечь JSON
                content = script.string
                
                # Ищем JSON объекты
                json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content)
                
                for match in json_matches[:3]:
                    try:
                        data = json.loads(match)
                        if 'price' in str(data).lower() or 'model' in str(data).lower():
                            print(f"\n  Found JSON data: {str(data)[:200]}")
                    except:
                        pass
        
        # Вариант 4: Поиск по классам
        price_containers = soup.find_all(class_=re.compile(r'price|pricing|cost|model', re.IGNORECASE))
        print(f"\n🏷️  Found {len(price_containers)} elements with price-related classes")
        
        for elem in price_containers[:10]:
            print(f"  {elem.name}.{elem.get('class')}: {elem.get_text(strip=True)[:100]}")
        
        return pricing_data
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    pricing = scrape_pricing_page()
    
    if pricing is not None:
        # Сохраняем
        output = Path('artifacts/pricing_from_page.json')
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(pricing, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Saved: {output}")
        print(f"   Models: {len(pricing)}")
    else:
        print("\n⚠️  No pricing data extracted, check HTML manually")
        print("   File: cache/kie_pricing_page.html")


if __name__ == '__main__':
    main()
