#!/usr/bin/env python3
"""
Comprehensive Model Testing Script
Tests ALL models in SOURCE_OF_TRUTH starting from cheapest
Skips already tested models from previous runs
"""
import json
import os
import sys
import time
import httpx
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Set

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Constants
SOURCE_OF_TRUTH_PATH = Path("models/KIE_SOURCE_OF_TRUTH.json")
RESULTS_PATH = Path("artifacts/comprehensive_test_results.json")
TESTED_MODELS_PATH = Path("artifacts/tested_models_history.json")
KIE_API_KEY = os.getenv("KIE_API_KEY", "4d49a621bc589222a2769978cb725495")
MAX_COST_PER_RUN = 50.0  # Maximum RUB to spend per run
WAIT_BETWEEN_TESTS = 2  # seconds

def load_source_of_truth() -> Dict[str, Any]:
    """Load SOURCE_OF_TRUTH"""
    with open(SOURCE_OF_TRUTH_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_tested_models() -> Set[str]:
    """Load history of successfully tested models"""
    if not TESTED_MODELS_PATH.exists():
        return set()
    
    try:
        with open(TESTED_MODELS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return set(data.get('successful_models', []))
    except:
        return set()

def save_tested_model(model_id: str):
    """Add model to tested history"""
    tested = load_tested_models()
    tested.add(model_id)
    
    TESTED_MODELS_PATH.parent.mkdir(exist_ok=True)
    with open(TESTED_MODELS_PATH, 'w', encoding='utf-8') as f:
        json.dump({
            'successful_models': sorted(list(tested)),
            'last_updated': datetime.utcnow().isoformat()
        }, f, indent=2, ensure_ascii=False)

def get_models_to_test(sot: Dict[str, Any], already_tested: Set[str]) -> List[Dict[str, Any]]:
    """Get models sorted by price, excluding already tested"""
    models = sot.get('models', {})
    
    # Filter enabled models with prices
    testable = []
    for model_id, model in models.items():
        if not model.get('enabled', True):
            continue
        
        price = model.get('pricing', {}).get('rub_per_gen')
        if price is None:
            continue
        
        # Skip if already successfully tested
        if model_id in already_tested:
            continue
        
        testable.append({
            'model_id': model_id,
            'display_name': model.get('display_name', model_id),
            'price': price,
            'category': model.get('category', 'unknown'),
            'endpoint': model.get('endpoint', ''),
            'input_schema': model.get('input_schema', {})
        })
    
    # Sort by price (cheapest first)
    testable.sort(key=lambda m: m['price'])
    return testable

def build_test_payload(model: Dict[str, Any]) -> Dict[str, Any]:
    """Build minimal valid test payload from model's input_schema examples"""
    schema = model.get('input_schema', {})
    
    # Extract example input from schema
    # Schema structure: {"model": {...}, "callBackUrl": {...}, "input": {"type": "dict", "examples": [...]}}
    input_field = schema.get('input', {})
    examples = input_field.get('examples', [])
    
    if examples and isinstance(examples[0], dict):
        # Use first example as template - it has all required fields
        example_input = examples[0].copy()
        
        # Replace with minimal test values
        if 'prompt' in example_input:
            # Replace empty or use "test" if too long
            if not example_input['prompt'] or len(example_input['prompt']) > 50:
                example_input['prompt'] = "test"
        
        # Fix common empty fields with valid test data
        if 'text' in example_input and not example_input['text']:
            example_input['text'] = "test sound effect"
        
        if 'image_url' in example_input and not example_input['image_url']:
            example_input['image_url'] = "https://picsum.photos/512/512"
        
        if 'imageUrl' in example_input and not example_input['imageUrl']:
            example_input['imageUrl'] = "https://picsum.photos/512/512"
        
        if 'image' in example_input and not example_input['image']:
            example_input['image'] = "https://picsum.photos/512/512"
        
        if 'audio_url' in example_input and not example_input['audio_url']:
            example_input['audio_url'] = "https://file.aiquickdraw.com/custom-page/akr/section-images/1756964657418ljw1jbzr.mp3"
        
        if 'video_url' in example_input and not example_input['video_url']:
            example_input['video_url'] = "https://example.com/test.mp4"
        
        payload = {
            "model": model['model_id'],
            "input": example_input
        }
        return payload
    
    # Fallback: build from scratch (shouldn't happen with proper SOT)
    return {
        "model": model['model_id'],
        "input": {"prompt": "test"}
    }

def test_model(model: Dict[str, Any]) -> Dict[str, Any]:
    """Test single model via KIE API"""
    result = {
        'model_id': model['model_id'],
        'display_name': model['display_name'],
        'price': model['price'],
        'category': model['category'],
        'success': False,
        'error': None,
        'task_id': None,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    try:
        # Build payload
        payload = build_test_payload(model)
        endpoint = model.get('endpoint') or "/api/v1/jobs/createTask"
        
        # Make API request
        headers = {
            "Authorization": f"Bearer {KIE_API_KEY}",
            "Content-Type": "application/json"
        }
        
        with httpx.Client(timeout=30) as client:
            url = f"https://api.kie.ai{endpoint}"
            resp = client.post(url, headers=headers, json=payload)
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get('code') == 200:
                    task_id = data.get('data', {}).get('taskId')
                    result['success'] = True
                    result['task_id'] = task_id
                else:
                    result['error'] = f"API error: {data.get('msg', 'Unknown')}"
            else:
                result['error'] = f"HTTP {resp.status_code}: {resp.text[:200]}"
    
    except Exception as e:
        result['error'] = f"Exception: {str(e)}"
    
    return result

def main():
    """Main testing loop"""
    print("🧪 Comprehensive Model Testing")
    print("=" * 60)
    
    # Load data
    sot = load_source_of_truth()
    already_tested = load_tested_models()
    
    print(f"✅ SOURCE_OF_TRUTH loaded: {len(sot.get('models', {}))} models")
    print(f"✅ Already tested: {len(already_tested)} models")
    
    # Get models to test
    models_to_test = get_models_to_test(sot, already_tested)
    print(f"📋 Models to test: {len(models_to_test)}")
    
    if not models_to_test:
        print("✅ All models already tested!")
        return
    
    # Calculate budget
    total_cost_estimate = sum(m['price'] for m in models_to_test)
    print(f"💰 Estimated total cost: {total_cost_estimate:.2f} RUB")
    print(f"💰 Budget limit: {MAX_COST_PER_RUN:.2f} RUB")
    print()
    
    # Test models
    results = []
    total_cost = 0.0
    successful = 0
    failed = 0
    
    for i, model in enumerate(models_to_test, 1):
        # Check budget
        if total_cost + model['price'] > MAX_COST_PER_RUN:
            print(f"⚠️ Budget limit reached ({MAX_COST_PER_RUN} RUB). Stopping.")
            break
        
        print(f"\n[{i}/{len(models_to_test)}] Testing: {model['display_name']}")
        print(f"  Model ID: {model['model_id']}")
        print(f"  Price: {model['price']:.2f} RUB")
        print(f"  Category: {model['category']}")
        
        # Run test
        result = test_model(model)
        results.append(result)
        
        if result['success']:
            print(f"  ✅ SUCCESS - Task ID: {result['task_id']}")
            successful += 1
            total_cost += model['price']
            save_tested_model(model['model_id'])
        else:
            print(f"  ❌ FAILED - {result['error']}")
            failed += 1
        
        # Wait between tests
        if i < len(models_to_test):
            time.sleep(WAIT_BETWEEN_TESTS)
    
    # Save results
    RESULTS_PATH.parent.mkdir(exist_ok=True)
    with open(RESULTS_PATH, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.utcnow().isoformat(),
            'total_tested': len(results),
            'successful': successful,
            'failed': failed,
            'total_cost': total_cost,
            'results': results
        }, f, indent=2, ensure_ascii=False)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"💰 Total cost: {total_cost:.2f} RUB")
    print(f"📁 Results saved to: {RESULTS_PATH}")
    print(f"📁 History saved to: {TESTED_MODELS_PATH}")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
