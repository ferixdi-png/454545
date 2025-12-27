#!/usr/bin/env python3
"""
🎯 MASTER SCRAPER - ЕДИНСТВЕННЫЙ SOURCE OF TRUTH

ЭТО ГЛАВНЫЙ СКРИПТ ПРОЕКТА!
Парсит Kie.ai и создает ОКОНЧАТЕЛЬНЫЙ registry моделей.

ФИЛОСОФИЯ:
1. Извлекаем список ВСЕХ моделей из docs.kie.ai (JSON структура)
2. Для КАЖДОЙ модели - парсим страницу + Copy page/API примеры
3. Извлекаем pricing из API/страницы
4. Создаем ЕДИНЫЙ registry с валидацией
5. Сохраняем как models/KIE_SOURCE_OF_TRUTH.json

ЭТОТ ФАЙЛ ЗАПУСКАЕТСЯ ОДИН РАЗ И СОЗДАЕТ БАЗУ.
Возвращаемся к парсингу ТОЛЬКО если модель не работает.
"""

import re
import json
import httpx
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
import time


class MasterKieScraper:
    """Мастер-парсер Kie.ai - единственный источник правды"""
    
    def __init__(self):
        self.client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        self.cache_dir = Path("cache/kie_model_pages")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.models_registry = {}
        self.pending_models = []
        
    def extract_docs_model_list(self) -> List[Dict[str, str]]:
        """
        Извлекает список всех моделей из docs.kie.ai
        Используя структуру JSON, которая там есть
        """
        
        print("=" * 80)
        print("📚 STEP 1: Extracting model list from docs.kie.ai")
        print("=" * 80)
        
        # Читаем закэшированный docs HTML
        docs_file = Path("cache/kie_docs/_common-api_get-account-credits.html")
        if not docs_file.exists():
            print("❌ Docs cache not found, downloading...")
            try:
                resp = self.client.get("https://docs.kie.ai/")
                docs_file.write_text(resp.text, encoding='utf-8')
            except Exception as e:
                print(f"❌ Error downloading docs: {e}")
                return []
        
        html = docs_file.read_text(encoding='utf-8')
        
        # Извлекаем JSON структуру из Next.js data
        # Паттерн: "pages":[{"group":"Seedream","pages":[...]}]
        
        models = []
        
        # Парсим market/* модели - используем простой grep-like поиск
        market_pattern = r'market/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)'
        market_matches = re.findall(market_pattern, html)
        
        print(f"\n📋 Found {len(market_matches)} market model references")
        
        seen = set()
        for provider, model_slug in market_matches:
            # Пропускаем служебные
            if model_slug == 'get-task-detail' or provider == 'common':
                continue
                
            model_id = f"{provider}/{model_slug}"
            path = f"market/{provider}/{model_slug}"
            
            if model_id not in seen:
                seen.add(model_id)
                
                models.append({
                    "model_id": model_id,
                    "provider": provider,
                    "slug": path,
                    "category": self._infer_category(provider, model_slug)
                })
        
        # Добавляем Veo3, Suno, 4o, Flux из отдельных API
        special_models = [
            {
                "model_id": "veo3/quality",
                "provider": "google",
                "slug": "veo3-api/generate-veo-3-video",
                "category": "video"
            },
            {
                "model_id": "veo3/fast",
                "provider": "google",
                "slug": "veo3-api/generate-veo-3-video",
                "category": "video"
            },
            {
                "model_id": "suno/v4",
                "provider": "suno",
                "slug": "suno-api/generate-music",
                "category": "audio"
            },
            {
                "model_id": "4o-image/standard",
                "provider": "openai",
                "slug": "4o-image-api/create-image",
                "category": "image"
            },
            {
                "model_id": "flux-kontext/pro",
                "provider": "black-forest-labs",
                "slug": "flux-kontext-api/generate-image",
                "category": "image"
            },
        ]
        
        models.extend(special_models)
        
        print(f"✅ Total models extracted: {len(models)}")
        print(f"   - Providers: {len(set(m['provider'] for m in models))}")
        print(f"   - Categories: {set(m['category'] for m in models)}")
        
        return models
    
    def _infer_category(self, provider: str, model_id: str) -> str:
        """Определяет категорию модели"""
        
        text = f"{provider} {model_id}".lower()
        
        if any(x in text for x in ['image', 'picture', 'photo', 'seedream', 'flux', '4o-image']):
            return 'image'
        elif any(x in text for x in ['video', 'veo', 'runway', 'kling', 'wan', 'luma', 'minimax']):
            return 'video'
        elif any(x in text for x in ['audio', 'music', 'suno', 'sound', 'speech', 'elevenlabs']):
            return 'audio'
        elif any(x in text for x in ['upscale', 'enhance']):
            return 'enhance'
        else:
            return 'other'
    
    def scrape_model_details(self, model_info: Dict) -> Optional[Dict]:
        """
        Парсит страницу конкретной модели и извлекает:
        - endpoint
        - input_schema (из Copy page / API примеров)
        - pricing (credits/gen, usd/gen)
        - примеры использования
        """
        
        model_id = model_info['model_id']
        slug = model_info['slug']
        
        print(f"\n📄 [{model_id}] Scraping docs page...")
        
        # URL страницы в docs
        url = f"https://docs.kie.ai/{slug}"
        cache_file = self.cache_dir / f"{slug.replace('/', '_')}.html"
        
        # Проверяем кэш
        if cache_file.exists():
            print(f"   📦 Using cache")
            html = cache_file.read_text(encoding='utf-8')
        else:
            try:
                print(f"   🌐 Fetching: {url}")
                resp = self.client.get(url)
                
                if resp.status_code == 404:
                    print(f"   ⚠️  404 Not Found")
                    return None
                
                html = resp.text
                cache_file.write_text(html, encoding='utf-8')
                time.sleep(0.5)  # Be polite
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
                return None
        
        # Парсим данные
        return self._extract_from_docs_page(html, model_info)
    
    def _extract_from_docs_page(self, html: str, model_info: Dict) -> Dict:
        """Извлекает все данные из страницы документации"""
        
        soup = BeautifulSoup(html, 'lxml')
        
        model_data = {
            "model_id": model_info['model_id'],
            "provider": model_info['provider'],
            "category": model_info['category'],
            "slug": model_info['slug'],
            "display_name": None,
            "description": None,
            "endpoint": None,
            "method": "POST",
            "input_schema": {},
            "pricing": {},
            "examples": [],
            "source_url": f"https://docs.kie.ai/{model_info['slug']}"
        }
        
        # 1. Display name (из h1)
        h1 = soup.find('h1')
        if h1:
            model_data['display_name'] = h1.get_text(strip=True)
        else:
            model_data['display_name'] = model_info['model_id']
        
        # 2. Description
        desc_tag = soup.find('p', class_=lambda x: x and ('description' in x.lower() or 'subtitle' in x.lower()) if x else False)
        if desc_tag:
            model_data['description'] = desc_tag.get_text(strip=True)
        else:
            # Первый параграф после заголовка
            first_p = soup.find('p')
            if first_p:
                model_data['description'] = first_p.get_text(strip=True)[:200]
        
        # 3. Endpoint (из code blocks или cURL examples)
        endpoints = self._extract_endpoints(soup)
        if endpoints:
            model_data['endpoint'] = endpoints[0]  # Берем первый
            print(f"   ✅ Endpoint: {model_data['endpoint']}")
        
        # 4. Input schema (из JSON примеров)
        schema, examples = self._extract_input_schema(soup)
        if schema:
            model_data['input_schema'] = schema
            model_data['examples'] = examples
            print(f"   ✅ Schema params: {list(schema.keys())}")
        
        # 5. Pricing (из текста страницы или таблиц)
        pricing = self._extract_pricing(soup, html)
        if pricing:
            model_data['pricing'] = pricing
            print(f"   💰 Pricing: {pricing}")
        
        return model_data
    
    def _extract_endpoints(self, soup: BeautifulSoup) -> List[str]:
        """Извлекает API endpoints из документации"""
        
        endpoints = []
        
        # Паттерн 1: в code blocks
        code_blocks = soup.find_all(['code', 'pre'])
        for block in code_blocks:
            text = block.get_text()
            
            # Ищем https://api.kie.ai/...
            matches = re.findall(r'https://api\.kie\.ai(/api/v\d+/[^\s"\'\)\]]+)', text)
            endpoints.extend(matches)
            
            # Ищем относительные пути /api/v1/...
            rel_matches = re.findall(r'(/api/v\d+/jobs/\w+)', text)
            endpoints.extend(rel_matches)
        
        # Дедупликация
        return list(dict.fromkeys(endpoints))
    
    def _extract_input_schema(self, soup: BeautifulSoup) -> tuple[Dict, List]:
        """Извлекает input schema из JSON примеров"""
        
        schema = {}
        examples = []
        
        code_blocks = soup.find_all(['code', 'pre'])
        
        for block in code_blocks:
            text = block.get_text()
            
            # Ищем JSON объекты
            try:
                # Паттерн: { ... "prompt": ... }
                json_match = re.search(r'\{[^\{\}]*(?:\{[^\{\}]*\}[^\{\}]*)*\}', text, re.DOTALL)
                if json_match:
                    json_obj = json.loads(json_match.group(0))
                    
                    # Это request payload?
                    if 'prompt' in json_obj or 'model' in json_obj or 'text' in json_obj:
                        examples.append(json_obj)
                        
                        # Строим schema
                        for key, value in json_obj.items():
                            if key not in schema:
                                schema[key] = {
                                    "type": type(value).__name__,
                                    "required": True,
                                    "examples": []
                                }
                            schema[key]['examples'].append(value)
            except:
                pass
        
        return schema, examples
    
    def _extract_pricing(self, soup: BeautifulSoup, html: str) -> Dict:
        """Извлекает pricing из страницы"""
        
        pricing = {}
        
        text = soup.get_text()
        
        # Паттерн 1: "X credits per generation"
        credits_match = re.search(r'(\d+(?:\.\d+)?)\s*credits?\s*(?:per|/)\s*(?:gen|generation)', text, re.IGNORECASE)
        if credits_match:
            pricing['credits_per_gen'] = float(credits_match.group(1))
        
        # Паттерн 2: "$X per generation" или "$X/gen"
        usd_match = re.search(r'\$(\d+(?:\.\d+)?)\s*(?:per|/)\s*(?:gen|generation)', text, re.IGNORECASE)
        if usd_match:
            pricing['usd_per_gen'] = float(usd_match.group(1))
        
        # Паттерн 3: просто "$X" рядом с "price" или "cost"
        price_match = re.search(r'(?:price|cost)[^\$]*\$(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        if price_match and 'usd_per_gen' not in pricing:
            pricing['usd_per_gen'] = float(price_match.group(1))
        
        return pricing
    
    def build_master_registry(self) -> Dict:
        """
        Главный метод: строит полный registry
        """
        
        print("\n" + "=" * 80)
        print("🎯 BUILDING MASTER SOURCE OF TRUTH REGISTRY")
        print("=" * 80)
        
        # Шаг 1: Получаем список моделей
        model_list = self.extract_docs_model_list()
        
        if not model_list:
            print("❌ No models found!")
            return {}
        
        # Шаг 2: Парсим каждую модель
        print(f"\n📦 STEP 2: Scraping {len(model_list)} models")
        print("=" * 80)
        
        for idx, model_info in enumerate(model_list, 1):
            model_id = model_info['model_id']
            print(f"\n[{idx}/{len(model_list)}] Processing: {model_id}")
            
            model_data = self.scrape_model_details(model_info)
            
            if model_data:
                # Валидация
                if not model_data.get('endpoint'):
                    print(f"   ⚠️  No endpoint found - adding to pending")
                    self.pending_models.append({
                        "model_id": model_id,
                        "reason": "No endpoint found",
                        **model_info
                    })
                else:
                    # Добавляем в registry
                    self.models_registry[model_id] = model_data
                    print(f"   ✅ Added to registry")
            else:
                self.pending_models.append({
                    "model_id": model_id,
                    "reason": "Failed to scrape",
                    **model_info
                })
        
        # Шаг 3: Сохраняем
        return self._save_registry()
    
    def _save_registry(self) -> Dict:
        """Сохраняет registry в JSON"""
        
        registry = {
            "version": "1.0.0-MASTER-SOURCE-OF-TRUTH",
            "scraped_at": datetime.now().isoformat(),
            "source": "docs.kie.ai + page scraping",
            "philosophy": """
ЕДИНСТВЕННЫЙ SOURCE OF TRUTH - docs.kie.ai + страницы моделей.
Спарсено ОДИН РАЗ с максимальной точностью.
Возвращаемся к парсингу ТОЛЬКО если модель не работает.
            """,
            "total_models": len(self.models_registry),
            "pending_models": len(self.pending_models),
            "models": self.models_registry,
            "pending": self.pending_models
        }
        
        # Сохраняем
        output_file = Path("models/KIE_SOURCE_OF_TRUTH.json")
        output_file.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding='utf-8')
        
        print("\n" + "=" * 80)
        print("✅ MASTER REGISTRY CREATED")
        print("=" * 80)
        print(f"📄 Saved to: {output_file}")
        print(f"✅ Total models: {len(self.models_registry)}")
        print(f"⏳ Pending models: {len(self.pending_models)}")
        
        if self.models_registry:
            print(f"\n📊 Registry stats:")
            categories = {}
            with_pricing = 0
            with_schema = 0
            
            for model_id, data in self.models_registry.items():
                cat = data.get('category', 'unknown')
                categories[cat] = categories.get(cat, 0) + 1
                if data.get('pricing'):
                    with_pricing += 1
                if data.get('input_schema'):
                    with_schema += 1
            
            print(f"   - Categories: {categories}")
            print(f"   - With pricing: {with_pricing}/{len(self.models_registry)}")
            print(f"   - With schema: {with_schema}/{len(self.models_registry)}")
        
        return registry


def main():
    """Главная функция"""
    
    scraper = MasterKieScraper()
    registry = scraper.build_master_registry()
    
    print("\n" + "=" * 80)
    print("🎉 DONE! Source of Truth created.")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Review models/KIE_SOURCE_OF_TRUTH.json")
    print("2. Add manual pricing for pending models if needed")
    print("3. Integrate registry into bot")
    

if __name__ == "__main__":
    main()
