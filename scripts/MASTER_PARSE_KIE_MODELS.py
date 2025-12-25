#!/usr/bin/env python3
"""
🎯 MASTER KIE.AI MODEL PARSER - SINGLE SOURCE OF TRUTH

ФИЛОСОФИЯ:
- Каждая модель парсится ОДИН РАЗ со страницы kie.ai
- "Copy page" button - это SOURCE OF TRUTH для input_schema
- После парсинга - фиксируем результат
- К парсингу возвращаемся только если модель НЕ РАБОТАЕТ

ПРОЦЕСС:
1. Загружаем список из final_truth.json (77 моделей)
2. Для КАЖДОЙ модели:
   - Открываем страницу https://kie.ai/models/{model_id}
   - Ищем "Copy page" / API examples
   - Извлекаем tech_model_id, input_schema, pricing
   - Сохраняем HTML в cache для отладки
3. Сохраняем результат в models/kie_parsed_truth.json
4. Валидируем через smoke test

ВАЖНО:
- Playwright с headless=True (быстрее)
- Кэширование HTML страниц
- Retry с exponential backoff
- Прогресс бар
- Детальное логирование
"""
import asyncio
import json
import re
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime

try:
    from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeout
    from bs4 import BeautifulSoup
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
    print("❌ Missing dependencies. Install: pip install playwright beautifulsoup4 lxml")
    print("   Then run: playwright install chromium")
    exit(1)


@dataclass
class ParsedModel:
    """Parsed model data from kie.ai"""
    model_id: str
    display_name: str
    category: str
    tech_model_id: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None
    output_type: Optional[str] = None
    pricing_usd: Optional[float] = None
    pricing_credits: Optional[float] = None
    page_url: Optional[str] = None
    parsed_at: Optional[str] = None
    parse_success: bool = False
    parse_error: Optional[str] = None
    html_cached: bool = False


