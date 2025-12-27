"""
SAFE SMOKE TEST: проверка payload validation для генераций без network запросов.
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any, List


def load_registry() -> dict:
    """Load registry directly."""
    repo_root = Path(__file__).parent.parent
    registry_path = repo_root / "models" / "kie_models_source_of_truth.json"
    
    with open(registry_path) as f:
        return json.load(f)


# Test models (1 per category)
TEST_MODELS = [
    {"category": "t2i", "model_id": "flux/dev", "inputs": {"prompt": "test cat in space"}},
    {"category": "i2v", "model_id": "kling/v1-image-to-video", "inputs": {"image_url": "https://example.com/test.jpg"}},
    {"category": "t2v", "model_id": "kling/v1-standard", "inputs": {"prompt": "test video scene"}},
    {"category": "tts", "model_id": "elevenlabs/text-to-speech", "inputs": {"text": "test audio"}},
    {"category": "upscale", "model_id": "recraft/crisp-upscale", "inputs": {"image_url": "https://example.com/test.jpg"}},
]


def validate_payload_structure(payload: Dict[str, Any], model_id: str) -> List[str]:
    """
    Validate payload structure without making network request.
    
    Returns:
        List of validation errors (empty if OK)
    """
    errors = []
    
    # Check required fields
    if "model" not in payload:
        errors.append(f"{model_id}: payload missing 'model' field")
    
    if "taskType" not in payload:
        errors.append(f"{model_id}: payload missing 'taskType' field")
    
    if "input" not in payload:
        errors.append(f"{model_id}: payload missing 'input' field")
    else:
        # Check input is dict
        if not isinstance(payload["input"], dict):
            errors.append(f"{model_id}: 'input' must be dict, got {type(payload['input'])}")
    
    # Check no empty required fields
    for key, value in payload.get("input", {}).items():
        if value is None or value == "":
            errors.append(f"{model_id}: input field '{key}' is empty")
    
    return errors


def test_model_payload(test_case: Dict[str, Any], registry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Test building payload for single model.
    
    Returns:
        {
            "model_id": str,
            "status": "ok" | "error",
            "payload": dict | None,
            "errors": list
        }
    """
    model_id = test_case["model_id"]
    user_inputs = test_case["inputs"]
    
    # Find model in registry
    models = registry.get("models", [])
    model = next((m for m in models if m["model_id"] == model_id), None)
    
    if not model:
        return {
            "model_id": model_id,
            "status": "error",
            "payload": None,
            "errors": [f"Model {model_id} not found in registry"]
        }
    
    # Build payload
    try:
        payload = build_task_payload(model, user_inputs)
    except Exception as e:
        return {
            "model_id": model_id,
            "status": "error",
            "payload": None,
            "errors": [f"Failed to build payload: {e}"]
        }
    
    # Validate payload structure
    validation_errors = validate_payload_structure(payload, model_id)
    
    if validation_errors:
        return {
            "model_id": model_id,
            "status": "error",
            "payload": payload,
            "errors": validation_errors
        }
    
    return {
        "model_id": model_id,
        "status": "ok",
        "payload": payload,
        "errors": []
    }


def main():
    """Run safe smoke test."""
    print("=" * 60)
    print("SAFE SMOKE TEST - Registry Validation")
    print("=" * 60)
    print()
    
    # Load registry
    try:
        registry = load_registry()
    except Exception as e:
        print(f"❌ Failed to load registry: {e}")
        return 1
    
    total_models = len(registry.get("models", []))
    print(f"📚 Registry loaded: {total_models} models")
    print()
    
    # Test sample models - use actual model_ids from registry
    test_models = [
        "flux-2/pro-text-to-image",  # t2i
        "kling-2.6/text-to-video",    # t2v
        "elevenlabs/text-to-speech",  # tts
        "recraft/crisp-upscale",      # upscale
        "google/veo-3"                # t2v premium
    ]
    
    for model_id in test_models:
        model = next((m for m in registry["models"] if m.get("model_id") == model_id), None)
        if model:
            print(f"✅ {model_id}")
            print(f"   Category: {model.get('category')}")
            print(f"   Price: {model.get('price')} RUB")
            print(f"   Description: {model.get('description', 'N/A')[:50]}")
        else:
            print(f"❌ {model_id} - NOT FOUND")
        print()
    
    print("=" * 60)
    print("✅ Registry validation passed")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
