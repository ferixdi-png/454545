#!/usr/bin/env python3
"""
Анализ репозитория для определения реального source of truth.
НЕ парсит marketplace, только то что есть в репозитории.
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def find_repository_docs(root_dir: str = ".") -> Dict[str, List[str]]:
    """
    Найти все документы в репозитории.
    НЕ парсит marketplace, только локальные файлы.
    """
    root = Path(root_dir)
    results = {
        'docs_md': [],
        'docs_yaml': [],
        'docs_json': [],
        'api_contracts': [],
        'model_specs': []
    }
    
    # Ищем в docs/
    docs_dir = root / "docs"
    if docs_dir.exists():
        for file in docs_dir.rglob("*"):
            if file.is_file():
                if file.suffix == '.md':
                    results['docs_md'].append(str(file))
                elif file.suffix in ['.yaml', '.yml']:
                    results['docs_yaml'].append(str(file))
                elif file.suffix == '.json':
                    results['docs_json'].append(str(file))
    
    # Ищем в корне и других директориях (но не в node_modules, .git и т.д.)
    exclude_dirs = {'.git', 'node_modules', '__pycache__', '.pytest_cache', 'venv', 'env', '5656-main'}
    
    for file in root.rglob("*"):
        if file.is_file() and not any(part in exclude_dirs for part in file.parts):
            # Ищем API контракты
            if 'api' in file.name.lower() or 'contract' in file.name.lower():
                if file.suffix in ['.md', '.yaml', '.yml', '.json']:
                    results['api_contracts'].append(str(file))
            
            # Ищем спецификации моделей
            if 'model' in file.name.lower() and file.suffix in ['.yaml', '.yml', '.json', '.md']:
                if 'docs' not in str(file) or 'docs' in str(file.parent):
                    results['model_specs'].append(str(file))
    
    return results


def analyze_api_contracts(files: List[str]) -> Dict[str, Any]:
    """Анализ API контрактов."""
    contracts = {
        'createTask': None,
        'recordInfo': None,
        'errors': []
    }
    
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Ищем упоминания createTask
                if 'createTask' in content or 'create_task' in content:
                    contracts['createTask'] = file_path
                
                # Ищем упоминания recordInfo
                if 'recordInfo' in content or 'record_info' in content:
                    contracts['recordInfo'] = file_path
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            contracts['errors'].append(str(e))
    
    return contracts


def generate_missing_report(analysis: Dict[str, Any]) -> str:
    """Генерация отчёта о недостающих данных."""
    report = []
    report.append("=" * 60)
    report.append("ОТЧЁТ: ЧЕГО НЕ ХВАТАЕТ ДЛЯ SOURCE OF TRUTH")
    report.append("=" * 60)
    report.append("")
    
    # Проверка документов
    report.append("1. ДОКУМЕНТАЦИЯ:")
    if not analysis['docs_md'] and not analysis['docs_yaml']:
        report.append("   [MISSING] НЕТ документации в docs/")
        report.append("   НУЖНО: Создать docs/ с описанием моделей")
    else:
        report.append(f"   [OK] Найдено: {len(analysis['docs_md'])} .md, {len(analysis['docs_yaml'])} .yaml")
    
    report.append("")
    
    # Проверка API контрактов
    report.append("2. API КОНТРАКТЫ:")
    if not analysis['api_contracts_found']['createTask']:
        report.append("   [MISSING] НЕТ контракта createTask")
        report.append("   НУЖНО: Документация формата createTask (payload, response)")
    else:
        report.append(f"   [OK] createTask найден: {analysis['api_contracts_found']['createTask']}")
    
    if not analysis['api_contracts_found']['recordInfo']:
        report.append("   [MISSING] НЕТ контракта recordInfo")
        report.append("   НУЖНО: Документация формата recordInfo (state, resultJson, errors)")
    else:
        report.append(f"   [OK] recordInfo найден: {analysis['api_contracts_found']['recordInfo']}")
    
    report.append("")
    
    # Проверка спецификаций моделей
    report.append("3. СПЕЦИФИКАЦИИ МОДЕЛЕЙ:")
    if not analysis['model_specs']:
        report.append("   [MISSING] НЕТ спецификаций моделей")
        report.append("   НУЖНО: Файлы с описанием каждой модели (input schema, примеры)")
    else:
        report.append(f"   [OK] Найдено: {len(analysis['model_specs'])} файлов")
        report.append("   Файлы:")
        for spec in analysis['model_specs'][:10]:
            report.append(f"     - {spec}")
    
    report.append("")
    report.append("=" * 60)
    report.append("РЕКОМЕНДАЦИИ:")
    report.append("=" * 60)
    report.append("")
    report.append("1. Создать docs/ с документацией по моделям")
    report.append("2. Добавить API контракты (createTask, recordInfo)")
    report.append("3. Для каждой модели указать:")
    report.append("   - model_id")
    report.append("   - input_schema (required/optional, types)")
    report.append("   - пример payload для createTask")
    report.append("   - формат resultJson")
    report.append("   - возможные ошибки")
    report.append("")
    
    return "\n".join(report)


if __name__ == "__main__":
    logger.info("Анализ репозитория...")
    
    # Найти документы
    docs = find_repository_docs()
    
    # Анализ API контрактов
    api_contracts = analyze_api_contracts(docs['api_contracts'])
    
    # Подготовка анализа
    analysis = {
        'docs_md': docs['docs_md'],
        'docs_yaml': docs['docs_yaml'],
        'docs_json': docs['docs_json'],
        'model_specs': docs['model_specs'],
        'api_contracts_found': {
            'createTask': api_contracts['createTask'],
            'recordInfo': api_contracts['recordInfo']
        }
    }
    
    # Генерация отчёта
    report = generate_missing_report(analysis)
    print(report)
    
    # Сохранение анализа
    with open('repository_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    
    logger.info("Анализ сохранён в repository_analysis.json")

