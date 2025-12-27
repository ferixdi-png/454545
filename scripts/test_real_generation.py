"""
REAL PRODUCTION TEST: Test actual generation on cheapest models.

CRITICAL: If ANY model fails, it indicates a GLOBAL PROBLEM
that may affect other models too.

MASTER PROMPT compliance:
- Test real API calls
- Verify parameter passing
- Check generation flow
- Ensure proper error handling
"""

import os
import sys
import asyncio
import json
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.kie.generator import KieGenerator
from app.kie.builder import load_source_of_truth


async def test_model(generator: KieGenerator, model_id: str, test_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Test a single model with real API call.
    
    Returns:
        Result dict with success status and details
    """
    print(f"\n{'='*80}")
    print(f"TESTING: {model_id}")
    print(f"{'='*80}")
    print(f"Inputs: {json.dumps(test_inputs, indent=2)}")
    
    try:
        result = await generator.generate(
            model_id=model_id,
            user_inputs=test_inputs,
            progress_callback=None,
            timeout=240  # 4 minutes timeout for complex models
        )
        
        success = result.get('success', False)
        message = result.get('message', 'No message')
        
        if success:
            print(f"✅ SUCCESS")
            print(f"Message: {message}")
            result_urls = result.get('result_urls', [])
            if result_urls:
                print(f"Result URLs: {len(result_urls)} files")
                for url in result_urls[:2]:
                    print(f"  - {url}")
        else:
            print(f"❌ FAILED")
            print(f"Message: {message}")
            error_code = result.get('error_code', 'UNKNOWN')
            error_message = result.get('error_message', 'No details')
            print(f"Error code: {error_code}")
            print(f"Error message: {error_message}")
        
        return {
            'model_id': model_id,
            'success': success,
            'message': message,
            'error_code': result.get('error_code'),
            'error_message': result.get('error_message'),
            'result_urls': result.get('result_urls', [])
        }
        
    except Exception as e:
        print(f"❌ EXCEPTION: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'model_id': model_id,
            'success': False,
            'message': f"Exception: {e}",
            'error_code': 'EXCEPTION',
            'error_message': str(e),
            'result_urls': []
        }


async def main():
    """Run real production tests on cheapest models."""
    
    print("="*80)
    print("REAL PRODUCTION TEST - CHEAPEST MODELS")
    print("="*80)
    
    # Check KIE API key
    kie_api_key = os.getenv("KIE_API_KEY")
    if not kie_api_key:
        print("❌ ERROR: KIE_API_KEY not set in environment")
        print("Please set KIE_API_KEY environment variable")
        return 1
    
    print(f"\n✅ KIE API Key: {kie_api_key[:8]}...{kie_api_key[-4:]}")
    
    # Load free models
    with open('artifacts/free_models.json', 'r') as f:
        free_data = json.load(f)
    
    free_models = free_data.get('models', [])
    print(f"\n📦 Free models to test: {len(free_models)}")
    
    # Load source of truth for input schemas
    registry = load_source_of_truth()
    all_models = registry.get('models', [])
    
    # Create generator
    generator = KieGenerator()
    
    # Define test cases for each model
    test_cases = {
        "elevenlabs/speech-to-text": {
            "audio_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
        },
        "elevenlabs/audio-isolation": {
            "audio_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
        },
        "elevenlabs/text-to-speech": {
            "text": "Hello world, this is a test of text to speech generation."
        },
        "elevenlabs/text-to-speech-multilingual-v2": {
            "text": "Привет мир, это тест генерации речи из текста.",
            "prompt": "Привет мир, это тест генерации речи из текста."  # Try both fields
        },
        "elevenlabs/sound-effect": {
            "prompt": "door opening and closing",
            "text": "door opening and closing"  # Try both fields
        }
    }
    
    # Run tests
    results = []
    
    for model_data in free_models:
        model_id = model_data.get('model_id')
        
        # Get test inputs
        test_inputs = test_cases.get(model_id)
        if not test_inputs:
            print(f"\n⚠️ WARNING: No test case defined for {model_id}")
            continue
        
        # Find model in registry to check schema
        model_info = next((m for m in all_models if m.get('model_id') == model_id), None)
        if model_info:
            schema = model_info.get('input_schema', {})
            required = schema.get('required', [])
            print(f"\nModel schema - Required: {required}")
        
        # Run test
        result = await test_model(generator, model_id, test_inputs)
        results.append(result)
        
        # Add delay between tests to avoid rate limiting
        await asyncio.sleep(2)
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    success_count = sum(1 for r in results if r['success'])
    total_count = len(results)
    
    print(f"\nResults: {success_count}/{total_count} successful")
    print()
    
    for result in results:
        status = "✅" if result['success'] else "❌"
        model_id = result['model_id']
        message = result['message']
        print(f"{status} {model_id}")
        if not result['success']:
            print(f"   Error: {message}")
    
    print()
    
    if success_count == total_count:
        print("🎉 ALL TESTS PASSED!")
        print("✅ All models work correctly")
        print("✅ Parameters are properly passed")
        print("✅ Generation flow is stable")
        return 0
    else:
        print("⚠️ SOME TESTS FAILED")
        print()
        print("CRITICAL: Test failures indicate GLOBAL PROBLEMS:")
        print()
        
        # Analyze failures
        failed = [r for r in results if not r['success']]
        
        # Group by error type
        error_types = {}
        for f in failed:
            error_code = f.get('error_code', 'UNKNOWN')
            if error_code not in error_types:
                error_types[error_code] = []
            error_types[error_code].append(f['model_id'])
        
        print("Error types:")
        for error_code, models in error_types.items():
            print(f"\n{error_code}:")
            for model in models:
                print(f"  - {model}")
        
        print()
        print("ACTION REQUIRED:")
        print("1. Check KIE API integration")
        print("2. Verify input parameter mapping")
        print("3. Review error handling")
        print("4. Fix identified issues")
        
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
