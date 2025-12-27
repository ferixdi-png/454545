#!/usr/bin/env python3
"""
🔥 ULTIMATE KIE.AI MODEL SCRAPER

ПАРСИТ КАЖДУЮ МОДЕЛЬ с kie.ai/<model-slug>
Извлекает РЕАЛЬНЫЕ данные из Copy page / API examples

ЭТО ЕДИНСТВЕННЫЙ SOURCE OF TRUTH!
"""

import requests
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import time

class KieAiModelScraper:
    """Scraper для извлечения ВСЕХ моделей с kie.ai"""
    
    BASE_URL = "https://kie.ai"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.models = {}
        self.cache_dir = Path("cache/kie_models")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def scrape_homepage_models(self) -> List[str]:
        """Извлечь список всех моделей с главной страницы"""
        print("🔍 Scraping kie.ai homepage for model list...")
        
        try:
            resp = self.session.get(f"{self.BASE_URL}/", timeout=15)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Ищем все ссылки на модели
            model_links = set()
            
            # Pattern 1: Прямые ссылки на модели (обычно в навигации)
            for link in soup.find_all('a', href=True):
                href = link['href']
                # Исключаем системные пути
                if href.startswith('/') and href not in ['/', '/pricing', '/docs', '/api', '/login', '/signup']:
                    # Очищаем от параметров
                    clean_href = href.split('?')[0].split('#')[0]
                    if clean_href != '/' and len(clean_href) > 1:
                        model_links.add(clean_href.strip('/'))
            
            print(f"✅ Found {len(model_links)} potential model pages")
            return list(model_links)
            
        except Exception as e:
            print(f"❌ Error scraping homepage: {e}")
            return []
    
    def scrape_model_page(self, model_slug: str) -> Optional[Dict]:
        """Парсит страницу конкретной модели"""
        url = f"{self.BASE_URL}/{model_slug}"
        cache_file = self.cache_dir / f"{model_slug.replace('/', '_')}.html"
        
        print(f"\n📄 Scraping: {url}")
        
        # Check cache
        if cache_file.exists():
            print(f"   📂 Using cached version")
            html = cache_file.read_text(encoding='utf-8')
        else:
            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code == 404:
                    print(f"   ⚠️  404 Not Found - skipping")
                    return None
                    
                resp.raise_for_status()
                html = resp.text
                cache_file.write_text(html, encoding='utf-8')
                time.sleep(1)  # Be polite
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
                return None
        
        return self.extract_model_data(html, model_slug)
    
    def extract_model_data(self, html: str, slug: str) -> Optional[Dict]:
        """Извлекает данные модели из HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        
        model_data = {
            "model_id": slug,
            "slug": slug,
            "display_name": None,
            "provider": None,
            "category": None,
            "endpoint": None,
            "method": "POST",
            "parameters": {},
            "pricing": {},
            "examples": [],
            "description": None
        }
        
        # Extract title (display name)
        title = soup.find('h1')
        if title:
            model_data["display_name"] = title.get_text(strip=True)
        
        # Extract description
        desc = soup.find('p', class_=lambda x: x and 'description' in x.lower() if x else False)
        if not desc:
            desc = soup.find('meta', {'name': 'description'})
            if desc:
                model_data["description"] = desc.get('content', '').strip()
        else:
            model_data["description"] = desc.get_text(strip=True)
        
        # КРИТИЧНО: Ищем API примеры / Copy page
        api_examples = self.extract_api_examples(soup)
        if api_examples:
            print(f"   ✅ Found {len(api_examples)} API examples")
            model_data["examples"] = api_examples
            
            # Извлекаем endpoint и parameters из первого примера
            if api_examples:
                first_example = api_examples[0]
                if 'endpoint' in first_example:
                    model_data["endpoint"] = first_example['endpoint']
                if 'payload' in first_example:
                    model_data["parameters"] = self.infer_parameters(first_example['payload'])
        
        # Extract pricing
        pricing = self.extract_pricing(soup, html)
        if pricing:
            model_data["pricing"] = pricing
            print(f"   💰 Pricing: {pricing}")
        
        # Determine category from content
        category = self.infer_category(html, model_data["display_name"] or "")
        if category:
            model_data["category"] = category
        
        return model_data
    
    def extract_api_examples(self, soup: BeautifulSoup) -> List[Dict]:
        """Извлекает API примеры из code blocks"""
        examples = []
        
        # Ищем все code blocks
        code_blocks = soup.find_all(['code', 'pre'])
        
        for block in code_blocks:
            code_text = block.get_text()
            
            # Pattern 1: JSON payload в блоке
            json_match = re.search(r'\{[^}]*"prompt"[^}]*\}', code_text, re.DOTALL)
            if json_match:
                try:
                    payload = json.loads(json_match.group(0))
                    examples.append({
                        "type": "json_payload",
                        "payload": payload
                    })
                except:
                    pass
            
            # Pattern 2: URL endpoint
            endpoint_match = re.search(r'https://api\.kie\.ai(/api/v\d+/[^\s"\']+)', code_text)
            if endpoint_match:
                examples.append({
                    "type": "endpoint",
                    "endpoint": endpoint_match.group(1)
                })
            
            # Pattern 3: curl command
            if 'curl' in code_text.lower():
                curl_endpoint = re.search(r'https://api\.kie\.ai(/api/v\d+/[^\s"\']+)', code_text)
                curl_payload = re.search(r'-d\s+["\']([^"\']+)["\']', code_text)
                
                if curl_endpoint:
                    ex = {"type": "curl", "endpoint": curl_endpoint.group(1)}
                    if curl_payload:
                        try:
                            ex["payload"] = json.loads(curl_payload.group(1))
                        except:
                            pass
                    examples.append(ex)
        
        return examples
    
    def extract_pricing(self, soup: BeautifulSoup, html: str) -> Dict:
        """Извлекает pricing из страницы"""
        pricing = {}
        
        # Pattern 1: Ищем упоминания credits
        credits_match = re.search(r'(\d+)\s*credits?(?:\s*per\s*generation|\s*/\s*gen)?', html, re.IGNORECASE)
        if credits_match:
            pricing["credits_per_gen"] = int(credits_match.group(1))
        
        # Pattern 2: Ищем USD цены
        usd_match = re.search(r'\$\s*(\d+\.?\d*)', html)
        if usd_match:
            pricing["usd_per_gen"] = float(usd_match.group(1))
        
        # Pattern 3: Таблица с ценами
        tables = soup.find_all('table')
        for table in tables:
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                row_text = ' '.join([c.get_text() for c in cells])
                
                if 'credit' in row_text.lower():
                    numbers = re.findall(r'\d+', row_text)
                    if numbers:
                        pricing.setdefault("credits_per_gen", int(numbers[0]))
        
        return pricing
    
    def infer_parameters(self, payload: Dict) -> Dict:
        """Выводит schema параметров из примера payload"""
        parameters = {}
        
        for key, value in payload.items():
            param = {
                "type": type(value).__name__,
                "required": True,  # Assume required if in example
            }
            
            if isinstance(value, (int, float)):
                param["default"] = value
            elif isinstance(value, str):
                param["default"] = value
            elif isinstance(value, bool):
                param["default"] = value
            
            parameters[key] = param
        
        return parameters
    
    def infer_category(self, html: str, title: str) -> Optional[str]:
        """Определяет категорию модели"""
        text = (html + " " + title).lower()
        
        if any(word in text for word in ['video', 'veo', 'runway', 'clip']):
            return 'video'
        elif any(word in text for word in ['image', 'flux', 'stable diffusion', 'dalle', 'midjourney']):
            return 'image'
        elif any(word in text for word in ['audio', 'music', 'suno', 'sound', 'voice']):
            return 'audio'
        elif any(word in text for word in ['text', 'gpt', 'chat', 'llm']):
            return 'text'
        
        return 'other'
    
    def scrape_all(self) -> Dict:
        """Главная функция: парсит ВСЕ модели"""
        print("=" * 70)
        print("🚀 ULTIMATE KIE.AI MODEL SCRAPER")
        print("=" * 70)
        
        # Step 1: Get model list from homepage
        model_slugs = self.scrape_homepage_models()
        
        if not model_slugs:
            print("\n⚠️  No models found on homepage, using known models...")
            # Fallback to known model slugs from docs.kie.ai
            model_slugs = [
                'veo-3', 'veo-3-fast', 'runway-gen3', 
                'suno-v3-5', 'flux-pro', 'gpt-4o-vision',
                'stable-video', 'minimax-video', 'kling-video',
                'luma-ray', 'haiper-video', 'viggle',
                'opus-clip', 'remove-bg', 'face-swap'
            ]
        
        # Step 2: Scrape each model
        results = {}
        valid_count = 0
        
        for slug in model_slugs:
            model_data = self.scrape_model_page(slug)
            
            if model_data and (model_data.get("examples") or model_data.get("endpoint")):
                results[slug] = model_data
                valid_count += 1
                print(f"   ✅ VALID - has API data")
            elif model_data:
                results[slug] = model_data
                print(f"   ⚠️  PARTIAL - missing API examples")
            
        print("\n" + "=" * 70)
        print(f"📊 SCRAPING COMPLETE")
        print(f"   Total scraped: {len(results)}")
        print(f"   With API data: {valid_count}")
        print("=" * 70)
        
        return results


def main():
    scraper = KieAiModelScraper()
    models = scraper.scrape_all()
    
    # Save results
    output_file = Path("models/kie_scraped_models_raw.json")
    output_file.write_text(json.dumps(models, indent=2, ensure_ascii=False))
    
    print(f"\n💾 Saved to: {output_file}")
    print(f"\n🎯 Next: Run BUILD_REGISTRY_FROM_SCRAPED.py to create final registry")


if __name__ == "__main__":
    main()
