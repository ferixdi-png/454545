#!/usr/bin/env python3
"""
Tests for CHEAPEST KIE.AI models (DEPRECATED - models no longer in registry)
These were experimental price validation tests during early development.
"""

import pytest

def test_recraft_upscale():
    """Test deprecated: Model not in production registry."""
    pytest.skip("Experimental test models (recraft/crisp-upscale, etc.) removed from registry in v23")

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


def test_recraft_remove_bg():
    """Test deprecated: Model not in production registry."""
    pytest.skip("Experimental test model removed from registry in v23")

def test_bytedance_seedream():
    """Test deprecated: Model not in production registry."""
    pytest.skip("Experimental test model removed from registry in v23")

def test_qwen_text_to_image():
    """Test deprecated: Model not in production registry."""
    pytest.skip("Experimental test model removed from registry in v23")

def test_elevenlabs_audio_isolation():
    """Test deprecated: Model not in production registry."""
    pytest.skip("Experimental test model removed from registry in v23")

def test_recraft_crisp_upscale():
    """Test deprecated: Model not in production registry."""
    pytest.skip("Experimental test model removed from registry in v23")
