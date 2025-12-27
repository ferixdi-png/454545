#!/usr/bin/env python3
"""
Verify overlay merge + format groups work correctly.
CRITICAL: Ensures UI enhancements don't break model loading.
"""
import sys
from pathlib import Path

# Add project root
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_overlay_merge():
    """Test overlay merges correctly into models."""
    from app.ui.catalog import load_models_sot, merge_overlay
    
    models = load_models_sot()
    
    # Check overlay applied to remove-background
    rb_model = models.get("recraft/remove-background")
    if not rb_model:
        print("❌ recraft/remove-background not found")
        return False
    
    # Check schema override
    schema = rb_model.get("input_schema", {})
    required = schema.get("required", [])
    
    if "image_url" not in required:
        print(f"❌ recraft/remove-background schema not fixed: required={required}")
        return False
    
    # Check output_type
    if rb_model.get("output_type") != "image":
        print(f"❌ recraft/remove-background output_type={rb_model.get('output_type')}, expected 'image'")
        return False
    
    # Check UI metadata
    if "ui" not in rb_model:
        print("❌ recraft/remove-background missing UI metadata")
        return False
    
    print("✅ Overlay merge works (remove-background schema fixed)")
    return True


def test_format_groups():
    """Test format grouping works."""
    from app.ui.format_groups import group_by_format, get_format_group, get_popular_score
    from app.ui.catalog import load_models_sot
    
    models = load_models_sot()
    grouped = group_by_format(models)
    
    # Check groups exist
    expected_groups = ["text2image", "image2video", "text2video", "text2audio", "tools"]
    for group in expected_groups:
        if group not in grouped:
            print(f"❌ Missing format group: {group}")
            return False
        
        if len(grouped[group]) == 0:
            print(f"⚠️  WARNING: Empty format group: {group}")
    
    # Check sora-2-text-to-video in text2video
    sora = models.get("sora-2-text-to-video")
    if sora:
        format_group = get_format_group(sora)
        if format_group != "text2video":
            print(f"❌ sora format_group={format_group}, expected 'text2video'")
            return False
    
    # Check popular_score exists
    z_image = models.get("z-image")
    if z_image:
        score = get_popular_score(z_image)
        if score < 50:
            print(f"⚠️  WARNING: z-image popular_score={score}, expected high score")
    
    print(f"✅ Format groups work ({len([g for g in grouped.values() if g])} non-empty groups)")
    return True


def test_get_popular_models():
    """Test popular models sorting."""
    from app.ui.format_groups import get_popular_models
    from app.ui.catalog import load_models_sot
    
    models = load_models_sot()
    popular = get_popular_models(models, limit=5)
    
    if len(popular) < 5:
        print(f"❌ get_popular_models returned only {len(popular)} models")
        return False
    
    # Check sorted by score (descending)
    from app.ui.format_groups import get_popular_score
    scores = [get_popular_score(m) for m in popular]
    
    if scores != sorted(scores, reverse=True):
        print(f"❌ Popular models not sorted by score: {scores}")
        return False
    
    print(f"✅ Popular models sorted correctly (top 5 scores: {scores})")
    return True


def test_wizard_input_types():
    """Test wizard can handle different input types."""
    from app.ui.input_spec import get_input_spec, InputType
    from app.ui.catalog import get_model
    
    # Test image-to-video (requires image_url)
    sora_i2v = get_model("sora-2-image-to-video")
    if sora_i2v:
        spec = get_input_spec(sora_i2v)
        
        # Should have image_url field
        image_field = next((f for f in spec.fields if f.name == "image_url"), None)
        if not image_field:
            print("❌ sora-2-image-to-video missing image_url field")
            return False
        
        if image_field.type not in [InputType.IMAGE_URL, InputType.IMAGE_FILE]:
            print(f"❌ image_url field has wrong type: {image_field.type}")
            return False
    
    # Test audio isolation (requires audio_url)
    audio_iso = get_model("elevenlabs/audio-isolation")
    if audio_iso:
        spec = get_input_spec(audio_iso)
        
        audio_field = next((f for f in spec.fields if f.name == "audio_url"), None)
        if not audio_field:
            print("❌ audio-isolation missing audio_url field")
            return False
    
    print("✅ Wizard input types correct (image_url, audio_url fields detected)")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("OVERLAY + FORMAT GROUPS VERIFICATION")
    print("=" * 60)
    
    tests = [
        ("Overlay merge", test_overlay_merge),
        ("Format groups", test_format_groups),
        ("Popular models sorting", test_get_popular_models),
        ("Wizard input types", test_wizard_input_types),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n{'=' * 60}")
        print(f"TEST: {name}")
        print(f"{'=' * 60}")
        
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n{passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 ALL TESTS PASSED - Overlay system works")
        return 0
    else:
        print(f"\n❌ {total_count - passed_count} tests FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
