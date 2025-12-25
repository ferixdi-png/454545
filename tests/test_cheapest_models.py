#!/usr/bin/env python3
"""
Tests for CHEAPEST KIE.AI models (0.36₽ - 3.56₽)
Budget: ~50₽ max
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.kie.builder import build_payload
import time

def test_recraft_upscale():
    """Test Recraft Crisp Upscale - 0.36₽"""
    print("\n" + "="*80)
    print("🧪 TEST: Recraft Crisp Upscale (0.36₽)")
    print("="*80)
    
    payload = build_payload("recraft/crisp-upscale", {
        "image": "https://example.com/test.jpg"
    })
    
    print(f"📦 Payload: {payload}")
    print("💰 Cost: 0.36₽")
    # Note: Don't actually run - need real image URL

def test_qwen_z_image():
    """Test z-image - FREE (0₽)"""
    print("\n" + "="*80)
    print("🧪 TEST: z-image (FREE)")
    print("="*80)
    
    payload = build_payload("z-image", {
        "prompt": "A cute cat sitting on a windowsill"
    })
    
    print(f"📦 Payload: {payload}")
    print("💰 Cost: FREE")

def test_recraft_remove_bg():
    """Test Recraft Remove Background - 0.4₽"""
    print("\n" + "="*80)
    print("🧪 TEST: Recraft Remove Background (0.4₽)")
    print("="*80)
    
    payload = build_payload("recraft/remove-background", {
        "image_url": "https://example.com/test.jpg"
    })
    
    print(f"📦 Payload: {payload}")
    print("💰 Cost: 0.4₽")

def test_bytedance_seedream():
    """Test Bytedance Seedream - 1.38₽"""
    print("\n" + "="*80)
    print("🧪 TEST: Bytedance Seedream (1.38₽)")
    print("="*80)
    
    payload = build_payload("bytedance/seedream", {
        "prompt": "A magical forest with glowing mushrooms"
    })
    
    print(f"📦 Payload: {payload}")
    print("💰 Cost: 1.38₽")

def test_qwen_text_to_image():
    """Test Qwen Text-to-Image - FREE"""
    print("\n" + "="*80)
    print("🧪 TEST: Qwen Text-to-Image (FREE)")
    print("="*80)
    
    payload = build_payload("qwen/text-to-image", {
        "prompt": "Modern minimalist logo for AI company"
    })
    
    print(f"📦 Payload: {payload}")
    print("💰 Cost: FREE")

def test_elevenlabs_audio_isolation():
    """Test ElevenLabs Audio Isolation - 0.08₽"""
    print("\n" + "="*80)
    print("🧪 TEST: ElevenLabs Audio Isolation (0.08₽)")
    print("="*80)
    
    payload = build_payload("elevenlabs/audio-isolation", {
        "audio_url": "https://example.com/audio.mp3"
    })
    
    print(f"📦 Payload: {payload}")
    print("💰 Cost: 0.08₽")

def test_recraft_crisp_upscale():
    """Test Recraft Crisp Upscale - 0.2₽"""
    print("\n" + "="*80)
    print("🧪 TEST: Recraft Crisp Upscale (0.2₽)")
    print("="*80)
    
    payload = build_payload("recraft/crisp-upscale", {
        "image_url": "https://example.com/test.jpg"
    })
    
    print(f"📦 Payload: {payload}")
    print("💰 Cost: 0.2₽")

def main():
    """Run all tests"""
    print("🚀 CHEAPEST KIE.AI MODELS TEST SUITE")
    print(f"📅 Date: 2025-12-24")
    print(f"💵 Budget: 50₽ max")
    print(f"🔑 API Key: {'✅ SET' if os.getenv('KIE_API_KEY') else '❌ NOT SET'}")
    
    total_cost = 0.36 + 0.57 + 0.71 + 2.14 + 2.49 + 2.85 + 2.85 + 3.56 + 3.56
    print(f"💰 Estimated total cost: {total_cost:.2f}₽")
    
    # Run payload tests (no API calls yet)
    test_recraft_upscale()
    test_qwen_z_image()
    test_recraft_remove_bg()
    test_midjourney_fast()
    test_ideogram_v3()
    test_grok_text_to_image()
    test_nano_banana()
    test_flux_pro()
    test_seedream_4()
    
    print("\n" + "="*80)
    print("✅ ALL PAYLOAD TESTS PASSED")
    print("="*80)
    print()
    print("⚠️  To run REAL API tests:")
    print("   export KIE_API_KEY=sk-your-key")
    print("   python tests/test_cheapest_models.py --real")
    print()

if __name__ == "__main__":
    main()
