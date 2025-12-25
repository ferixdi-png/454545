#!/usr/bin/env python3
"""
Test Wan 2.6 and Seedream 4.5 models with real Kie.ai API.
Budget-conscious testing.
"""
import asyncio
import os
import sys
import json

sys.path.insert(0, '/workspaces/5656')

from app.kie.generator import KieGenerator

MAX_TOTAL_BUDGET_RUB = 100  # 100₽ budget
credits_spent = []


async def test_seedream_45_basic():
    """
    Test seedream/4.5-text-to-image with Basic quality (2K)
    Cost: 5 credits = 0.025 USD = 2.38₽ (KIE) → 3.56₽ (our price)
    CHEAPEST IMAGE MODEL!
    """
    print("\n" + "="*80)
    print("TEST 1: Seedream 4.5 Text-to-Image Basic (3.56₽) - CHEAPEST IMAGE!")
    print("="*80)
    
    generator = KieGenerator()
    
    result = await generator.generate(
        model_id='seedream/4.5-text-to-image',
        user_inputs={
            'prompt': 'A cute cat sitting on a windowsill',
            'aspect_ratio': '16:9',
            'quality': 'basic'
        },
        timeout=180
    )
    
    print(f"\n✅ Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get('success'):
        credits_spent.append({
            'model': 'seedream/4.5-text-to-image',
            'quality': 'basic',
            'cost_rub': 3.56,
            'result': result.get('result_urls', [])
        })
        print(f"💰 Cost: 3.56₽")
        return True
    else:
        print(f"❌ Failed: {result.get('error_code')}: {result.get('error_message')}")
        return False


async def test_wan_26_text_to_video_5s():
    """
    Test wan/2-6-text-to-video with 5s duration
    Cost: 70 credits = 0.35 USD = 33.25₽ (KIE) → 49.88₽ (our price)
    """
    print("\n" + "="*80)
    print("TEST 2: Wan 2.6 Text-to-Video 5s (49.88₽)")
    print("="*80)
    
    generator = KieGenerator()
    
    result = await generator.generate(
        model_id='wan/2-6-text-to-video',
        user_inputs={
            'prompt': 'A cat playing with a ball of yarn in slow motion',
            'duration': '5',
            'resolution': '1080p',
            'multi_shots': False
        },
        timeout=300
    )
    
    print(f"\n✅ Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get('success'):
        credits_spent.append({
            'model': 'wan/2-6-text-to-video',
            'duration': '5s',
            'cost_rub': 49.88,
            'result': result.get('result_urls', [])
        })
        print(f"💰 Cost: 49.88₽")
        return True
    else:
        print(f"❌ Failed: {result.get('error_code')}: {result.get('error_message')}")
        return False


async def test_wan_26_image_to_video_5s():
    """
    Test wan/2-6-image-to-video with 5s duration
    Cost: 60 credits = 0.30 USD = 28.50₽ (KIE) → 42.75₽ (our price)
    """
    print("\n" + "="*80)
    print("TEST 3: Wan 2.6 Image-to-Video 5s (42.75₽)")
    print("="*80)
    
    generator = KieGenerator()
    
    # Using example image from Wan docs
    result = await generator.generate(
        model_id='wan/2-6-image-to-video',
        user_inputs={
            'image_urls': ['https://static.aiquickdraw.com/tools/example/1765957673717_awiBAidD.webp'],
            'prompt': 'The fox starts singing and dancing',
            'duration': '5',
            'resolution': '720p',  # Use 720p to save credits
            'multi_shots': False
        },
        timeout=300
    )
    
    print(f"\n✅ Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get('success'):
        credits_spent.append({
            'model': 'wan/2-6-image-to-video',
            'duration': '5s',
            'resolution': '720p',
            'cost_rub': 42.75,
            'result': result.get('result_urls', [])
        })
        print(f"💰 Cost: 42.75₽")
        return True
    else:
        print(f"❌ Failed: {result.get('error_code')}: {result.get('error_message')}")
        return False


async def main():
    """Run all tests."""
    print("🚀 TESTING WAN 2.6 & SEEDREAM 4.5 MODELS")
    print(f"📊 Budget: {MAX_TOTAL_BUDGET_RUB}₽")
    print()
    
    # Check API key
    if not os.getenv('KIE_API_KEY'):
        print("⚠️  KIE_API_KEY not set!")
        print("   Set it with: export KIE_API_KEY=your_key")
        print("   Skipping real API tests...")
        return
    
    results = []
    
    # Test cheapest first
    results.append(await test_seedream_45_basic())  # 3.56₽
    results.append(await test_wan_26_image_to_video_5s())  # 42.75₽
    results.append(await test_wan_26_text_to_video_5s())  # 49.88₽
    
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
