#!/usr/bin/env python3
"""
Model Page Extractor - извлекает параметры модели со страницы

Для каждой модели извлекает:
- model_id (tech id для API)
- display_name
- category/modality
- input_schema (все параметры)
- pricing rules
- output type
"""
import httpx
import logging
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from .discover import _fetch_url

logger = logging.getLogger(__name__)


def extract_model_id_from_page(html: str, url: str) -> Optional[str]:
    """
    Extract technical model_id from page.
    
    Tries multiple strategies:
    1. From API example payload
    2. From URL path
    3. From page meta tags
    """
    # Strategy 1: Look for "model": "..." in API examples
    model_pattern = r'"model"\s*:\s*"([^"]+)"'
    matches = re.findall(model_pattern, html)
    if matches:
        # Return most common match
        from collections import Counter
        most_common = Counter(matches).most_common(1)[0][0]
        logger.info(f"  Found model ID in payload: {most_common}")
        return most_common
    
    # Strategy 2: From URL
    path = url.split('/')[-1]
    if path and not path.endswith('.html'):
        logger.info(f"  Using model ID from URL: {path}")
        return path
    
    return None


def extract_pricing(html: str) -> Dict[str, Any]:
    """
    Extract pricing information from page.
    
    Returns:
        {
            'credits_per_run': float or None,
            'usd_per_run': float or None,
            'pricing_note': str (if variable pricing)
        }
    """
    pricing = {
        'credits_per_run': None,
        'usd_per_run': None,
        'pricing_note': None
    }
    
    # Look for pricing in text
    # Pattern: "0.8 Kie credits" or "$0.004"
    credits_pattern = r'([\d.]+)\s*(?:Kie\s*)?credits?'
    usd_pattern = r'\$([\d.]+)'
    
    credits_matches = re.findall(credits_pattern, html, re.IGNORECASE)
    usd_matches = re.findall(usd_pattern, html)
    
    if credits_matches:
        try:
            pricing['credits_per_run'] = float(credits_matches[0])
        except ValueError:
            pass
    
    if usd_matches:
        try:
            pricing['usd_per_run'] = float(usd_matches[0])
        except ValueError:
            pass
    
    # Check for variable pricing
    if 'pricing depends' in html.lower() or 'varies by' in html.lower():
        pricing['pricing_note'] = "Variable pricing - depends on parameters"
    
    return pricing


def extract_input_schema(html: str) -> Dict[str, Any]:
    """
    Extract input parameters schema from page.
    
    Returns:
        JSON Schema compatible dict
    """
    schema = {
        "type": "object",
        "required": [],
        "properties": {}
    }
    
    # Look for common input fields
    common_fields = {
        'prompt': {
            'type': 'string',
            'description': 'Text description',
            'max_length': 1000
        },
        'aspect_ratio': {
            'type': 'string',
            'enum': ['1:1', '4:3', '3:4', '16:9', '9:16'],
            'description': 'Aspect ratio'
        },
        'duration': {
            'type': 'string',
            'enum': ['5.0s', '10.0s', '15.0s'],
            'description': 'Video duration'
        },
        'resolution': {
            'type': 'string',
            'enum': ['480p', '720p', '1080p'],
            'description': 'Output resolution'
        },
    }
    
    # Detect which fields are present
    for field_name, field_schema in common_fields.items():
        if field_name in html.lower():
            schema['properties'][field_name] = field_schema
            
            # Check if required
            if 'required' in html.lower() and field_name in html.lower():
                schema['required'].append(field_name)
    
    # Always require prompt if it exists
    if 'prompt' in schema['properties'] and 'prompt' not in schema['required']:
        schema['required'].append('prompt')
    
    return schema


def extract_model_page(url: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """
    Extract full model information from page.
    
    Args:
        url: Model page URL
        use_cache: Use cached HTML
    
    Returns:
        Model dict or None on error
    """
    logger.info(f"\nExtracting model from: {url}")
    
    html = _fetch_url(url, use_cache=use_cache)
    if not html:
        logger.error(f"  ❌ Failed to fetch {url}")
        return None
    
    # Extract components
    model_id = extract_model_id_from_page(html, url)
    if not model_id:
        logger.warning(f"  ⚠️ Could not determine model_id for {url}")
        return None
    
    pricing = extract_pricing(html)
    input_schema = extract_input_schema(html)
    
    # Determine category from content
    category = "other"
    if 'text-to-image' in html.lower() or 'text → image' in html.lower():
        category = "text-to-image"
    elif 'text-to-video' in html.lower() or 'text → video' in html.lower():
        category = "text-to-video"
    elif 'image-to-video' in html.lower():
        category = "image-to-video"
    elif 'image-to-image' in html.lower():
        category = "image-to-image"
    elif 'text-to-speech' in html.lower() or 'tts' in html.lower():
        category = "text-to-speech"
    elif 'upscale' in html.lower() or 'enhance' in html.lower():
        category = "upscale"
    
    # Build model dict
    model = {
        'model_id': model_id,
        'display_name': model_id.replace('-', ' ').title(),
        'url': url,
        'category': category,
        'pricing': pricing,
        'input_schema': input_schema,
        'enabled': True,
        'verified': False,  # Will be set by validator
        'source': 'page_extraction'
    }
    
    logger.info(f"  ✅ Extracted: {model_id} ({category})")
    logger.info(f"     Pricing: {pricing}")
    logger.info(f"     Inputs: {list(input_schema.get('properties', {}).keys())}")
    
    return model


def extract_all_models(models_index: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Extract detailed info for all models in index.
    
    Args:
        models_index: List from discover.py
    
    Returns:
        List of full model dicts
    """
    extracted = []
    
    logger.info(f"\n{'='*60}")
    logger.info(f"EXTRACTING {len(models_index)} MODELS")
    logger.info(f"{'='*60}\n")
    
    for i, model_info in enumerate(models_index, 1):
        logger.info(f"[{i}/{len(models_index)}] {model_info['model_id']}")
        
        try:
            model = extract_model_page(model_info['url'])
            if model:
                extracted.append(model)
        except Exception as e:
            logger.error(f"  ❌ Error: {e}")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"EXTRACTED: {len(extracted)}/{len(models_index)} models")
    logger.info(f"{'='*60}\n")
    
    return extracted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test on z-image
    model = extract_model_page("https://kie.ai/z-image")
    if model:
        print(json.dumps(model, indent=2))
