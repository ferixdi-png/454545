"""
API Router для новой архитектуры Kie.ai.
Маршрутизирует запросы к правильным category-specific endpoints.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Загрузка source of truth
def load_v4_source_of_truth() -> Dict[str, Any]:
    """
    Load source of truth with new API architecture.
    
    Tries in order:
    1. models/kie_source_of_truth_v4.json (old name)
    2. models/KIE_SOURCE_OF_TRUTH.json (new canonical name)
    3. Fallback to stub
    """
    # Try old v4 path first (for backwards compatibility)
    v4_path_old = Path(__file__).parent.parent.parent / "models" / "kie_source_of_truth_v4.json"
    if v4_path_old.exists():
        with open(v4_path_old, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # Try new canonical path
    sot_path = Path(__file__).parent.parent.parent / "models" / "KIE_SOURCE_OF_TRUTH.json"
    if sot_path.exists():
        logger.info(f"✅ Using SOURCE_OF_TRUTH (v4 router): {sot_path}")
        with open(sot_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # Fallback to stub
    logger.warning("No source of truth found, using empty stub")
    return {"version": "stub", "models": {}, "categories": {}}


def get_api_category_for_model(model_id: str, source_v4: Optional[Dict] = None) -> Optional[str]:
    """
    Determine which API category a model belongs to.
    
    Args:
        model_id: Model identifier (e.g. 'veo3', 'suno-v4', 'gpt-4o-image')
        source_v4: Optional pre-loaded v4 source of truth
    
    Returns:
        API category name ('veo3', 'suno', 'runway', etc.) or None
    """
    if source_v4 is None:
        source_v4 = load_v4_source_of_truth()
    
    # Handle both dict and list structures
    models = source_v4.get('models', {})
    
    # If models is dict (new format), iterate over values
    if isinstance(models, dict):
        for model_id_key, model in models.items():
            if model.get('model_id') == model_id:
                return model.get('category')  # Use 'category' field from new SOT
    # If models is list (old v4 format), iterate directly
    elif isinstance(models, list):
        for model in models:
            if model.get('model_id') == model_id:
                return model.get('api_category')
    
    logger.warning(f"Model {model_id} not found in source of truth")
    return None


def build_category_payload(
    model_id: str, 
    user_inputs: Dict[str, Any],
    source_v4: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Build payload for category-specific API endpoint.
    
    This is different from old universal createTask - each category
    has its own payload format.
    
    Args:
        model_id: Model ID
        user_inputs: User-provided inputs
        source_v4: Optional pre-loaded v4 source of truth
    
    Returns:
        Payload dict ready for category-specific API
    """
    if source_v4 is None:
        source_v4 = load_v4_source_of_truth()
    
    # Handle both dict and list structures
    models = source_v4.get('models', {})
    
    model_schema = None
    # If models is dict (new format)
    if isinstance(models, dict):
        model_schema = models.get(model_id)
    # If models is list (old v4 format)
    elif isinstance(models, list):
        for model in models:
            if model.get('model_id') == model_id:
                model_schema = model
                break
    
    if not model_schema:
        raise ValueError(f"Model {model_id} not found in source of truth")
    
    category = model_schema.get('category') or model_schema.get('api_category')
    input_schema = model_schema.get('input_schema', {})
    properties = input_schema.get('properties', {})
    required_fields = input_schema.get('required', [])
    
    # Build payload based on category
    # CRITICAL: Always include model field for V4 API
    payload = {'model': model_id}
    
    # Add required fields
    for field in required_fields:
        if field in user_inputs:
            payload[field] = user_inputs[field]
        elif field in properties and 'default' in properties[field]:
            payload[field] = properties[field]['default']
        else:
            raise ValueError(f"Required field '{field}' missing for model {model_id}")
    
    # Add optional fields if provided
    for field, field_schema in properties.items():
        if field not in required_fields and field in user_inputs:
            payload[field] = user_inputs[field]
        elif field not in payload and 'default' in field_schema:
            # Add defaults for optional fields
            payload[field] = field_schema['default']
    
    logger.info(f"Built {category} payload for {model_id}: {payload}")
    return payload


def get_api_endpoint_for_model(model_id: str, source_v4: Optional[Dict] = None) -> str:
    """
    Get the full API endpoint path for a model.
    
    Args:
        model_id: Model ID
        source_v4: Optional pre-loaded v4 source of truth
    
    Returns:
        Full endpoint path (e.g. '/api/v1/jobs/createTask')
    """
    if source_v4 is None:
        source_v4 = load_v4_source_of_truth()
    
    # Handle both dict and list structures
    models = source_v4.get('models', {})
    
    # If models is dict (new format)
    if isinstance(models, dict):
        model = models.get(model_id)
        if model:
            return model.get('endpoint', '/api/v1/jobs/createTask')
    # If models is list (old v4 format)
    elif isinstance(models, list):
        for model in models:
            if model.get('model_id') == model_id:
                return model.get('api_endpoint', '/api/v1/jobs/createTask')
    
    # Fallback to default endpoint
    logger.warning(f"Model {model_id} not found, using default endpoint")
    return '/api/v1/jobs/createTask'


def get_base_url_for_category(category: str, source_v4: Optional[Dict] = None) -> str:
    """
    Get base URL for API category.
    
    Args:
        category: API category ('veo3', 'suno', etc.)
        source_v4: Optional pre-loaded v4 source of truth
    
    Returns:
        Base URL (typically 'https://api.kie.ai')
    """
    if source_v4 is None:
        source_v4 = load_v4_source_of_truth()
    
    categories = source_v4.get('categories', {})
    if category in categories:
        return categories[category].get('base_url', 'https://api.kie.ai')
    
    # Fallback
    return 'https://api.kie.ai'


# Compatibility helpers для старого кода
def is_v4_model(model_id: str) -> bool:
    """Check if model exists in v4 source of truth."""
    try:
        source_v4 = load_v4_source_of_truth()
        models = source_v4.get('models', {})
        # models is dict, not list
        return model_id in models
    except Exception as e:
        logger.error(f"Failed to check v4 model: {e}")
        return False


def get_all_v4_models() -> list:
    """Get list of all available v4 models."""
    try:
        source_v4 = load_v4_source_of_truth()
        models = source_v4.get('models', {})
        # models is dict - return list of model objects
        return list(models.values())
    except Exception as e:
        logger.error(f"Failed to load v4 models: {e}")
        return []
