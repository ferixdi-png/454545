#!/usr/bin/env python3
"""
Извлекает ВСЕ модели из кешированных HTML-файлов docs.kie.ai
"""

import re
import json
from pathlib import Path
from collections import defaultdict

def extract_models_from_html(html_path: Path) -> dict:
    """Извлечь модели из HTML-файла"""
    html = html_path.read_text(encoding='utf-8', errors='ignore')
    
    results = {
        "api_name": html_path.stem.replace('_', '/'),
        "models": set(),
        "endpoints": set(),
        "parameters": set()
    }
    
    # Pattern 1: "model": "model_id" в JSON/JavaScript
    models_json = re.findall(r'"model"\s*:\s*"([^"]+)"', html)
    results["models"].update(models_json)
    
    # Pattern 2: model=value в примерах кода
    models_code = re.findall(r'model\s*[=:]\s*["\']([^"\']+)["\']', html)
    results["models"].update(models_code)
    
    # Pattern 3: Модели в таблицах параметров (часто в <code>)
    models_in_code = re.findall(r'<code[^>]*>([^<]*(?:veo|runway|suno|flux|gpt)[^<]*)</code>', html, re.IGNORECASE)
    results["models"].update([m.strip() for m in models_in_code if not m.startswith('http')])
    
    # Pattern 4: Endpoints
    endpoints = re.findall(r'https://api\.kie\.ai/api/v\d+/[^\s"\'<>]+', html)
    results["endpoints"].update(endpoints)
    
    # Pattern 5: Default values в таблицах параметров
    default_models = re.findall(r'Default[^:]*:\s*["\']?([^"\'<>\s,]+)["\']?', html)
    potential_models = [m for m in default_models if any(
        keyword in m.lower() for keyword in ['veo', 'gen', 'v3', 'v4', 'flux', 'gpt', 'runway']
    )]
    results["models"].update(potential_models)
    
    return results

def main():
    cache_dir = Path("cache/kie_docs")
    
    print("🔍 ИЗВЛЕЧЕНИЕ МОДЕЛЕЙ ИЗ DOCS.KIE.AI HTML")
    print("=" * 60)
    
    all_models = defaultdict(set)
    all_endpoints = set()
    api_details = {}
    
    # Анализируем только API quickstart files (не category pages)
    api_files = [
        "_veo3-api_quickstart.html",
        "_runway-api_quickstart.html",
        "_suno-api_quickstart.html",
        "_flux-kontext-api_quickstart.html",
        "_4o-image-api_quickstart.html"
    ]
    
    for filename in api_files:
        file_path = cache_dir / filename
        if not file_path.exists():
            print(f"⚠️  {filename} не найден")
            continue
            
        print(f"\n📄 Анализ: {filename}")
        results = extract_models_from_html(file_path)
        
        api_name = filename.replace("_", "").replace("-api-quickstart.html", "")
        api_details[api_name] = results
        
        print(f"   Моделей найдено: {len(results['models'])}")
        if results['models']:
            for model in sorted(results['models']):
                if len(model) > 3 and len(model) < 50:  # Filter out too short/long
                    print(f"      • {model}")
                    all_models[api_name].add(model)
        
        print(f"   Endpoints: {len(results['endpoints'])}")
        all_endpoints.update(results['endpoints'])
    
    # Save results
    output = {
        "version": "EXTRACTED_FROM_HTML_1.0",
        "source": "cache/kie_docs/*.html",
        "total_models": sum(len(models) for models in all_models.values()),
        "total_apis": len(all_models),
        "total_endpoints": len(all_endpoints),
        "models_by_api": {k: sorted(list(v)) for k, v in all_models.items()},
        "all_endpoints": sorted(list(all_endpoints)),
        "details": {k: {
            "models": sorted(list(v["models"])),
            "endpoints": sorted(list(v["endpoints"]))
        } for k, v in api_details.items()}
    }
    
    output_path = Path("models/kie_models_extracted_from_html.json")
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 60)
    print("📊 ИТОГО:")
    print(f"   APIs: {output['total_apis']}")
    print(f"   Models: {output['total_models']}")
    print(f"   Endpoints: {output['total_endpoints']}")
    print(f"\n✅ Сохранено в: {output_path}")
    
    # Print summary by API
    print("\n📋 МОДЕЛИ ПО API:")
    for api_name, models in sorted(all_models.items()):
        print(f"\n{api_name.upper()}:")
        for model in sorted(models):
            print(f"  • {model}")

if __name__ == "__main__":
    main()
