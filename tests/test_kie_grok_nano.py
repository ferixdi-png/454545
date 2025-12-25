#!/usr/bin/env python3
"""
Test Grok and Nano Banana models with real Kie.ai API.
These are CHEAP models suitable for testing.
"""
import asyncio
import os
import sys
import json

# Add parent directory to path
sys.path.insert(0, '/workspaces/5656')

from app.kie.generator import KieGenerator

# Test budget
MAX_TOTAL_BUDGET_RUB = 100  # 100₽ total budget
credits_spent = []

async def test_grok_text_to_video():
    """
    Test grok-imagine/text-to-video
    Cost: 20 credits = 0.1 USD = 9.5₽ (KIE) → 14.25₽ (our price)
    """
    print("\n" + "="*80)
    print("TEST 1: Grok Text-to-Video (14.25₽)")
    print("="*80)
    
    generator = KieGenerator()
    
    result = await generator.generate(
        model_id='grok-imagine/text-to-video',
        user_inputs={
            'prompt': 'A cute cat playing with a ball of yarn',
            'aspect_ratio': '1:1',
            'mode': 'normal'
        },
        timeout=300  # 5 minutes
    )
    
    print(f"\n✅ Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get('success'):
        credits_spent.append({
            'model': 'grok-imagine/text-to-video',
            'cost_rub': 14.25,
            'result': result.get('result_urls', [])
        })
        print(f"💰 Cost: 14.25₽")
        return True
    else:
        print(f"❌ Failed: {result.get('error_code')}: {result.get('error_message')}")
        return False


async def test_grok_text_to_image():
    """
    Test grok-imagine/text-to-image
    Cost: Unknown (need to check pricing page)
    """
    print("\n" + "="*80)
    print("TEST 2: Grok Text-to-Image (price TBD)")
    print("="*80)
    
    generator = KieGenerator()
    
    result = await generator.generate(
        model_id='grok-imagine/text-to-image',
        user_inputs={
            'prompt': 'A beautiful sunset over mountains',
            'aspect_ratio': '16:9'
        },
        timeout=180
    )
    
    print(f"\n✅ Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get('success'):
        # Price unknown, estimate 10₽
        credits_spent.append({
            'model': 'grok-imagine/text-to-image',
            'cost_rub': 10.0,
            'result': result.get('result_urls', [])
        })
        print(f"💰 Cost: ~10₽ (estimated)")
        return True
    else:
        print(f"❌ Failed: {result.get('error_code')}: {result.get('error_message')}")
        return False


async def test_nano_banana_pro_1k():
    """
    Test nano-banana-pro with 1K resolution
    Cost: 18 credits = 0.09 USD = 8.55₽ (KIE) → 12.83₽ (our price)
    """
    print("\n" + "="*80)
    print("TEST 3: Nano Banana Pro 1K (12.83₽) - CHEAPEST IMAGE MODEL")
    print("="*80)
    
    generator = KieGenerator()
    
    result = await generator.generate(
        model_id='nano-banana-pro',
        user_inputs={
            'prompt': 'A cute banana character with sunglasses',
            'aspect_ratio': '1:1',
            'resolution': '1K',
            'output_format': 'png'
        },
        timeout=180
    )
    
    print(f"\n✅ Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get('success'):
        credits_spent.append({
            'model': 'nano-banana-pro',
            'resolution': '1K',
            'cost_rub': 12.83,
            'result': result.get('result_urls', [])
        })
        print(f"💰 Cost: 12.83₽")
        return True
    else:
        print(f"❌ Failed: {result.get('error_code')}: {result.get('error_message')}")
        return False


async def test_grok_image_to_video():
    """
    Test grok-imagine/image-to-video
    Cost: 20 credits = 0.1 USD = 9.5₽ (KIE) → 14.25₽ (our price)
    
    Note: This test requires an image URL or previous task_id
    """
    print("\n" + "="*80)
    print("TEST 4: Grok Image-to-Video (14.25₽)")
    print("="*80)
    
    generator = KieGenerator()
    
    # Using example image from docs
    result = await generator.generate(
        model_id='grok-imagine/image-to-video',
        user_inputs={
            'image_urls': ['https://file.aiquickdraw.com/custom-page/akr/section-images/1762247692373tw5di116.png'],
            'prompt': 'The girl smiles and waves hello',
            'mode': 'normal'
        },
        timeout=300
    )
    
    print(f"\n✅ Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get('success'):
        credits_spent.append({
            'model': 'grok-imagine/image-to-video',
            'cost_rub': 14.25,
            'result': result.get('result_urls', [])
        })
        print(f"💰 Cost: 14.25₽")
        return True
    else:
        print(f"❌ Failed: {result.get('error_code')}: {result.get('error_message')}")
        return False


async def main():
    """Run all tests."""
    print("🚀 TESTING KIE.AI MODELS")
    print(f"📊 Budget: {MAX_TOTAL_BUDGET_RUB}₽")
    print()
    
    # Check API key
    if not os.getenv('KIE_API_KEY'):
        print("⚠️  KIE_API_KEY not set!")
        print("   Set it with: export KIE_API_KEY=your_key")
        print("   Skipping real API tests...")
        return
    
    results = []
    
    # Test cheapest models first
    results.append(await test_nano_banana_pro_1k())  # 12.83₽
    results.append(await test_grok_text_to_video())  # 14.25₽
    results.append(await test_grok_image_to_video())  # 14.25₽
    results.append(await test_grok_text_to_image())  # ~10₽
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    total_cost = sum(c['cost_rub'] for c in credits_spent)
    passed = sum(1 for r in results if r)
    failed = sum(1 for r in results if not r)
    
    print(f"✅ Passed: {passed}/{len(results)}")
    print(f"❌ Failed: {failed}/{len(results)}")
    print(f"💰 Total spent: {total_cost:.2f}₽ / {MAX_TOTAL_BUDGET_RUB}₽")
    
    if total_cost > MAX_TOTAL_BUDGET_RUB:
        print(f"⚠️  WARNING: Over budget by {total_cost - MAX_TOTAL_BUDGET_RUB:.2f}₽")
    
    print("\n📦 Generated content:")
    for i, credit in enumerate(credits_spent, 1):
        print(f"{i}. {credit['model']} ({credit['cost_rub']}₽):")
        for url in credit.get('result', []):
            print(f"   - {url}")
    
    return passed == len(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
