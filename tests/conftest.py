"""Pytest configuration for test path setup."""
import sys
import os
import pytest

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


@pytest.fixture
def source_of_truth_models_as_list():
    """
    Load SOURCE_OF_TRUTH and convert models dict to list for backward compatibility.
    
    New format (v1.2.10): {"models": {model_id: {...}}}
    Old format (tests expect): {"models": [{model_id: ..., ...}]}
    """
    from app.kie.builder import load_source_of_truth
    
    sot = load_source_of_truth()
    models = sot.get('models', {})
    
    # Convert dict to list
    if isinstance(models, dict):
        models_list = []
        for model_id, model_data in models.items():
            model_copy = model_data.copy()
            if 'model_id' not in model_copy:
                model_copy['model_id'] = model_id
            models_list.append(model_copy)
        sot['models'] = models_list
    
    return sot

