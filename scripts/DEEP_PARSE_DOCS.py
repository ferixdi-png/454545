#!/usr/bin/env python3
"""
🎯 DEEP PARSER - Извлечение ВСЕХ деталей из Kie.ai docs

Парсит каждую страницу API документации чтобы извлечь:
1. Model IDs и их варианты
2. Request/Response примеры
3. Все параметры с типами и описаниями
4. Pricing (если указан)
5. Эндпойнты для каждой модели

ЦЕЛЬ: Создать ПОЛНЫЙ SOURCE OF TRUTH для каждой модели
"""
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Dict, List, Any
from datetime import datetime


def extract_code_examples(html: str) -> List[Dict]:
    """Извлечь все code examples из HTML"""
    soup = BeautifulSoup(html, 'lxml')
    examples = []
    
    # Ищем все code blocks
    code_blocks = soup.find_all(['code', 'pre'])
    
    for block in code_blocks:
        text = block.get_text()
        
        # Пытаемся найти JSON
        json_matches = re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        
        for match in json_matches:
            json_text = match.group(0)
            try:
                data = json.loads(json_text)
                examples.append(data)
            except:
                # Попробуем очистить и повторить
                try:
                    cleaned = re.sub(r'//.*\n', '\n', json_text)  # Remove comments
                    cleaned = re.sub(r',\s*}', '}', cleaned)  # Remove trailing commas
                    data = json.loads(cleaned)
                    examples.append(data)
                except:
                    pass
    
    return examples


def parse_api_page_deep(html_file: Path) -> Dict[str, Any]:
    """Глубокий парсинг страницы API"""
    html = html_file.read_text(encoding='utf-8')
    soup = BeautifulSoup(html, 'lxml')
    
    info = {
        "file": html_file.name,
        "title": "",
        "endpoints": [],
        "models": set(),
        "parameters": {},
        "examples": {},
        "pricing": {}
    }
    
    # Title
    title = soup.find('h1')
    if title:
        info['title'] = title.get_text(strip=True)
    
    # Extract all URLs
    urls = re.findall(r'https://api\.kie\.ai/[^\s"\'<>]+', html)
    info['endpoints'] = list(set(urls))
    
    # Extract code examples
    examples = extract_code_examples(html)
    
    # Analyze examples
    for ex in examples:
        # Model ID
        if 'model' in ex:
            info['models'].add(ex['model'])
        
        # Parameters from examples
        if 'input' in ex or isinstance(ex, dict):
            params = ex.get('input', ex)
            for key, value in params.items():
                if key not in info['parameters']:
                    info['parameters'][key] = {
                        'examples': [],
                        'type': type(value).__name__
                    }
                info['parameters'][key]['examples'].append(value)
        
        # Store full example
        example_type = 'request' if any(k in ex for k in ['model', 'input', 'prompt']) else 'response'
        if example_type not in info['examples']:
            info['examples'][example_type] = []
        info['examples'][example_type].append(ex)
    
    # Convert sets to lists for JSON serialization
    info['models'] = sorted(list(info['models']))
    
    return info


def main():
    docs_dir = Path('cache/kie_docs')
    
    if not docs_dir.exists():
        print("❌ Cache dir not found. Run PARSE_KIE_DOCS.py first")
        return
    
    all_apis = {}
    
    print("="*80)
    print("🎯 DEEP PARSING KIE.AI DOCS")
    print("="*80)
    
    for html_file in sorted(docs_dir.glob('*.html')):
        print(f"\n📄 Parsing: {html_file.name}")
        
        api_info = parse_api_page_deep(html_file)
        
        if api_info['endpoints'] or api_info['models']:
            all_apis[html_file.stem] = api_info
            
            print(f"   Title: {api_info['title']}")
            print(f"   Endpoints: {len(api_info['endpoints'])}")
            print(f"   Models: {api_info['models']}")
            print(f"   Parameters: {len(api_info['parameters'])}")
            print(f"   Examples: request={len(api_info['examples'].get('request', []))}, response={len(api_info['examples'].get('response', []))}")
    
    # Save results
    output = {
        "version": "DEEP_PARSE_1.0",
        "parsed_at": datetime.now().isoformat(),
        "source": "docs.kie.ai (deep parse)",
        "apis": all_apis,
        "summary": {
            "total_apis": len(all_apis),
            "total_endpoints": sum(len(api['endpoints']) for api in all_apis.values()),
            "total_models": len(set(m for api in all_apis.values() for m in api['models'])),
            "total_params": sum(len(api['parameters']) for api in all_apis.values())
        }
    }
    
    output_file = Path("models/kie_docs_deep_parse.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*80}")
    print(f"💾 Saved: {output_file}")
    print(f"\n📊 Summary:")
    for key, value in output['summary'].items():
        print(f"   {key}: {value}")
    
    # Показываем найденные модели
    all_models = sorted(set(m for api in all_apis.values() for m in api['models']))
    if all_models:
        print(f"\n🎯 Найденные Model IDs ({len(all_models)}):")
        for model in all_models:
            print(f"   - {model}")


if __name__ == "__main__":
    main()
