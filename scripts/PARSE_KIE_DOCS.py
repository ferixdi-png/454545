#!/usr/bin/env python3
"""
🎯 KIE.AI DOCS PARSER - SINGLE SOURCE OF TRUTH

Парсит документацию Kie.ai чтобы извлечь:
1. Специализированные API endpoints для каждой категории
2. Model IDs и их параметры
3. Примеры request/response
4. Pricing информацию

ФИЛОСОФИЯ:
- Kie.ai docs - единственный источник истины
- Парсим ОДИН РАЗ, фиксируем результат
- Возвращаемся к парсингу только если что-то не работает
"""
import httpx
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
from datetime import datetime

DOCS_BASE = "https://docs.kie.ai"
CACHE_DIR = Path("cache/kie_docs")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class KieDocsParser:
    """Parser для Kie.ai документации"""
    
    def __init__(self):
        self.api_categories = {}
        self.models = []
        self.endpoints = {}
        
    def fetch_page(self, path: str) -> Optional[str]:
        """Fetch и cache страницы документации"""
        cache_file = CACHE_DIR / f"{path.replace('/', '_')}.html"
        
        # Проверяем cache
        if cache_file.exists():
            print(f"📦 Cache hit: {path}")
            return cache_file.read_text(encoding='utf-8')
        
        # Загружаем
        url = f"{DOCS_BASE}{path}" if path.startswith('/') else f"{DOCS_BASE}/{path}"
        print(f"🌐 Fetching: {url}")
        
        try:
            response = httpx.get(url, timeout=30.0, follow_redirects=True)
            if response.status_code == 200:
                cache_file.write_text(response.text, encoding='utf-8')
                return response.text
            else:
                print(f"❌ HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def parse_homepage(self):
        """Парсим главную страницу чтобы найти категории API"""
        html = self.fetch_page('/')
        if not html:
            return
        
        soup = BeautifulSoup(html, 'lxml')
        
        # Ищем категории
        categories = {
            "video": [],
            "audio": [],
            "image": [],
            "utility": []
        }
        
        # Извлекаем ссылки на API
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True)
            
            # Video APIs
            if 'veo' in href.lower() or 'runway' in href.lower() or 'video' in text.lower():
                categories['video'].append({'text': text, 'href': href})
            # Audio APIs
            elif 'suno' in href.lower() or 'audio' in text.lower() or 'music' in text.lower():
                categories['audio'].append({'text': text, 'href': href})
            # Image APIs
            elif 'flux' in href.lower() or '4o-image' in href.lower() or 'image' in text.lower():
                categories['image'].append({'text': text, 'href': href})
            # Utility
            elif 'file-upload' in href.lower() or 'common' in href.lower():
                categories['utility'].append({'text': text, 'href': href})
        
        self.api_categories = categories
        
        print("\n📂 Найденные категории API:")
        for cat, links in categories.items():
            print(f"\n{cat.upper()} ({len(links)} APIs):")
            for item in links[:5]:
                print(f"  - {item['text']}: {item['href']}")
    
    def parse_api_page(self, path: str) -> Dict[str, Any]:
        """Парсим страницу конкретного API"""
        html = self.fetch_page(path)
        if not html:
            return {}
        
        soup = BeautifulSoup(html, 'lxml')
        
        api_info = {
            "path": path,
            "endpoints": [],
            "models": [],
            "examples": []
        }
        
        # Ищем code blocks с примерами
        code_blocks = soup.find_all(['pre', 'code'])
        for block in code_blocks:
            text = block.get_text()
            
            # Endpoint URLs
            endpoint_match = re.search(r'(https://api\.kie\.ai[^\s"\']+)', text)
            if endpoint_match:
                endpoint = endpoint_match.group(1)
                if endpoint not in api_info['endpoints']:
                    api_info['endpoints'].append(endpoint)
            
            # Model IDs в примерах
            model_match = re.search(r'"model"\s*:\s*"([^"]+)"', text)
            if model_match:
                model_id = model_match.group(1)
                if model_id not in api_info['models']:
                    api_info['models'].append(model_id)
            
            # JSON примеры
            if '{' in text and '"input"' in text:
                try:
                    json_match = re.search(r'\{.*\}', text, re.DOTALL)
                    if json_match:
                        example = json.loads(json_match.group(0))
                        api_info['examples'].append(example)
                except:
                    pass
        
        return api_info
    
    def parse_all_categories(self):
        """Парсим все категории API"""
        results = {}
        
        for category, links in self.api_categories.items():
            print(f"\n🔍 Parsing {category.upper()} APIs...")
            results[category] = []
            
            for item in links[:3]:  # Первые 3 из каждой категории
                href = item['href']
                if not href.startswith('http'):
                    href = href if href.startswith('/') else f'/{href}'
                
                api_info = self.parse_api_page(href)
                if api_info and api_info.get('endpoints'):
                    results[category].append({
                        'name': item['text'],
                        'href': href,
                        **api_info
                    })
        
        return results
    
    def save_results(self, results: Dict[str, Any]):
        """Сохраняем результаты парсинга"""
        output = {
            "version": "PARSED_FROM_DOCS_1.0",
            "source": "docs.kie.ai",
            "parsed_at": datetime.now().isoformat(),
            "api_structure": results,
            "summary": {
                "total_categories": len(results),
                "total_apis": sum(len(apis) for apis in results.values()),
                "total_endpoints": sum(
                    len(api.get('endpoints', [])) 
                    for apis in results.values() 
                    for api in apis
                ),
                "total_models": sum(
                    len(api.get('models', [])) 
                    for apis in results.values() 
                    for api in apis
                )
            }
        }
        
        output_file = Path("models/kie_api_structure.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Saved: {output_file}")
        print(f"📊 Summary:")
        for key, value in output['summary'].items():
            print(f"   {key}: {value}")


def main():
    """Main entry point"""
    print("="*80)
    print("🎯 KIE.AI DOCS PARSER - STARTING")
    print("="*80)
    
    parser = KieDocsParser()
    
    # Step 1: Parse homepage
    print("\n📖 Step 1: Parsing homepage...")
    parser.parse_homepage()
    
    # Step 2: Parse all API categories
    print("\n📖 Step 2: Parsing API categories...")
    results = parser.parse_all_categories()
    
    # Step 3: Save results
    print("\n📖 Step 3: Saving results...")
    parser.save_results(results)
    
    print("\n✅ DONE!")


if __name__ == "__main__":
    main()
