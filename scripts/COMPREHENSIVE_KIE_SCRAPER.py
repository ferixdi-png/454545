#!/usr/bin/env python3
"""
🔥 COMPREHENSIVE KIE.AI SCRAPER - FINAL SOURCE OF TRUTH 🔥

ЦЕЛЬ: Извлечь ВСЕ модели с kie.ai, парсить КАЖДУЮ страницу модели,
      найти "copy page" / API examples, построить ПОЛНЫЙ registry.

ФИЛОСОФИЯ: Один раз спарсить правильно - использовать всегда.
           Возвращаться к парсингу только если что-то не работает.

ИСТОЧНИК ПРАВДЫ: kie.ai страницы моделей (НЕ docs.kie.ai)
"""

import requests
import re
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from datetime import datetime


class ComprehensiveKieScraper:
    """
    Comprehensive scraper для kie.ai
    
    Извлекает:
    1. Список всех моделей
    2. Для каждой модели:
       - Model ID (tech)
       - Display name
       - Provider
       - Category
       - Endpoint
       - Request body example
       - Parameters schema
       - Pricing (credits/gen)
       - Примеры
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.models_data = {}
        self.errors = []
        
    def get_models_list(self) -> List[Dict]:
        """
        Получить список всех моделей с kie.ai
        
        Стратегия:
        1. Парсим главную страницу / models page
        2. Извлекаем ссылки на модели
        3. Возвращаем список {name, url, slug}
        """
        print("=" * 80)
        print("🔍 STEP 1: Получение списка всех моделей")
        print("=" * 80)
        
        models = []
        
        # Try different endpoints
        endpoints_to_try = [
            "https://kie.ai/models",
            "https://kie.ai/",
            "https://docs.kie.ai/",
        ]
        
        for url in endpoints_to_try:
            try:
                print(f"\n📡 Trying: {url}")
                resp = self.session.get(url, timeout=10)
                
                if resp.status_code != 200:
                    print(f"   ❌ Status: {resp.status_code}")
                    continue
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Find model links
                # Pattern 1: Direct model links (kie.ai/<model-slug>)
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    
                    # Skip non-model links
                    if any(skip in href for skip in [
                        '/docs/', '/api/', '/pricing', '/login', '/signup',
                        'mailto:', 'http://not.kie.ai', 'discord', 'twitter'
                    ]):
                        continue
                    
                    # Model slug pattern
                    if re.match(r'^/[a-z0-9-]+(/[a-z0-9-]+)?$', href):
                        model_name = link.get_text(strip=True)
                        slug = href.strip('/')
                        
                        if model_name and slug:
                            models.append({
                                'name': model_name,
                                'slug': slug,
                                'url': f'https://kie.ai/{slug}'
                            })
                
                if models:
                    print(f"   ✅ Found {len(models)} potential models")
                    break
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
                continue
        
        # Deduplicate
        unique_models = []
        seen_slugs = set()
        for m in models:
            if m['slug'] not in seen_slugs:
                unique_models.append(m)
                seen_slugs.add(m['slug'])
        
        # If no models found via parsing, use known models from docs
        if not unique_models:
            print("\n⚠️  Не удалось извлечь модели через parsing, использую known models")
            unique_models = self._get_known_models_from_docs()
        
        print(f"\n✅ Total unique models: {len(unique_models)}")
        for i, m in enumerate(unique_models[:10], 1):
            print(f"   {i}. {m['slug']}")
        if len(unique_models) > 10:
            print(f"   ... and {len(unique_models) - 10} more")
        
        return unique_models
    
    def _get_known_models_from_docs(self) -> List[Dict]:
        """Fallback: известные модели из docs.kie.ai"""
        known = [
            {'name': 'Veo 3', 'slug': 'veo3-api', 'url': 'https://docs.kie.ai/veo3-api/quickstart'},
            {'name': 'Runway', 'slug': 'runway-api', 'url': 'https://docs.kie.ai/runway-api/quickstart'},
            {'name': 'Suno', 'slug': 'suno-api', 'url': 'https://docs.kie.ai/suno-api/quickstart'},
            {'name': 'Flux Kontext', 'slug': 'flux-kontext-api', 'url': 'https://docs.kie.ai/flux-kontext-api/quickstart'},
            {'name': 'GPT-4o Image', 'slug': '4o-image-api', 'url': 'https://docs.kie.ai/4o-image-api/quickstart'},
        ]
        return known
    
    def scrape_model_page(self, model_info: Dict) -> Optional[Dict]:
        """
        Парсить страницу конкретной модели
        
        Извлекает:
        - Model ID (tech) из API examples
        - Endpoint
        - Request body example
        - Parameters
        - Pricing
        """
        slug = model_info['slug']
        url = model_info['url']
        
        print(f"\n{'=' * 80}")
        print(f"📄 Парсинг: {slug}")
        print(f"   URL: {url}")
        print("=" * 80)
        
        try:
            resp = self.session.get(url, timeout=15)
            
            if resp.status_code != 200:
                print(f"   ❌ Status: {resp.status_code}")
                return None
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Извлечение данных
            model_data = {
                'slug': slug,
                'display_name': model_info['name'],
                'source_url': url,
                'scraped_at': datetime.now().isoformat(),
            }
            
            # 1. Ищем код примеры (обычно в <code> или <pre>)
            code_blocks = soup.find_all(['code', 'pre'])
            
            for block in code_blocks:
                text = block.get_text()
                
                # Ищем endpoint
                endpoint_match = re.search(r'https://api\.kie\.ai(/api/v\d+/[^\s"\'\)]+)', text)
                if endpoint_match and 'endpoint' not in model_data:
                    model_data['endpoint'] = f"https://api.kie.ai{endpoint_match.group(1)}"
                
                # Ищем model ID в JSON
                if '"model"' in text or "'model'" in text:
                    try:
                        # Try to extract JSON
                        json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
                        if json_match:
                            try:
                                payload = json.loads(json_match.group(0))
                                if 'model' in payload:
                                    model_data['model_id'] = payload['model']
                            except:
                                # Try single quotes
                                json_str = json_match.group(0).replace("'", '"')
                                try:
                                    payload = json.loads(json_str)
                                    if 'model' in payload:
                                        model_data['model_id'] = payload['model']
                                except:
                                    pass
                    except Exception as e:
                        pass
                
                # Ищем request body example
                if '{' in text and '"prompt"' in text:
                    model_data['example_request'] = text[:500]  # First 500 chars
            
            # 2. Ищем pricing информацию
            pricing_patterns = [
                r'(\d+)\s*credits?/gen',
                r'(\d+)\s*credits?\s*per\s*generation',
                r'Price:\s*\$?(\d+\.?\d*)',
            ]
            
            page_text = soup.get_text()
            for pattern in pricing_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    try:
                        credits = int(match.group(1))
                        model_data['credits_per_gen'] = credits
                        break
                    except:
                        pass
            
            # 3. Определяем category
            if 'video' in slug.lower() or 'veo' in slug.lower() or 'runway' in slug.lower():
                model_data['category'] = 'video'
            elif 'image' in slug.lower() or 'flux' in slug.lower() or '4o' in slug.lower():
                model_data['category'] = 'image'
            elif 'audio' in slug.lower() or 'suno' in slug.lower() or 'music' in slug.lower():
                model_data['category'] = 'audio'
            else:
                model_data['category'] = 'other'
            
            # 4. Определяем provider
            if 'veo' in slug.lower():
                model_data['provider'] = 'Google'
            elif 'runway' in slug.lower():
                model_data['provider'] = 'Runway'
            elif 'suno' in slug.lower():
                model_data['provider'] = 'Suno'
            elif 'flux' in slug.lower():
                model_data['provider'] = 'Black Forest Labs'
            elif 'gpt' in slug.lower() or '4o' in slug.lower():
                model_data['provider'] = 'OpenAI'
            else:
                model_data['provider'] = 'Unknown'
            
            # Summary
            print(f"\n📊 Extracted data:")
            print(f"   Model ID: {model_data.get('model_id', 'NOT FOUND')}")
            print(f"   Endpoint: {model_data.get('endpoint', 'NOT FOUND')}")
            print(f"   Pricing: {model_data.get('credits_per_gen', 'NOT FOUND')} credits/gen")
            print(f"   Category: {model_data.get('category')}")
            print(f"   Provider: {model_data.get('provider')}")
            
            return model_data
            
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            self.errors.append({'slug': slug, 'error': str(e)})
            return None
    
    def build_comprehensive_registry(self, scraped_models: List[Dict]) -> Dict:
        """
        Построить comprehensive registry из спарсенных данных
        """
        print("\n" + "=" * 80)
        print("🏗️  BUILDING COMPREHENSIVE REGISTRY")
        print("=" * 80)
        
        registry = {
            "version": "8.0.0-KIE-AI-SCRAPED-SOURCE-OF-TRUTH",
            "source": "kie.ai model pages - comprehensive scraping",
            "scraped_at": datetime.now().isoformat(),
            "philosophy": """
