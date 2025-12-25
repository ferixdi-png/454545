#!/usr/bin/env python3
"""
Collect Kie.ai models source of truth from all specifications.
Searches docs/, models/*.yaml, *.md, *.json and creates unified registry.
"""
import os
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import yaml, but make it optional
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    logger.warning("PyYAML not installed, YAML files will be skipped")


def find_model_specs(root_dir: str = ".") -> List[Path]:
    """Find all model specification files."""
    specs = []
    root = Path(root_dir)
    
    # Search patterns
    patterns = [
        "**/models/**/*.yaml",
        "**/models/**/*.yml",
        "**/models/**/*.json",
        "**/docs/**/*.md",
        "**/docs/**/*.yaml",
        "**/docs/**/*.json",
        "**/*model*.yaml",
        "**/*model*.json",
    ]
    
    for pattern in patterns:
        specs.extend(root.glob(pattern))
    
    # Remove duplicates and sort
    specs = sorted(set(specs))
    logger.info(f"Found {len(specs)} specification files")
    return specs


def extract_model_id_from_path(path: Path) -> Optional[str]:
    """Extract model_id from file path or name."""
    name = path.stem
    name = re.sub(r'^(model|spec|config|kie)[_-]?', '', name, flags=re.I)
    name = re.sub(r'[_-](model|spec|config)$', '', name, flags=re.I)
    return name if name else None


def parse_yaml_spec(path: Path) -> Optional[Dict[str, Any]]:
    """Parse YAML specification file."""
    if not HAS_YAML:
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if not data:
                return None
            if isinstance(data, dict):
                if 'model_id' in data or 'id' in data or 'name' in data:
                    return data
                elif isinstance(data.get('models'), list):
                    return {'models': data['models']}
                elif 'model' in data:
                    return data['model'] if isinstance(data['model'], dict) else data
            return data
    except Exception as e:
        logger.warning(f"Failed to parse YAML {path}: {e}")
        return None


def parse_json_spec(path: Path) -> Optional[Dict[str, Any]]:
    """Parse JSON specification file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not data:
                return None
            if isinstance(data, list):
                return {'models': data}
            elif isinstance(data, dict):
                if 'models' in data:
                    return data
                elif 'model_id' in data or 'id' in data:
                    return data
            return data
    except Exception as e:
        logger.warning(f"Failed to parse JSON {path}: {e}")
        return None


def parse_markdown_spec(path: Path) -> Optional[Dict[str, Any]]:
    """Parse Markdown specification file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            if HAS_YAML:
                frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
                if frontmatter_match:
                    try:
                        data = yaml.safe_load(frontmatter_match.group(1))
                        return data
                    except:
                        pass
            
            json_match = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                    return data
                except:
                    pass
            
            model_id = extract_model_id_from_path(path)
            if model_id:
                return {'model_id': model_id, 'source_file': str(path)}
    except Exception as e:
        logger.warning(f"Failed to parse Markdown {path}: {e}")
        return None


def extract_input_schema(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Extract input schema from specification."""
    schema = {'required': [], 'optional': [], 'properties': {}}
    
    input_keys = ['input', 'inputs', 'input_schema', 'parameters', 'params', 'fields']
    for key in input_keys:
        if key in spec:
            input_data = spec[key]
            if isinstance(input_data, dict):
                if 'required' in input_data:
                    schema['required'] = input_data['required']
                if 'properties' in input_data:
                    schema['properties'] = input_data['properties']
                    all_fields = set(input_data['properties'].keys())
                    required_fields = set(input_data.get('required', []))
                    schema['optional'] = list(all_fields - required_fields)
                break
            elif isinstance(input_data, list):
                for field in input_data:
                    if isinstance(field, dict):
                        field_name = field.get('name') or field.get('field')
                        if field_name:
                            schema['properties'][field_name] = {
                                'type': field.get('type', 'string'),
                                'description': field.get('description', ''),
                                'required': field.get('required', False)
                            }
                            if field.get('required'):
                                schema['required'].append(field_name)
                            else:
                                schema['optional'].append(field_name)
    
    return schema


def extract_output_type(spec: Dict[str, Any]) -> str:
    """Extract output type from specification."""
    output_keys = ['output', 'output_type', 'output_format', 'result_type']
    for key in output_keys:
        if key in spec:
            output = spec[key]
            if isinstance(output, str):
                return output
            elif isinstance(output, dict) and 'type' in output:
                return output['type']
    return 'json'


def normalize_model_spec(spec: Dict[str, Any], source_file: str) -> Optional[Dict[str, Any]]:
    """Normalize model specification to standard format."""
    model_id = (
        spec.get('model_id') or 
        spec.get('id') or 
        spec.get('name') or 
        spec.get('model') or
        extract_model_id_from_path(Path(source_file))
    )
    
    if not model_id:
        logger.warning(f"No model_id found in {source_file}")
        return None
    
    category = spec.get('category') or spec.get('type') or spec.get('model_type') or 'other'
    input_schema = extract_input_schema(spec)
    output_type = extract_output_type(spec)
    example_payload = spec.get('example') or spec.get('example_request') or spec.get('payload') or spec.get('sample') or {}
    
    normalized = {
        'model_id': str(model_id),
        'category': str(category),
        'input_schema': input_schema,
        'output_type': output_type,
        'example_payload': example_payload if example_payload else {},
        'source_file': source_file,
        'metadata': {
            'endpoint': spec.get('endpoint', ''),
            'method': spec.get('method', 'POST'),
            'base_url': spec.get('base_url', ''),
        }
    }
    
    return normalized


def collect_source_of_truth(output_file: str = "models/kie_models_source_of_truth.json") -> Dict[str, Any]:
    """Collect all model specifications into source of truth."""
    logger.info("Starting source of truth collection...")
    
    spec_files = find_model_specs()
    models = []
    processed_files = []
    
    for spec_file in spec_files:
        logger.info(f"Processing {spec_file}")
        processed_files.append(str(spec_file))
        
        if spec_file.suffix in ['.yaml', '.yml']:
            data = parse_yaml_spec(spec_file)
        elif spec_file.suffix == '.json':
            data = parse_json_spec(spec_file)
        elif spec_file.suffix == '.md':
            data = parse_markdown_spec(spec_file)
        else:
            continue
        
        if not data:
            continue
        
        if isinstance(data, dict) and 'models' in data:
            for model_spec in data['models']:
                if isinstance(model_spec, dict):
                    normalized = normalize_model_spec(model_spec, str(spec_file))
                    if normalized:
                        models.append(normalized)
        elif isinstance(data, dict):
            normalized = normalize_model_spec(data, str(spec_file))
            if normalized:
                models.append(normalized)
        elif isinstance(data, list):
            # Direct list of models
            for model_spec in data:
                if isinstance(model_spec, dict):
                    normalized = normalize_model_spec(model_spec, str(spec_file))
                    if normalized:
                        models.append(normalized)
    
    # Remove duplicates
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
        'total_models': len(unique_models),
        'source_files': processed_files,
        'models': unique_models
    }
    
    os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Source of truth saved: {output_file} ({len(unique_models)} models)")
    return result


if __name__ == "__main__":
    result = collect_source_of_truth()
    print(f"\n[OK] Collected {result['total_models']} models")
    print(f"[OK] Saved to: models/kie_models_source_of_truth.json")

