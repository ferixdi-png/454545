"""
Smoke test: проверка работоспособности TOP-5 cheapest моделей с реальным Kie.ai API.

ЦЕЛИ:
1. Валидация tech_model_id (работают ли они с API)
2. Валидация input_schema (принимает ли API эти параметры)
3. Проверка error handling
4. Проверка статусов генерации

БЮДЖЕТ: ~6₽ (TOP-5 cheapest: 0.36₽ + 0.57₽ + 0.71₽ + 2.14₽ + 2.14₽)
"""
import json
import os
import sys
import time
import httpx
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.kie.builder import build_payload, get_model_schema

KIE_API_KEY = os.getenv("KIE_API_KEY")
KIE_BASE_URL = os.getenv("KIE_BASE_URL", "https://api.kie.ai")
SMOKE_TEST_TIMEOUT = 120  # 2 minutes max per model


def load_top5_cheapest() -> List[Dict[str, Any]]:
    """Load TOP-5 cheapest models from registry."""
    registry_path = Path("models/kie_models_final_truth.json")
    
    with open(registry_path) as f:
        data = json.load(f)
    
    models = sorted(
        data['models'], 
        key=lambda m: m.get('pricing', {}).get('rub_per_use', 999999)
    )[:5]
    
    return models


def prepare_test_payload(model: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Prepare minimal valid payload for smoke test.
    
    Uses minimal required parameters + safe defaults for optional.
    """
    model_id = model['model_id']
    schema = model.get('input_schema', {})
    required = schema.get('required', [])
    optional = schema.get('optional', [])
    properties = schema.get('properties', {})
    
    # Build test inputs
    user_inputs = {}
    
    # Handle required parameters
    for param in required:
        prop = properties.get(param, {})
        param_type = prop.get('type', 'string')
        
        if param == 'prompt':
            user_inputs['prompt'] = "test image, simple, minimal"
        elif param == 'image':
            # Use a small test image URL
            user_inputs['image'] = "https://picsum.photos/200"
        elif param_type == 'string':
            user_inputs[param] = "test"
        elif param_type == 'number' or param_type == 'integer':
            user_inputs[param] = 1
        elif param_type == 'boolean':
            user_inputs[param] = True
        else:
            print(f"   ⚠️  Unknown required param type: {param} ({param_type})")
            return None
    
    # Add safe optional parameters
    for param in optional:
        prop = properties.get(param, {})
        param_type = prop.get('type', 'string')
        
        # Skip optional params that might cause issues
        if param in ['negative_prompt', 'seed', 'num_outputs']:
            continue
        
        # Add width/height if available (use small values)
        if param == 'width':
            user_inputs['width'] = 512
        elif param == 'height':
            user_inputs['height'] = 512
    
    # Build payload using builder
    try:
        payload = build_payload(model_id, user_inputs)
        return payload
    except Exception as e:
        print(f"   ❌ Failed to build payload: {e}")
        return None


def create_task(payload: Dict[str, Any]) -> Optional[str]:
    """Create task via Kie.ai API."""
    if not KIE_API_KEY or KIE_API_KEY == "test-key":
        print("   ⚠️  Skipping API call (no valid API key)")
        return None
    
    url = f"{KIE_BASE_URL}/api/v1/jobs/createTask"
    headers = {
        "Authorization": f"Bearer {KIE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                request_id = data.get('data', {}).get('requestId')
                return request_id
            else:
                print(f"   ❌ API error {response.status_code}: {response.text[:200]}")
                return None
                
    except Exception as e:
        print(f"   ❌ Request failed: {e}")
        return None


def check_task_status(request_id: str, timeout: int = 60) -> Dict[str, Any]:
    """Poll task status until completion or timeout."""
    if not KIE_API_KEY or KIE_API_KEY == "test-key":
        return {"status": "skipped", "reason": "no API key"}
    
    url = f"{KIE_BASE_URL}/api/v1/jobs/getResult"
    headers = {
        "Authorization": f"Bearer {KIE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"requestId": request_id}
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, json=payload, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get('data', {}).get('status')
                    
                    if status == 'SUCCESS':
                        return {
                            "status": "success",
                            "data": data.get('data', {})
                        }
                    elif status in ['FAILED', 'REJECTED']:
                        return {
                            "status": "failed",
                            "error": data.get('data', {}).get('failReason', 'Unknown error')
                        }
                    elif status in ['PROCESSING', 'PENDING']:
                        print(f"   ⏳ Status: {status}...", end='\r')
                        time.sleep(3)
                        continue
                    else:
                        print(f"   ⚠️  Unknown status: {status}")
                        time.sleep(3)
                        continue
                else:
                    return {
                        "status": "error",
                        "error": f"HTTP {response.status_code}: {response.text[:100]}"
                    }
                    
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    return {"status": "timeout", "error": f"Exceeded {timeout}s timeout"}


def smoke_test_model(model: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    """
    Run smoke test on single model.
    
    Returns:
        {
            "model_id": str,
            "success": bool,
            "stage": str,  # "payload", "create", "status", "complete"
            "error": Optional[str],
            "request_id": Optional[str],
            "duration": float
        }
    """
    model_id = model['model_id']
    display_name = model.get('display_name', model_id)
    price = model.get('pricing', {}).get('rub_per_use', 0)
    
    print(f"\n🧪 Testing: {display_name}")
    print(f"   Model ID: {model_id}")
    print(f"   Price: {price} ₽")
    
    result = {
        "model_id": model_id,
        "display_name": display_name,
        "price": price,
        "success": False,
        "stage": "init",
        "error": None,
        "request_id": None,
        "duration": 0.0
    }
    
    start_time = time.time()
    
    # Stage 1: Build payload
    print("   📝 Building payload...")
    payload = prepare_test_payload(model)
    
    if not payload:
        result['stage'] = 'payload'
        result['error'] = 'Failed to build payload'
        return result
    
    print(f"   ✅ Payload built: {len(payload)} fields")
    result['stage'] = 'payload'
    
    if dry_run:
        print("   ⏭️  DRY RUN - skipping API call")
        result['success'] = True
        result['stage'] = 'dry_run'
        result['duration'] = time.time() - start_time
        return result
    
    # Stage 2: Create task
    print("   🚀 Creating task...")
    request_id = create_task(payload)
    
    if not request_id:
        result['stage'] = 'create'
        result['error'] = 'Failed to create task'
        result['duration'] = time.time() - start_time
        return result
    
    print(f"   ✅ Task created: {request_id}")
    result['request_id'] = request_id
    result['stage'] = 'create'
    
    # Stage 3: Check status
    print("   ⏳ Waiting for completion...")
    status_result = check_task_status(request_id, timeout=SMOKE_TEST_TIMEOUT)
    
    result['duration'] = time.time() - start_time
    
    if status_result['status'] == 'success':
        print(f"   ✅ COMPLETED in {result['duration']:.1f}s")
        result['success'] = True
        result['stage'] = 'complete'
    elif status_result['status'] == 'failed':
        print(f"   ❌ FAILED: {status_result['error']}")
        result['stage'] = 'status'
        result['error'] = status_result['error']
    elif status_result['status'] == 'timeout':
        print(f"   ⏱️  TIMEOUT after {result['duration']:.1f}s")
        result['stage'] = 'status'
        result['error'] = status_result['error']
    else:
        print(f"   ❌ ERROR: {status_result.get('error', 'Unknown')}")
        result['stage'] = 'status'
        result['error'] = status_result.get('error', 'Unknown error')
    
    return result


def main():
    """Run smoke test suite."""
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║          SMOKE TEST: TOP-5 CHEAPEST MODELS                    ║")
    print("║          Testing with REAL Kie.ai API                         ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    
    # Check API key
    if not KIE_API_KEY or KIE_API_KEY == "test-key":
        print("\n⚠️  WARNING: No valid KIE_API_KEY found")
        print("Running in DRY RUN mode (payload validation only)")
        dry_run = True
    else:
        print(f"\n✅ API Key configured: {KIE_API_KEY[:10]}...{KIE_API_KEY[-4:]}")
        dry_run = False
    
    # Load models
    print("\n📦 Loading TOP-5 cheapest models...")
    models = load_top5_cheapest()
    
    total_cost = sum(m.get('pricing', {}).get('rub_per_use', 0) for m in models)
    print(f"   Models: {len(models)}")
    print(f"   Estimated cost: {total_cost:.2f} ₽")
    
    # Run tests
    results = []
    
    for model in models:
        result = smoke_test_model(model, dry_run=dry_run)
        results.append(result)
        
        # Small delay between tests
        if not dry_run:
            time.sleep(2)
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 SMOKE TEST RESULTS")
    print("=" * 70)
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"\n✅ Successful: {len(successful)}/{len(results)}")
    for r in successful:
        print(f"   - {r['display_name']} ({r['duration']:.1f}s)")
    
    if failed:
        print(f"\n❌ Failed: {len(failed)}/{len(results)}")
        for r in failed:
            print(f"   - {r['display_name']}")
            print(f"     Stage: {r['stage']}")
            print(f"     Error: {r.get('error', 'Unknown')}")
    
    # Save results
    output_path = Path("artifacts/smoke_test_results.json")
    output_path.parent.mkdir(exist_ok=True)
    
    output = {
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "total_models": len(results),
        "successful": len(successful),
        "failed": len(failed),
        "total_cost": sum(r['price'] for r in results if r['success']),
        "results": results
    }
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved: {output_path}")
    
    # Exit code
    if len(successful) == len(results):
        print("\n✅ ALL TESTS PASSED")
        return 0
    elif len(successful) > 0:
        print(f"\n⚠️  PARTIAL SUCCESS: {len(successful)}/{len(results)} passed")
        return 1
    else:
        print("\n❌ ALL TESTS FAILED")
        return 2


if __name__ == "__main__":
    sys.exit(main())