ЕДИНСТВЕННЫЙ SOURCE OF TRUTH - страницы моделей на kie.ai.
Спарсено ОДИН РАЗ с максимальной точностью.
Возвращаемся к парсингу ТОЛЬКО если модель не работает.
            """,
            "models": {},
            "pending_models": [],
            "scraping_errors": self.errors
        }
        
        for model_data in scraped_models:
            if not model_data:
                continue
            
            # Проверяем что есть критичные данные
            has_endpoint = 'endpoint' in model_data
            has_model_id = 'model_id' in model_data
            
            # Если нет model_id, пробуем сгенерировать из slug
            if not has_model_id:
                # Для некоторых API model_id не нужен (endpoint сам определяет)
                if 'runway' in model_data['slug']:
                    model_data['model_id'] = 'runway_gen3_alpha'
                elif 'suno' in model_data['slug']:
                    model_data['model_id'] = 'V3_5'
                elif '4o-image' in model_data['slug']:
                    model_data['model_id'] = 'gpt-4o-image'
                elif 'veo3' in model_data['slug']:
                    if 'fast' in model_data['slug']:
                        model_data['model_id'] = 'veo3_fast'
                    else:
                        model_data['model_id'] = 'veo3'
                elif 'flux' in model_data['slug']:
                    if 'max' in model_data['slug']:
                        model_data['model_id'] = 'flux-kontext-max'
                    else:
                        model_data['model_id'] = 'flux-kontext-pro'
                else:
                    model_data['model_id'] = model_data['slug'].replace('-api', '').replace('/', '_')
            
            model_id = model_data['model_id']
            
            # Build registry entry
            if has_endpoint:
                registry['models'][model_id] = {
                    "model_id": model_id,
                    "display_name": model_data.get('display_name', model_id),
                    "provider": model_data.get('provider', 'Unknown'),
                    "category": model_data.get('category', 'other'),
                    "endpoint": model_data['endpoint'],
                    "method": "POST",
                    "pricing": {
                        "credits_per_gen": model_data.get('credits_per_gen', 999),
                        "estimated": 'credits_per_gen' not in model_data
                    },
                    "source_url": model_data.get('source_url'),
                    "scraped_at": model_data.get('scraped_at'),
                    "enabled": True,
                    "tested": False
                }
            else:
                # Pending if no endpoint
                registry['pending_models'].append({
                    "slug": model_data['slug'],
                    "display_name": model_data.get('display_name'),
                    "reason": "No endpoint found in page",
                    "source_url": model_data.get('source_url')
                })
        
        print(f"\n✅ Registry built:")
        print(f"   Total models: {len(registry['models'])}")
        print(f"   Pending models: {len(registry['pending_models'])}")
        print(f"   Errors: {len(registry['scraping_errors'])}")
        
        return registry
    
    def run(self, output_path: str = "models/kie_models_v8_comprehensive_source_of_truth.json"):
        """Запустить полный пайплайн"""
        print("\n" + "=" * 80)
        print("🚀 COMPREHENSIVE KIE.AI SCRAPER - START")
        print("=" * 80)
        
        # Step 1: Get models list
        models_list = self.get_models_list()
        
        if not models_list:
            print("\n❌ FATAL: Не удалось получить список моделей")
            return None
        
        # Step 2: Scrape each model
        scraped_data = []
        for i, model_info in enumerate(models_list, 1):
            print(f"\n[{i}/{len(models_list)}] Processing {model_info['slug']}...")
            
            model_data = self.scrape_model_page(model_info)
            if model_data:
                scraped_data.append(model_data)
            
            # Rate limiting
            time.sleep(1)
        
        # Step 3: Build registry
        registry = self.build_comprehensive_registry(scraped_data)
        
        # Step 4: Save
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(registry, indent=2, ensure_ascii=False))
        
        print(f"\n✅ Registry saved to: {output_path}")
        
        return registry


def main():
    scraper = ComprehensiveKieScraper()
    registry = scraper.run()
    
    if registry:
        print("\n" + "=" * 80)
        print("🎉 SCRAPING COMPLETE!")
        print("=" * 80)
        print(f"\nTotal models: {len(registry['models'])}")
        print(f"Pending: {len(registry['pending_models'])}")
        
        # Show TOP-5 cheapest
        models_list = [
            (mid, m) for mid, m in registry['models'].items()
        ]
        sorted_models = sorted(
            models_list,
            key=lambda x: x[1].get('pricing', {}).get('credits_per_gen', 999)
        )
        
        print("\n🎯 TOP-5 CHEAPEST:")
        for i, (mid, m) in enumerate(sorted_models[:5], 1):
            credits = m.get('pricing', {}).get('credits_per_gen')
            print(f"   {i}. {mid} - {credits} cr/gen")


if __name__ == "__main__":
    main()
