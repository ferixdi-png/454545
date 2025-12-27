#!/usr/bin/env python3
"""
🎯 КРИТИЧЕСКИ ВАЖНЫЙ СКРИПТ: PARSE COPY PAGE FOR EACH MODEL

ЭТО ЕДИНСТВЕННЫЙ ИСТОЧНИК ПРАВДЫ!
Для КАЖДОЙ модели на kie.ai:
1. Открываем страницу модели kie.ai/{slug}
2. Находим Copy page / API tab
3. Извлекаем:
   - Точный endpoint URL
   - Точный model_id (tech ID)
   - Все параметры с типами
   - Примеры request/response
   - Pricing (credits/gen)
4. Сохраняем как SOURCE OF TRUTH

ЭТОТ ФАЙЛ СОЗДАЕТСЯ ОДИН РАЗ И СТАНОВИТСЯ БАЗОЙ.
Возвращаемся к парсингу ТОЛЬКО если что-то сломалось.
"""

import json
import httpx
import re
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, List, Any, Optional


class KieCopyPageParser:
    """Парсер Copy page/API для каждой модели Kie.ai"""
    
    def __init__(self):
        self.cache_dir = Path("cache/kie_model_pages")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(timeout=30.0, follow_redirects=True)
        
        # Список известных моделей из разных источников
        self.known_models = self._build_initial_model_list()
    
    def _build_initial_model_list(self) -> List[Dict[str, str]]:
        """Строим начальный список моделей из docs + pricing hints"""
        
        models = []
        
        # Из docs.kie.ai мы знаем основные API
        docs_apis = [
            {"slug": "veo-3", "name": "Veo 3.1", "category": "video"},
            {"slug": "runway-gen-3-alpha", "name": "Runway Gen-3 Alpha", "category": "video"},
            {"slug": "suno-v4", "name": "Suno V4", "category": "audio"},
            {"slug": "gpt-4o-image", "name": "GPT-4o Image", "category": "image"},
            {"slug": "flux-kontext", "name": "Flux Kontext", "category": "image"},
        ]
        
        # Добавим известные варианты из pricing hints
        additional_models = [
            {"slug": "flux-dev", "name": "Flux Dev", "category": "image"},
            {"slug": "flux-pro", "name": "Flux Pro", "category": "image"},
            {"slug": "flux-schnell", "name": "Flux Schnell", "category": "image"},
            {"slug": "stable-diffusion-3", "name": "Stable Diffusion 3", "category": "image"},
            {"slug": "kling-ai", "name": "Kling AI", "category": "video"},
            {"slug": "luma-dream-machine", "name": "Luma Dream Machine", "category": "video"},
            {"slug": "minimax-video", "name": "MiniMax Video", "category": "video"},
        ]
        
        models.extend(docs_apis)
        models.extend(additional_models)
        
        return models
    
    def fetch_model_page(self, slug: str) -> Optional[str]:
        """Скачиваем страницу модели"""
        
        cache_file = self.cache_dir / f"{slug}.html"
        
        # Проверяем кэш
        if cache_file.exists():
            print(f"  📦 Using cache: {slug}")
            return cache_file.read_text(encoding='utf-8')
        
        # Скачиваем
        try:
            url = f"https://kie.ai/{slug}"
            print(f"  🌐 Fetching: {url}")
            response = self.client.get(url)
            
            if response.status_code == 200:
                html = response.text
                cache_file.write_text(html, encoding='utf-8')
                return html
            else:
                print(f"  ❌ Error {response.status_code} for {slug}")
                return None
                
        except Exception as e:
            print(f"  ❌ Exception fetching {slug}: {e}")
            return None
    
    def extract_copy_page_data(self, html: str, model_name: str) -> Dict[str, Any]:
        """
        Извлекаем данные из Copy page/API tab
        
        Ищем:
        - <code> блоки с примерами API
        - JSON payload примеры
        - endpoint URLs
        - model_id values
        - параметры и их типы
        """
        
        soup = BeautifulSoup(html, 'lxml')
        
        data = {
            "model_name": model_name,
            "endpoints": [],
            "model_ids": [],
            "parameters": {},
            "request_examples": [],
            "response_examples": [],
            "pricing": {},
            "raw_code_blocks": []
        }
        
        # 1. Извлекаем все <code> и <pre> блоки
        code_blocks = soup.find_all(['code', 'pre'])
        for block in code_blocks:
            text = block.get_text()
            data["raw_code_blocks"].append(text)
            
            # Ищем endpoints
            endpoints = re.findall(r'https://api\.kie\.ai[^\s"\'<>]+', text)
            data["endpoints"].extend(endpoints)
            
            # Ищем model_id values
            model_ids = re.findall(r'"model":\s*"([^"]+)"', text)
            data["model_ids"].extend(model_ids)
            
            # Пытаемся распарсить как JSON
            try:
                if '{' in text and '}' in text:
                    # Извлекаем JSON объект
                    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
                    if json_match:
                        json_obj = json.loads(json_match.group(0))
                        
                        # Если это request example
                        if 'model' in json_obj or 'prompt' in json_obj:
                            data["request_examples"].append(json_obj)
                            
                            # Извлекаем параметры
                            for key, value in json_obj.items():
                                if key not in data["parameters"]:
                                    data["parameters"][key] = {
                                        "type": type(value).__name__,
                                        "examples": []
                                    }
                                data["parameters"][key]["examples"].append(value)
                        
                        # Если это response example
                        elif 'taskId' in json_obj or 'data' in json_obj:
                            data["response_examples"].append(json_obj)
                            
            except json.JSONDecodeError:
                pass
        
        # 2. Ищем pricing информацию
        text_content = soup.get_text()
        
        # Паттерны для pricing
        credits_match = re.search(r'(\d+(?:\.\d+)?)\s*credits?(?:/gen)?', text_content, re.IGNORECASE)
        usd_match = re.search(r'\$(\d+(?:\.\d+)?)(?:/gen)?', text_content)
        
        if credits_match:
            data["pricing"]["credits_per_gen"] = float(credits_match.group(1))
        if usd_match:
            data["pricing"]["usd_per_gen"] = float(usd_match.group(1))
        
        # 3. Дедупликация
        data["endpoints"] = list(set(data["endpoints"]))
        data["model_ids"] = list(set(data["model_ids"]))
        
        return data
    
    def parse_all_models(self) -> Dict[str, Any]:
        """Парсим ВСЕ модели и создаем SOURCE OF TRUTH"""
        
        print("=" * 80)
        print("🎯 PARSING COPY PAGE FOR ALL MODELS - SOURCE OF TRUTH")
        print("=" * 80)
        
        results = {
            "version": "COPY_PAGE_SOURCE_OF_TRUTH_1.0",
            "parsed_at": datetime.now().isoformat(),
            "source": "kie.ai/{slug} - Copy page/API tab",
            "models": {}
        }
        
        print(f"\n📋 Total models to parse: {len(self.known_models)}\n")
        
        for idx, model_info in enumerate(self.known_models, 1):
            slug = model_info["slug"]
            name = model_info["name"]
            category = model_info["category"]
            
            print(f"[{idx}/{len(self.known_models)}] Parsing: {name} ({slug})")
            
            # Скачиваем страницу
            html = self.fetch_model_page(slug)
            if not html:
                results["models"][slug] = {
                    "status": "FAILED",
                    "error": "Could not fetch page"
                }
                continue
            
            # Извлекаем Copy page данные
            copy_data = self.extract_copy_page_data(html, name)
            
            # Валидация
            if not copy_data["endpoints"]:
                print(f"  ⚠️  WARNING: No endpoints found!")
            if not copy_data["model_ids"]:
                print(f"  ⚠️  WARNING: No model_ids found!")
            
            # Сохраняем
            results["models"][slug] = {
                "status": "SUCCESS",
                "name": name,
                "category": category,
                "slug": slug,
                "copy_page_data": copy_data,
                "has_endpoint": len(copy_data["endpoints"]) > 0,
                "has_model_id": len(copy_data["model_ids"]) > 0,
                "has_pricing": len(copy_data["pricing"]) > 0
            }
            
            print(f"  ✅ Endpoints: {len(copy_data['endpoints'])}")
            print(f"  ✅ Model IDs: {len(copy_data['model_ids'])}")
            print(f"  ✅ Parameters: {len(copy_data['parameters'])}")
            print(f"  ✅ Examples: {len(copy_data['request_examples'])}")
            if copy_data["pricing"]:
                print(f"  💰 Pricing: {copy_data['pricing']}")
            print()
        
        # Summary
        total = len(results["models"])
        success = sum(1 for m in results["models"].values() if m["status"] == "SUCCESS")
        with_endpoint = sum(1 for m in results["models"].values() if m.get("has_endpoint"))
        with_model_id = sum(1 for m in results["models"].values() if m.get("has_model_id"))
        with_pricing = sum(1 for m in results["models"].values() if m.get("has_pricing"))
        
        results["summary"] = {
            "total_models": total,
            "successful_parses": success,
            "with_endpoint": with_endpoint,
            "with_model_id": with_model_id,
            "with_pricing": with_pricing,
            "ready_for_integration": min(with_endpoint, with_model_id)
        }
        
        print("=" * 80)
        print("📊 PARSING SUMMARY")
        print("=" * 80)
        print(f"Total models: {total}")
        print(f"Successfully parsed: {success}")
        print(f"With endpoint: {with_endpoint}")
        print(f"With model_id: {with_model_id}")
        print(f"With pricing: {with_pricing}")
        print(f"✅ Ready for integration: {results['summary']['ready_for_integration']}")
        print()
        
        return results
    
    def save_results(self, results: Dict[str, Any]):
        """Сохраняем SOURCE OF TRUTH"""
        
        output_file = Path("models/kie_copy_page_source_of_truth.json")
        
        with output_file.open('w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Saved SOURCE OF TRUTH: {output_file}")
        print(f"   Size: {output_file.stat().st_size / 1024:.1f} KB")
        print()
        
        # Создаем также краткую версию для быстрого просмотра
        summary_file = Path("models/kie_copy_page_summary.json")
        
        summary = {
            "version": results["version"],
            "parsed_at": results["parsed_at"],
            "summary": results["summary"],
            "models_ready": {}
        }
        
        for slug, model in results["models"].items():
            if model.get("has_endpoint") and model.get("has_model_id"):
                summary["models_ready"][slug] = {
                    "name": model["name"],
                    "category": model["category"],
                    "endpoint": model["copy_page_data"]["endpoints"][0] if model["copy_page_data"]["endpoints"] else None,
                    "model_id": model["copy_page_data"]["model_ids"][0] if model["copy_page_data"]["model_ids"] else None,
                    "pricing": model["copy_page_data"]["pricing"]
                }
        
        with summary_file.open('w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Saved summary: {summary_file}")
        print(f"   Ready models: {len(summary['models_ready'])}")


def main():
    """Main execution"""
    
    parser = KieCopyPageParser()
    results = parser.parse_all_models()
    parser.save_results(results)
    
    print("\n" + "=" * 80)
    print("🎉 SOURCE OF TRUTH CREATED!")
    print("=" * 80)
    print("\nЭтот файл теперь БАЗА для всех моделей.")
    print("Возвращаемся к парсингу ТОЛЬКО если API изменился.")
    print("\nСледующие шаги:")
    print("1. Валидация реальными тестами (топ-5 дешевых)")
    print("2. Построение registry v7 на основе этих данных")
    print("3. Обновление бота")
    print()


if __name__ == "__main__":
    main()
