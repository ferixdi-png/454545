#!/usr/bin/env python3
"""
ПРАВИЛЬНЫЙ сборщик source of truth.
ТОЛЬКО из документов репозитория, БЕЗ парсинга marketplace.
"""
import os
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import yaml
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    logger.warning("PyYAML not installed, YAML files will be skipped")


def find_repository_docs(root_dir: str = ".") -> List[Path]:
    """
    Найти ТОЛЬКО документы в репозитории.
    НЕ парсит marketplace, НЕ использует Selenium/Playwright.
    """
    root = Path(root_dir)
    specs = []
    exclude_dirs = {'.git', 'node_modules', '__pycache__', '.pytest_cache', 'venv', 'env', '5656-main', 'tests'}
    
    # Ищем в docs/
    docs_dir = root / "docs"
    if docs_dir.exists():
        for file in docs_dir.rglob("*"):
            if file.is_file() and file.suffix in ['.md', '.yaml', '.yml', '.json']:
                specs.append(file)
    
    # Ищем спецификации моделей в корне и app/
    for pattern in ["**/*model*.yaml", "**/*model*.yml", "**/*model*.json", "**/*model*.md"]:
        for file in root.glob(pattern):
            if file.is_file() and not any(part in exclude_dirs for part in file.parts):
                if file not in specs:
                    specs.append(file)
    
    # Ищем в app/kie_catalog или подобных местах
    for dir_name in ['app', 'models', 'config']:
        dir_path = root / dir_name
        if dir_path.exists():
            for file in dir_path.rglob("*"):
                if file.is_file() and file.suffix in ['.yaml', '.yml', '.json', '.md']:
                    if not any(part in exclude_dirs for part in file.parts):
                        if file not in specs:
                            specs.append(file)
    
    specs = sorted(set(specs))
    logger.info(f"Found {len(specs)} specification files in repository (NO marketplace parsing)")
    return specs


def parse_doc_file(path: Path) -> Optional[Dict[str, Any]]:
    """Парсинг документа из репозитория."""
    try:
        if path.suffix == '.json':
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        elif path.suffix in ['.yaml', '.yml'] and HAS_YAML:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        elif path.suffix == '.md':
            # Парсим markdown с YAML frontmatter или JSON блоками
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # YAML frontmatter
                frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
                if frontmatter_match and HAS_YAML:
                    try:
                        return yaml.safe_load(frontmatter_match.group(1))
                    except:
                        pass
                
                # JSON блок
                json_match = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    try:
                        return json.loads(json_match.group(1))
                    except:
                        pass
                
                return {'content': content, 'source_file': str(path)}
    except Exception as e:
        logger.warning(f"Failed to parse {path}: {e}")
        return None


def extract_model_from_doc(doc: Dict[str, Any], source_file: str) -> Optional[Dict[str, Any]]:
    """Извлечение информации о модели из документа."""
    # Ищем model_id
    model_id = (
        doc.get('model_id') or 
        doc.get('id') or 
        doc.get('name') or
        doc.get('model')
    )
    
    if not model_id:
        return None
    
    # Извлекаем input_schema
    input_schema = doc.get('input_schema') or doc.get('input') or doc.get('inputs') or {}
    
    # Извлекаем примеры
    example_payload = doc.get('example') or doc.get('example_payload') or doc.get('payload') or {}
    
    # Формируем нормализованную модель
    model = {
        'model_id': str(model_id),
        'category': doc.get('category', 'other'),
        'input_schema': input_schema if isinstance(input_schema, dict) else {'required': [], 'optional': [], 'properties': {}},
        'output_type': doc.get('output_type', 'json'),
        'example_payload': example_payload if isinstance(example_payload, dict) else {},
        'source_file': source_file,
        'metadata': {
            'endpoint': doc.get('endpoint', ''),
            'method': doc.get('method', 'POST'),
        }
    }
    
    return model


def collect_from_repository(output_file: str = "models/kie_models_source_of_truth.json") -> Dict[str, Any]:
    """
    Собрать source of truth ТОЛЬКО из документов репозитория.
    """
    logger.info("Collecting source of truth from repository docs ONLY (NO marketplace parsing)...")
    
    spec_files = find_repository_docs()
    models = []
    processed_files = []
    
    for spec_file in spec_files:
        logger.info(f"Processing {spec_file}")
        doc_data = parse_doc_file(spec_file)
        
        if not doc_data:
            continue
        
        processed_files.append(str(spec_file))
        
        # Обработка разных структур
        if isinstance(doc_data, dict):
            # Одна модель или список моделей
            if 'models' in doc_data and isinstance(doc_data['models'], list):
                for model_doc in doc_data['models']:
                    model = extract_model_from_doc(model_doc, str(spec_file))
                    if model:
                        models.append(model)
            else:
                # Одна модель
                model = extract_model_from_doc(doc_data, str(spec_file))
                if model:
                    models.append(model)
        elif isinstance(doc_data, list):
            # Список моделей
            for model_doc in doc_data:
                if isinstance(model_doc, dict):
                    model = extract_model_from_doc(model_doc, str(spec_file))
                    if model:
                        models.append(model)
    
    # Удаление дубликатов
    seen_ids = set()
    unique_models = []
    for model in models:
        if model['model_id'] not in seen_ids:
            seen_ids.add(model['model_id'])
            unique_models.append(model)
        else:
            logger.warning(f"Duplicate model_id: {model['model_id']}")
    
    unique_models.sort(key=lambda x: x['model_id'])
    
    result = {
        'version': '1.0.0',
        'source': 'repository_docs_only',
        'total_models': len(unique_models),
        'source_files': processed_files,
        'models': unique_models,
        'note': 'This registry contains ONLY models documented in repository. NO marketplace parsing.'
    }
    
    # Сохранение
    os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Source of truth saved: {output_file} ({len(unique_models)} models from repository docs)")
    return result


if __name__ == "__main__":
    result = collect_from_repository()
    print(f"\n[OK] Collected {result['total_models']} models from repository docs")
    print(f"[OK] Saved to: models/kie_models_source_of_truth.json")
    print(f"[NOTE] NO marketplace parsing - only repository documentation")