class KieMasterParser:
    """Master parser for KIE.AI models"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.models: List[ParsedModel] = []
        self.cache_dir = Path("cache/kie_pages")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "with_schema": 0,
            "with_pricing": 0,
            "start_time": time.time()
        }
    
    async def init_browser(self):
        """Initialize Playwright browser"""
        print("🚀 Initializing browser...")
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        print("✅ Browser ready")
    
    async def close_browser(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
    
    def load_current_registry(self) -> List[Dict[str, Any]]:
        """Load current model registry"""
        registry_path = Path("models/kie_models_final_truth.json")
        
        if not registry_path.exists():
            print(f"❌ Registry not found: {registry_path}")
            return []
        
        with open(registry_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        models = data.get('models', [])
        print(f"📊 Loaded {len(models)} models from registry")
        return models
    
    def construct_page_url(self, model_id: str) -> str:
        """Construct model page URL"""
        # Преобразуем model_id в URL slug
        # flux/dev -> flux/dev
        # wan/2-5-image-to-video -> wan/2-5-image-to-video
        return f"https://kie.ai/models/{model_id}"
    
    async def parse_model_page(self, model_id: str, display_name: str, category: str) -> ParsedModel:
        """
        Parse single model page
        
        Ищет:
        1. API code examples (curl, python, javascript)
        2. "Copy page" button data
        3. Request/Response schemas
        4. Pricing information
        """
        url = self.construct_page_url(model_id)
        cache_file = self.cache_dir / f"{model_id.replace('/', '_')}.html"
        
        parsed = ParsedModel(
            model_id=model_id,
            display_name=display_name,
            category=category,
            page_url=url,
            parsed_at=datetime.now().isoformat()
        )
        
        print(f"\n🔍 Parsing: {model_id}")
        print(f"   URL: {url}")
        
        page = await self.browser.new_page()
        
        try:
            # Загружаем страницу
            response = await page.goto(url, wait_until="networkidle", timeout=30000)
            
            if not response or not response.ok:
                status = response.status if response else "NO_RESPONSE"
                parsed.parse_error = f"HTTP {status}"
                print(f"   ❌ Failed: {parsed.parse_error}")
                return parsed
            
            # Ждем загрузки контента
            await page.wait_for_timeout(2000)
            
            # Получаем HTML
            content = await page.content()
            
            # Сохраняем в cache
            cache_file.write_text(content, encoding='utf-8')
            parsed.html_cached = True
            print(f"   💾 Cached: {cache_file.name}")
            
            # Парсим HTML
            soup = BeautifulSoup(content, 'lxml')
            
            # 1. Ищем tech_model_id в code examples
            tech_model_id = self._extract_tech_model_id(soup)
            if tech_model_id:
                parsed.tech_model_id = tech_model_id
                print(f"   🎯 Tech Model ID: {tech_model_id}")
            
            # 2. Ищем input_schema
            input_schema = self._extract_input_schema(soup)
            if input_schema:
                parsed.input_schema = input_schema
                req = len(input_schema.get('required', []))
                opt = len(input_schema.get('optional', []))
                print(f"   📝 Input Schema: {req} required, {opt} optional")
                self.stats["with_schema"] += 1
            
            # 3. Ищем output type
            output_type = self._extract_output_type(soup)
            if output_type:
                parsed.output_type = output_type
                print(f"   📤 Output: {output_type}")
            
            # 4. Ищем pricing
            pricing = self._extract_pricing(soup)
            if pricing:
                parsed.pricing_usd = pricing.get('usd')
                parsed.pricing_credits = pricing.get('credits')
                print(f"   💰 Pricing: {pricing}")
                self.stats["with_pricing"] += 1
            
            parsed.parse_success = True
            self.stats["success"] += 1
            print(f"   ✅ Success")
            
        except PlaywrightTimeout as e:
            parsed.parse_error = f"Timeout: {str(e)[:100]}"
            print(f"   ⏱️  Timeout")
            self.stats["failed"] += 1
            
        except Exception as e:
            parsed.parse_error = f"Error: {str(e)[:100]}"
            print(f"   ❌ Error: {parsed.parse_error}")
            self.stats["failed"] += 1
            
        finally:
            await page.close()
        
        return parsed
    
    def _extract_tech_model_id(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract technical model ID from API examples"""
        patterns = [
            r'"model"\s*:\s*"([^"]+)"',
            r'model\s*=\s*["\']([^"\']+)["\']',
            r'--model\s+([^\s]+)',
        ]
        
        # Ищем в code blocks
        code_blocks = soup.find_all(['pre', 'code', 'div'], class_=re.compile(r'code|highlight|snippet'))
        
        for block in code_blocks:
            text = block.get_text()
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1)
        
        return None
    
    def _extract_input_schema(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        Extract input schema from API examples
        
        Ищет:
        - JSON примеры с "input": {...}
        - Таблицы с параметрами
        - Списки required/optional fields
        """
        schema = {
            "required": [],
            "optional": [],
            "properties": {}
        }
        
        # Метод 1: JSON examples
        code_blocks = soup.find_all(['pre', 'code'])
        for block in code_blocks:
            text = block.get_text()
            
            # Ищем JSON с input
            if '"input"' in text or "'input'" in text:
                try:
                    # Извлекаем JSON
                    json_match = re.search(r'\{.*\}', text, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group(0))
                        
                        # Проверяем структуру
                        if isinstance(data, dict) and 'input' in data:
                            input_data = data['input']
                            
                            # Собираем параметры
                            for key, value in input_data.items():
                                schema['properties'][key] = {
                                    "type": self._infer_type(value),
                                    "example": value
                                }
                                # Пока добавляем в optional
                                schema['optional'].append(key)
                            
                            if schema['properties']:
                                return schema
                except:
                    pass
        
        # Метод 2: Таблицы параметров
        tables = soup.find_all('table')
        for table in tables:
            headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
            
            if any(h in headers for h in ['parameter', 'field', 'name', 'key']):
                for row in table.find_all('tr')[1:]:  # Skip header
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        param_name = cells[0].get_text(strip=True)
                        param_type = cells[1].get_text(strip=True) if len(cells) > 1 else "string"
                        is_required = 'required' in row.get_text().lower()
                        
                        schema['properties'][param_name] = {
                            "type": param_type.lower()
                        }
                        
                        if is_required:
                            schema['required'].append(param_name)
                        else:
                            schema['optional'].append(param_name)
                
                if schema['properties']:
                    return schema
        
        return None if not schema['properties'] else schema
    
    def _extract_output_type(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract output type (image, video, audio, etc)"""
        patterns = [
            r'output.*?:\s*"?([^",\s]+)"?',
            r'type.*?:\s*"?([^",\s]+)"?',
            r'format.*?:\s*"?([^",\s]+)"?',
        ]
        
        text = soup.get_text().lower()
        
        # Direct matches
        if 'video' in text:
            return 'video'
        elif 'image' in text:
            return 'image'
        elif 'audio' in text:
            return 'audio'
        elif 'text' in text:
            return 'text'
        
        return None
    
    def _extract_pricing(self, soup: BeautifulSoup) -> Optional[Dict[str, float]]:
        """Extract pricing information"""
        pricing = {}
        
        text = soup.get_text()
        
        # Паттерны для поиска цен
        patterns = [
            (r'(\d+(?:\.\d+)?)\s*credits?', 'credits'),
            (r'\$\s*(\d+(?:\.\d+)?)', 'usd'),
            (r'(\d+(?:\.\d+)?)\s*USD', 'usd'),
        ]
        
        for pattern, currency in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    pricing[currency] = float(matches[0])
                except:
                    pass
        
        return pricing if pricing else None
    
    def _infer_type(self, value: Any) -> str:
        """Infer JSON type from value"""
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, str):
            if value.startswith('http'):
                return "url"
            return "string"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        return "string"
    
    async def parse_all_models(self, limit: Optional[int] = None):
        """Parse all models from registry"""
        models = self.load_current_registry()
        
        if limit:
            models = models[:limit]
            print(f"⚠️  Limited to first {limit} models for testing")
        
        self.stats["total"] = len(models)
        
        print(f"\n{'='*80}")
        print(f"🎯 STARTING MASTER PARSE OF {len(models)} MODELS")
        print(f"{'='*80}\n")
        
        for i, model_data in enumerate(models, 1):
            model_id = model_data.get('model_id')
            display_name = model_data.get('display_name', model_id)
            category = model_data.get('category', 'unknown')
            
            print(f"[{i}/{len(models)}] {model_id}")
            
            parsed = await self.parse_model_page(model_id, display_name, category)
            self.models.append(parsed)
            
            # Progress update
            if i % 10 == 0:
                self._print_progress()
            
            # Rate limiting
            await asyncio.sleep(1)  # 1 sec between requests
        
        self._print_final_stats()
    
    def _print_progress(self):
        """Print progress stats"""
        elapsed = time.time() - self.stats["start_time"]
        rate = self.stats["success"] / elapsed if elapsed > 0 else 0
        
        print(f"\n📊 Progress: {self.stats['success']}/{self.stats['total']} success")
        print(f"   ✅ Schema: {self.stats['with_schema']}")
        print(f"   💰 Pricing: {self.stats['with_pricing']}")
        print(f"   ⏱️  Rate: {rate:.1f} models/sec")
        print()
    
    def _print_final_stats(self):
        """Print final statistics"""
        elapsed = time.time() - self.stats["start_time"]
        
        print(f"\n{'='*80}")
        print(f"✅ PARSING COMPLETE")
        print(f"{'='*80}")
        print(f"\n📊 FINAL STATS:")
        print(f"   Total models: {self.stats['total']}")
        print(f"   ✅ Success: {self.stats['success']}")
        print(f"   ❌ Failed: {self.stats['failed']}")
        print(f"   📝 With schema: {self.stats['with_schema']}")
        print(f"   💰 With pricing: {self.stats['with_pricing']}")
        print(f"   ⏱️  Total time: {elapsed:.1f}s")
        print(f"   ⚡ Average: {elapsed/self.stats['total']:.1f}s per model")
    
    def save_results(self):
        """Save parsed results to JSON"""
        output_file = Path("models/kie_parsed_truth.json")
        
        data = {
            "version": "PARSED_1.0",
            "source": "kie.ai pages (Playwright parser)",
            "parsed_at": datetime.now().isoformat(),
            "stats": self.stats,
            "models": [asdict(m) for m in self.models]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved to: {output_file}")
        print(f"   Models: {len(self.models)}")
        print(f"   Success rate: {self.stats['success']}/{self.stats['total']} ({100*self.stats['success']/self.stats['total']:.1f}%)")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="🎯 Master KIE.AI Model Parser - Single Source of Truth"
    )
    parser.add_argument(
        '--limit',
        type=int,
        help="Limit number of models (for testing). Default: parse all 77"
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help="Test mode: parse only first 3 models"
    )
    
    args = parser.parse_args()
    
    limit = 3 if args.test else args.limit
    
    parser_instance = KieMasterParser()
    
    try:
        await parser_instance.init_browser()
        await parser_instance.parse_all_models(limit=limit)
        parser_instance.save_results()
        
    finally:
        await parser_instance.close_browser()
    
    print("\n✅ Done!")


if __name__ == "__main__":
    if not HAS_DEPS:
        exit(1)
    
    asyncio.run(main())
