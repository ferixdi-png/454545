#!/usr/bin/env python3
"""
🏗️ МАСТЕР-ПАРСЕР Kie.ai Copy Page

ЕДИНСТВЕННЫЙ ИСТОЧНИК ИСТИНЫ для каждой модели.
Парсит ОДИН РАЗ и сохраняет навсегда.

Извлекает:
- endpoint (реальный API path)
- input_schema (параметры из Copy page)
- examples (примеры использования)
- pricing (credits/gen из страницы)

Автор: AUTOPILOT
Дата: 2025-12-24
"""

import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup


class KieMasterParser:
    """Мастер-парсер для всех моделей Kie.ai"""
    
    BASE_URL = "https://docs.kie.ai"
    CACHE_DIR = Path("cache/kie_model_pages")
    OUTPUT_FILE = Path("models/KIE_PARSED_SOURCE_OF_TRUTH.json")
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Load existing registry
        registry_path = Path("models/KIE_SOURCE_OF_TRUTH.json")
        with open(registry_path) as f:
            self.registry = json.load(f)
        
        # Load existing pricing (fallback)
        pricing_path = Path("artifacts/pricing_corrected_final.json")
        if pricing_path.exists():
            with open(pricing_path) as f:
                self.existing_pricing = json.load(f)
        else:
            self.existing_pricing = {}
    
    def get_model_doc_url(self, model_id: str) -> Optional[str]:
        """Построить URL документации для модели"""
        
        # Маппинг model_id -> doc path
        # Примеры из структуры kie.ai/docs:
        # - qwen/z-image -> /market/z-image/z-image
        # - google/imagen4-fast -> /market/google/imagen4-fast
        # - sora-2-text-to-video -> /market/sora2/sora-2-text-to-video
        
        # Special single-name models
        if model_id == 'z-image':
            return f"{self.BASE_URL}/market/z-image/z-image"
        elif model_id == 'nano-banana-pro':
            return f"{self.BASE_URL}/market/google/nano-banana"
        
        if '/' in model_id:
            vendor, name = model_id.split('/', 1)
            
            # Special cases
            if vendor == 'qwen':
                return f"{self.BASE_URL}/market/z-image/{name}"
            
            elif vendor == 'google':
                return f"{self.BASE_URL}/market/google/{name}"
            
            elif vendor == 'flux-2':
                return f"{self.BASE_URL}/market/flux2/{name}"
            
            elif vendor == 'bytedance':
                if 'seedream' in name:
                    return f"{self.BASE_URL}/market/seedream/{name}"
                else:
                    return f"{self.BASE_URL}/market/bytedance/{name}"
            
            elif vendor == 'elevenlabs':
                return f"{self.BASE_URL}/market/elevenlabs/{name}"
            
            elif vendor == 'recraft':
                return f"{self.BASE_URL}/market/recraft/{name}"
            
            elif vendor == 'wan':
                return f"{self.BASE_URL}/market/wan/{name}"
            
            elif vendor == 'hailuo':
                return f"{self.BASE_URL}/market/hailuo/{name}"
            
            elif vendor == 'topaz':
                return f"{self.BASE_URL}/market/topaz/{name}"
            
            elif vendor == 'infinitalk':
                return f"{self.BASE_URL}/market/infinitalk/{name}"
            
            else:
                return f"{self.BASE_URL}/market/{vendor}/{name}"
        
        else:
            # Модели без vendor (sora-*, veo3_fast, V4)
            if model_id.startswith('sora-2'):
                return f"{self.BASE_URL}/market/sora2/{model_id}"
            elif model_id.startswith('sora-'):
                return f"{self.BASE_URL}/market/sora2/{model_id}"
            elif model_id.startswith('veo'):
                # veo3_fast, veo3.1
                return f"{self.BASE_URL}/veo3-api/quickstart"
            elif model_id == 'V4':
                # Seedream V4
                return f"{self.BASE_URL}/market/seedream/seedream"
            else:
                return None
    
    def fetch_page(self, url: str) -> Optional[str]:
        """Загрузить страницу (с кэшированием)"""
        
        # Cache key from URL
        cache_key = url.replace('https://', '').replace('/', '_') + '.html'
        cache_file = self.CACHE_DIR / cache_key
        
        # Check cache
        if cache_file.exists():
            print(f"   📦 Cache hit: {cache_key}")
            return cache_file.read_text(encoding='utf-8')
        
        # Fetch
        print(f"   🌐 Fetching: {url}")
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            
            html = resp.text
            
            # Save to cache
            cache_file.write_text(html, encoding='utf-8')
            
            time.sleep(1)  # Be nice
            return html
            
        except Exception as e:
            print(f"   ❌ Error fetching {url}: {e}")
            return None
    
    def extract_from_copy_page(self, html: str, model_id: str) -> Dict[str, Any]:
        """Извлечь данные из Copy page (JSON в скрипте)"""
        
        result = {
            'endpoint': None,
            'input_schema': {},
            'examples': [],
            'pricing': {},
            '_metadata': {
                'source': 'copy_page',
                'parsed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'parser_version': '2.1.0'
            }
        }
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. Поиск endpoint в JSON data (приоритет #1)
        # Ищем в структуре: {"openapi":"path/to/model.json post /api/v1/jobs/createTask"}
        openapi_pattern = r'"openapi":\s*"[^"]*?(?:post|POST|get|GET)\s+(/api/v[0-9]+/[a-zA-Z]+(?:/[a-zA-Z]+)*)'
        openapi_match = re.search(openapi_pattern, html, re.I)
        if openapi_match:
            endpoint_raw = openapi_match.group(1)
            # Debug
            if model_id == 'z-image':
                print(f"   DEBUG: Raw match: {repr(endpoint_raw)}")
            result['endpoint'] = endpoint_raw
            result['_metadata']['endpoint_source'] = 'openapi_json'
        
        # 2. Поиск в <script> тегах (Next.js данные)
        for script in soup.find_all('script'):
            if script.string and 'props' in script.string:
                # Try to extract JSON
                try:
                    # Look for endpoint patterns
                    if '/api/v1/' in script.string:
                        # Extract endpoint
                        endpoint_match = re.search(r'(/api/v1/[^"\']+)', script.string)
                        if endpoint_match:
                            result['endpoint'] = endpoint_match.group(1)
                    
                    # Look for pricing
                    credit_match = re.search(r'(\d+\.?\d*)\s*credits?\s*per', script.string, re.I)
                    if credit_match:
                        credits = float(credit_match.group(1))
                        result['pricing']['credits_per_gen'] = credits
                        result['pricing']['usd_per_gen'] = credits * 0.005  # 1 credit = $0.005
                    
                except:
                    pass
        
        # 2. Поиск в тексте страницы
        text = soup.get_text()
        
        # Pricing patterns
        for pattern in [
            r'(\d+\.?\d*)\s*credits?\s*per\s*(?:generation|call|video|image)',
            r'\$(\d+\.?\d*)\s*per\s*(?:generation|call|video|image)',
            r'(\d+\.?\d*)\s*kie\s*credits?'
        ]:
            match = re.search(pattern, text, re.I)
            if match:
                value = float(match.group(1))
                if '$' in pattern:
                    result['pricing']['usd_per_gen'] = value
                else:
                    result['pricing']['credits_per_gen'] = value
                    result['pricing']['usd_per_gen'] = value * 0.005
                break
        
        # 3. Extract code examples
        code_blocks = soup.find_all('code')
        for block in code_blocks:
            code = block.get_text()
            if 'prompt' in code or 'imageUrl' in code:
                if len(code) > 50:  # Meaningful example
                    result['examples'].append(code[:500])
        
        return result
    
    def parse_model(self, model_id: str) -> Dict[str, Any]:
        """Парсить ОДНУ модель полностью"""
        
        print(f"\n🔍 Parsing: {model_id}")
        
        # Get doc URL
        url = self.get_model_doc_url(model_id)
        if not url:
            print(f"   ⚠️  No doc URL mapping for {model_id}")
            return {}
        
        # Fetch page
        html = self.fetch_page(url)
        if not html:
            return {}
        
        # Extract
        data = self.extract_from_copy_page(html, model_id)
        
        # Fallback pricing from existing data
        if not data.get('pricing') or not data['pricing'].get('usd_per_gen'):
            if model_id in self.existing_pricing:
                existing = self.existing_pricing[model_id]
                data['pricing'] = {
                    'usd_per_gen': existing.get('usd_per_gen'),
                    'rub_per_gen': existing.get('rub_per_gen'),
                    'credits_per_gen': existing.get('credits_per_gen'),
                    'source': 'pricing_table_corrected'
                }
                data['_metadata']['pricing_source'] = 'pricing_table_fallback'
                print(f"   💾 Pricing (fallback): ${existing.get('usd_per_gen', 0):.3f}")
        
        print(f"   ✅ Endpoint: {data.get('endpoint', 'N/A')}")
        print(f"   ✅ Pricing: {data.get('pricing', {})}")
        print(f"   ✅ Examples: {len(data.get('examples', []))}")
        
        return data
    
    def parse_all_models(self, limit: Optional[int] = None):
        """Парсить ВСЕ модели из registry"""
        
        print("🏗️  МАСТЕР-ПАРСЕР: Извлечение SOURCE OF TRUTH из Kie.ai\n")
        print("=" * 70)
        
        models = self.registry['models']
        model_ids = list(models.keys())
        
        if limit:
            model_ids = model_ids[:limit]
        
        parsed_data = {}
        
        for i, model_id in enumerate(model_ids, 1):
            print(f"\n[{i}/{len(model_ids)}]", end=' ')
            
            data = self.parse_model(model_id)
            if data:
                parsed_data[model_id] = data
        
        # Save
        print(f"\n\n💾 Saving to {self.OUTPUT_FILE}")
        
        output = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_models': len(model_ids),
            'parsed_successfully': len(parsed_data),
            'models': parsed_data
        }
        
        self.OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Saved {len(parsed_data)}/{len(model_ids)} models")
        print(f"\n📊 Coverage: {len(parsed_data)/len(model_ids)*100:.1f}%")
        
        return parsed_data


def main():
    """Main entry point"""
    
    import sys
    
    parser = KieMasterParser()
    
    # Parse all or specific model
    if len(sys.argv) > 1:
        if sys.argv[1] == '--all':
            # Parse ALL models (no limit)
            parser.parse_all_models(limit=None)
        else:
            model_id = sys.argv[1]
            parser.parse_model(model_id)
    else:
        # Default: parse ALL models
        print("⚠️  No arguments - parsing ALL 72 models!")
        print("   Use: python master_kie_parser.py <model_id> for single model")
        print("   Use: python master_kie_parser.py --all for explicit all\n")
        parser.parse_all_models(limit=None)


if __name__ == '__main__':
    main()
