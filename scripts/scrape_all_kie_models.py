#!/usr/bin/env python3
"""
Автоматический сборщик всех моделей Kie.ai.
Парсит kie.ai/pricing и для каждой модели получает API документацию.
"""
import requests
from bs4 import BeautifulSoup
import json
import time
import re
from urllib.parse import urljoin

BASE_URL = "https://kie.ai"
PRICING_URL = f"{BASE_URL}/pricing"
USD_TO_RUB = 95.0
MARKUP_PERCENT = 50

def fetch_pricing_page():
    """Получить страницу pricing."""
    print(f"📡 Fetching {PRICING_URL}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    response = requests.get(PRICING_URL, headers=headers)
    return response.text

def extract_model_links(html):
    """Извлечь ссылки на все модели."""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Ищем все ссылки на модели
    # Паттерны: /model-name, /provider/model-name
    model_links = set()
    
    for link in soup.find_all('a', href=True):
        href = link['href']
        # Пропускаем служебные ссылки
        if any(skip in href for skip in ['/pricing', '/api-key', '/login', '/signup', '#']):
            continue
        # Добавляем ссылки на модели
        if href.startswith('/') and len(href) > 1:
            model_links.add(href)
    
    return list(model_links)

def fetch_model_page(model_path):
    """Получить страницу конкретной модели."""
    url = urljoin(BASE_URL, model_path)
    print(f"  📄 Fetching {url}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.text
        else:
            print(f"  ⚠️ Status {response.status_code}")
            return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

def extract_pricing_from_table(html):
    """Извлечь pricing из таблицы на странице pricing."""
    soup = BeautifulSoup(html, 'html.parser')
    
    models = []
    
    # Ищем таблицу с ценами
    # На странице pricing должна быть таблица с моделями
    rows = soup.find_all('tr')
    
    for row in rows:
        cells = row.find_all(['td', 'th'])
        if len(cells) >= 3:  # Минимум: model, credits, price
            try:
                # Попытка извлечь данные
                model_cell = cells[0].get_text(strip=True)
                
                # Ищем credits и price
                credits_text = None
                price_text = None
                
                for cell in cells:
                    text = cell.get_text(strip=True)
                    # Ищем числа для credits
                    if re.search(r'\d+\.?\d*\s*(credits?|Credits)', text, re.IGNORECASE):
                        credits_match = re.search(r'(\d+\.?\d*)', text)
                        if credits_match:
                            credits_text = credits_match.group(1)
                    # Ищем цены в USD
                    if re.search(r'\$\s*\d+\.?\d*', text):
                        price_match = re.search(r'\$\s*(\d+\.?\d*)', text)
                        if price_match:
                            price_text = price_match.group(1)
                
                if model_cell and (credits_text or price_text):
                    models.append({
                        'model_name': model_cell,
                        'credits': float(credits_text) if credits_text else None,
                        'price_usd': float(price_text) if price_text else None
                    })
            except Exception as e:
                continue
    
    return models

def parse_api_docs_from_page(html, model_id):
    """Парсить API документацию со страницы модели."""
    soup = BeautifulSoup(html, 'html.parser')
    
    model_info = {
        'model_id': model_id,
        'display_name': None,
        'category': None,
        'modality': None,
        'provider': None,
        'input_schema': {
            'required': [],
            'properties': {}
        },
        'pricing': {}
    }
    
    # Ищем заголовок модели
    h1 = soup.find('h1')
    if h1:
        model_info['display_name'] = h1.get_text(strip=True)
    
    # Ищем описание категории
    # Обычно есть теги или badges
    badges = soup.find_all(['span', 'div'], class_=re.compile(r'badge|tag|label', re.I))
    for badge in badges:
        text = badge.get_text(strip=True).lower()
        if 'video' in text:
            model_info['category'] = 'video'
        elif 'image' in text:
            model_info['category'] = 'image'
        elif 'audio' in text or 'music' in text:
            model_info['category'] = 'audio'
    
    # Ищем JSON с параметрами (обычно в script tag или pre)
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string:
            # Ищем JSON структуры
            json_matches = re.findall(r'\{[^{}]*"model"[^{}]*\}', script.string)
            for match in json_matches:
                try:
                    data = json.loads(match)
                    if 'model' in data:
                        model_info['model_id'] = data['model']
                except:
                    pass
    
    return model_info

def main():
    """Основная функция."""
    print("🚀 KIE.AI MODEL SCRAPER")
    print("=" * 80)
    print()
    
    # 1. Получаем страницу pricing
    pricing_html = fetch_pricing_page()
    print(f"✅ Pricing page loaded ({len(pricing_html)} bytes)")
    
    # Сохраняем для отладки
    with open('/workspaces/5656/kie_pricing_full.html', 'w', encoding='utf-8') as f:
        f.write(pricing_html)
    print("💾 Saved to kie_pricing_full.html")
    print()
    
    # 2. Извлекаем модели из таблицы
    print("📊 Extracting models from pricing table...")
    models = extract_pricing_from_table(pricing_html)
    print(f"✅ Found {len(models)} models in pricing table")
    print()
    
    # 3. Извлекаем ссылки на модели
    print("🔗 Extracting model links...")
    model_links = extract_model_links(pricing_html)
    print(f"✅ Found {len(model_links)} model links")
    print()
    
    # Показываем первые 20 ссылок
    print("📋 First 20 model links:")
    for i, link in enumerate(model_links[:20], 1):
        print(f"  {i}. {link}")
    print()
    
    # 4. Для каждой ссылки получаем детали (лимит 10 для начала)
    detailed_models = []
    
    print("📖 Fetching model details (first 10)...")
    for i, link in enumerate(model_links[:10], 1):
        print(f"\n{i}/{min(10, len(model_links))}: {link}")
        
        model_html = fetch_model_page(link)
        if model_html:
            model_id = link.strip('/')
            model_info = parse_api_docs_from_page(model_html, model_id)
            detailed_models.append(model_info)
            
            # Сохраняем HTML для отладки
            safe_name = model_id.replace('/', '_')
            with open(f'/workspaces/5656/model_{safe_name}.html', 'w', encoding='utf-8') as f:
                f.write(model_html)
            print(f"  💾 Saved HTML")
        
        time.sleep(0.5)  # Rate limiting
    
    # 5. Сохраняем результаты
    output = {
        'version': '5.1.0-scraped',
        'source': 'kie.ai/pricing (automated scraper)',
        'generated_at': '2024-12-24',
        'total_models_found': len(models),
        'total_links_found': len(model_links),
        'detailed_models_scraped': len(detailed_models),
        'models_from_table': models,
        'model_links': model_links,
        'detailed_models': detailed_models
    }
    
    with open('/workspaces/5656/models/kie_scraped_models.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print()
    print("=" * 80)
    print("✅ SCRAPING COMPLETE")
    print(f"📊 Total models in pricing table: {len(models)}")
    print(f"🔗 Total model links found: {len(model_links)}")
    print(f"📖 Detailed models scraped: {len(detailed_models)}")
    print(f"💾 Saved to models/kie_scraped_models.json")
    print()
    
    # Показываем пример scraped модели
    if detailed_models:
        print("📋 Example scraped model:")
        print(json.dumps(detailed_models[0], indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
