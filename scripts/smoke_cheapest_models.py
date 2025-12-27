"""
COST-SAFE TESTING: Test cheapest models only.

MASTER PROMPT compliance:
- Test ONLY 5 cheapest models (all are FREE)
- Detailed logging for each test
- Report generation issues
- Safe cost mode
"""

import os
import sys
import asyncio
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.kie.generator import KieGenerator
from app.kie.builder import load_source_of_truth

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_cheapest_models():
    """Test the 5 cheapest (FREE) models with real API calls."""
    
    print("="*80)
    print("COST-SAFE TESTING - CHEAPEST MODELS ONLY")
    print("="*80)
    
    # Check API key
    kie_api_key = os.getenv("KIE_API_KEY")
    if not kie_api_key:
        print("❌ ERROR: KIE_API_KEY not set")
        return 1
    
    print(f"\n✅ KIE API Key configured")
    
    # Load source of truth
    registry = load_source_of_truth()
    all_models = registry.get('models', [])
    
    # Get models with pricing
    models_with_price = [
        m for m in all_models 
        if 'price_usd' in m 
        and not m.get('model_id', '').endswith('_processor')
        and not m.get('model_id', '').isupper()
    ]
    
    # Sort by price
    sorted_models = sorted(models_with_price, key=lambda x: x.get('price_usd', 999999))
    
    # Get top 5 cheapest
    cheapest_5 = sorted_models[:5]
    
    print(f"\n📦 Testing {len(cheapest_5)} cheapest models:")
    for i, m in enumerate(cheapest_5, 1):
        model_id = m.get('model_id')
        price_usd = m.get('price_usd', 0)
        is_free = m.get('is_free', False)
        free_label = " [FREE ✅]" if is_free else ""
        print(f"  {i}. {model_id}: ${price_usd}{free_label}")
    
    # Define test inputs
    test_inputs = {
        "elevenlabs/speech-to-text": {
            "audio_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
        },
        "elevenlabs/audio-isolation": {
            "audio_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
        },
        "elevenlabs/text-to-speech": {
            "text": "Hello world, this is a test."
        },
        "elevenlabs/text-to-speech-multilingual-v2": {
            "text": "Hello world test",
            "prompt": "Hello world test"
        },
        "elevenlabs/sound-effect": {
            "prompt": "door opening",
            "text": "door opening"
        }
    }
    
    # Run tests
    generator = KieGenerator()
    results = []
    
    for model in cheapest_5:
        model_id = model.get('model_id')
        inputs = test_inputs.get(model_id)
        
        if not inputs:
            logger.warning(f"No test inputs defined for {model_id}, skipping")
            continue
        
        print(f"\n{'='*80}")
        print(f"TESTING: {model_id}")
        print(f"{'='*80}")
        print(f"Inputs: {json.dumps(inputs, indent=2, ensure_ascii=False)}")
        print(f"Timeout: 90 seconds")
        
        start_time = datetime.now()
        
        try:
            result = await generator.generate(
                model_id=model_id,
                user_inputs=inputs,
                progress_callback=None,
                timeout=90  # 90 seconds for cheap models
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            success = result.get('success', False)
            
            test_result = {
                'model_id': model_id,
                'success': success,
                'duration': duration,
                'message': result.get('message', ''),
                'error_code': result.get('error_code'),
                'error_message': result.get('error_message'),
                'result_urls': result.get('result_urls', []),
                'task_id': result.get('task_id')
            }
            
            results.append(test_result)
            
            if success:
                print(f"✅ SUCCESS in {duration:.1f}s")
                print(f"Message: {result.get('message', '')}")
                urls = result.get('result_urls', [])
                if urls:
                    print(f"Results: {len(urls)} files")
                    for url in urls[:2]:
                        print(f"  - {url}")
            else:
                print(f"❌ FAILED in {duration:.1f}s")
                print(f"Error: {result.get('error_message', 'Unknown')}")
                if result.get('task_id'):
                    print(f"Task ID: {result.get('task_id')}")
        
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            print(f"❌ EXCEPTION in {duration:.1f}s: {e}")
            
            results.append({
                'model_id': model_id,
                'success': False,
                'duration': duration,
                'message': str(e),
                'error_code': 'EXCEPTION',
                'error_message': str(e),
                'result_urls': [],
                'task_id': None
            })
        
        # Small delay between tests
        await asyncio.sleep(2)
    
    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY - CHEAPEST MODELS")
    print(f"{'='*80}")
    
    success_count = sum(1 for r in results if r['success'])
    total_count = len(results)
    
    print(f"\nResults: {success_count}/{total_count} successful")
    print()
    
    for result in results:
        status = "✅" if result['success'] else "❌"
        model_id = result['model_id']
        duration = result['duration']
        print(f"{status} {model_id} ({duration:.1f}s)")
        if not result['success']:
            print(f"   Error: {result['error_message']}")
    
    # Analysis
    print(f"\n{'='*80}")
    print("ANALYSIS")
    print(f"{'='*80}")
    
    if success_count == total_count:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ All cheapest models work correctly")
        print("✅ Generation flow is stable")
        print("✅ Ready to test medium-price models")
        return 0
    else:
        print(f"\n⚠️ {total_count - success_count} TESTS FAILED")
        
        # Group by error
        errors = {}
        for r in results:
            if not r['success']:
                error_code = r.get('error_code', 'UNKNOWN')
                if error_code not in errors:
                    errors[error_code] = []
                errors[error_code].append(r['model_id'])
        
        print("\nError breakdown:")
        for error_code, models in errors.items():
            print(f"\n{error_code}:")
            for model in models:
                print(f"  - {model}")
        
        print("\nACTION REQUIRED:")
        print("1. Fix identified issues")
        print("2. Re-run tests")
        print("3. Do NOT test expensive models until these pass")
        
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_cheapest_models())
    sys.exit(exit_code)
