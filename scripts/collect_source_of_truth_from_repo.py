#!/usr/bin/env python3
"""
Collect source of truth for Kie.ai models ONLY from repository files.
NO web scraping, NO marketplace parsing.

Sources:
- docs/*.md, docs/*.yaml, docs/*.json
- models/*.yaml, models/*.json
- *.md, *.yaml, *.json in root
"""
import os
import json
import yaml
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def find_repository_docs(root_dir: str = ".") -> List[Path]:
    """Find all documentation files in repository."""
    docs = []
    
    # Search patterns
    patterns = [
        "docs/**/*.md",
        "docs/**/*.yaml",
        "docs/**/*.yml",
        "docs/**/*.json",
        "models/**/*.yaml",
        "models/**/*.yml",
        "models/**/*.json",
        "*.md",
        "*.yaml",
        "*.yml",
    ]
    
    for pattern in patterns:
        for path in Path(root_dir).glob(pattern):
            if path.is_file() and path not in docs:
                # Skip certain files
                if any(skip in str(path) for skip in ['README', 'CHANGELOG', 'LICENSE', '.git']):
                    continue
                docs.append(path)
    
    return sorted(docs)


def extract_model_info_from_markdown(content: str) -> List[Dict[str, Any]]:
    """Extract model information from Markdown files."""
    models = []
    
    # Look for code blocks with JSON/YAML
    json_pattern = r'```(?:json|yaml)?\s*(\{.*?\})\s*```'
    yaml_pattern = r'```(?:yaml|yml)?\s*([\s\S]*?)\s*```'
    
    # Try JSON first
    for match in re.finditer(json_pattern, content, re.DOTALL):
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict) and 'model_id' in data:
                models.append(data)
            elif isinstance(data, list):
                models.extend([m for m in data if isinstance(m, dict) and 'model_id' in m])
        except:
            pass
    
    # Try YAML
    for match in re.finditer(yaml_pattern, content, re.DOTALL):
        try:
            data = yaml.safe_load(match.group(1))
            if isinstance(data, dict) and 'model_id' in data:
                models.append(data)
            elif isinstance(data, list):
                models.extend([m for m in data if isinstance(m, dict) and 'model_id' in m])
        except:
            pass
    
    # Look for model_id patterns in text
    model_id_pattern = r'model[_\s-]?id["\']?\s*[:=]\s*["\']?([^"\'\s]+)["\']?'
    for match in re.finditer(model_id_pattern, content, re.IGNORECASE):
        model_id = match.group(1)
        if model_id and len(model_id) > 2:
            # Try to extract more info around this
            models.append({
                'model_id': model_id,
                'source': 'markdown_text',
                'input_schema': {'required': [], 'optional': [], 'properties': {}}
            })
    
    return models


def extract_model_info_from_yaml(file_path: Path) -> List[Dict[str, Any]]:
    """Extract model information from YAML file."""
    models = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            
            if isinstance(data, dict):
                if 'model_id' in data:
                    models.append(data)
                elif 'models' in data:
                    models.extend([m for m in data['models'] if isinstance(m, dict)])
                elif 'model' in data:
                    models.append(data['model'])
            elif isinstance(data, list):
                models.extend([m for m in data if isinstance(m, dict)])
    except Exception as e:
        logger.warning(f"Failed to parse YAML {file_path}: {e}")
    
    return models


def extract_model_info_from_json(file_path: Path) -> List[Dict[str, Any]]:
    """Extract model information from JSON file."""
    models = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            if isinstance(data, dict):
                if 'model_id' in data:
                    models.append(data)
                elif 'models' in data:
                    models.extend([m for m in data['models'] if isinstance(m, dict)])
            elif isinstance(data, list):
                models.extend([m for m in data if isinstance(m, dict)])
    except Exception as e:
        logger.warning(f"Failed to parse JSON {file_path}: {e}")
    
    return models


def normalize_model_spec(model: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize model specification to standard format."""
    normalized = {
        'model_id': model.get('model_id') or model.get('id') or model.get('name') or 'unknown',
        'category': model.get('category') or model.get('type') or 'general',
        'input_schema': {
            'required': model.get('required', []) or model.get('required_fields', []),
            'optional': model.get('optional', []) or model.get('optional_fields', []),
            'properties': model.get('properties', {}) or model.get('input_properties', {})
        },
        'output_type': model.get('output_type') or model.get('output') or 'url',
        'description': model.get('description') or model.get('desc') or ''
    }
    
    # Ensure input_schema structure
    if not normalized['input_schema']['properties']:
        # Try to infer from required/optional
        props = {}
        for field in normalized['input_schema']['required'] + normalized['input_schema']['optional']:
            if isinstance(field, str):
                props[field] = {'type': 'string'}
            elif isinstance(field, dict):
                props.update(field)
        normalized['input_schema']['properties'] = props
    
    return normalized


def collect_source_of_truth() -> Dict[str, Any]:
    """Collect source of truth from repository files only."""
    logger.info("Collecting source of truth from repository files...")
    
    all_models = []
    seen_model_ids = set()
    
    # Find all documentation files
    doc_files = find_repository_docs()
    logger.info(f"Found {len(doc_files)} documentation files")
    
    for doc_file in doc_files:
        logger.info(f"Processing: {doc_file}")
        
        try:
            with open(doc_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            models = []
            
            if doc_file.suffix in ['.yaml', '.yml']:
                models = extract_model_info_from_yaml(doc_file)
            elif doc_file.suffix == '.json':
                models = extract_model_info_from_json(doc_file)
            elif doc_file.suffix == '.md':
                models = extract_model_info_from_markdown(content)
            
            # Normalize and deduplicate
            for model in models:
                normalized = normalize_model_spec(model)
                model_id = normalized['model_id']
                
                if model_id and model_id != 'unknown' and model_id not in seen_model_ids:
                    seen_model_ids.add(model_id)
                    all_models.append(normalized)
                    logger.info(f"  Found model: {model_id}")
        
        except Exception as e:
            logger.warning(f"Error processing {doc_file}: {e}")
    
    logger.info(f"Total models collected: {len(all_models)}")
    
    return {
        'version': '1.0',
        'source': 'repository_docs_only',
        'models': all_models
    }


def main():
    """Main entrypoint."""
    source_of_truth = collect_source_of_truth()
    
    # Save to file
    output_file = Path("models/kie_models_source_of_truth.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(source_of_truth, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Source of truth saved to {output_file}")
    logger.info(f"Total models: {len(source_of_truth['models'])}")
    
    return 0 if source_of_truth['models'] else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())

