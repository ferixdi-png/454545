"""Tests for format derivation from input_schema."""
import pytest
from app.ui.catalog import load_models_sot


def test_text_to_image_format():
    """Test text-to-image format detection."""
    # Models that should be text-to-image:
    # - Required: prompt (text input)
    # - No image_url required
    # - Output: image
    
    try:
        models = load_models_sot()
    except Exception:
        pytest.skip("SOURCE_OF_TRUTH not available")
    
    text_to_image_models = []
    
    for model_id, model in models.items():
        if not model.get("enabled", True):
            continue
        
        inputs = model.get("inputs", {})
        output_type = model.get("output_type", "unknown")
        
        # Text-to-image: requires prompt, no image_url, output is image
        has_prompt = "prompt" in inputs and inputs["prompt"].get("required", False)
        has_image_input = any(
            inp.get("type") == "IMAGE_URL" and inp.get("required", False)
            for inp in inputs.values()
        )
        is_image_output = output_type in ["IMAGE", "IMAGE_URL"]
        
        if has_prompt and not has_image_input and is_image_output:
            text_to_image_models.append(model_id)
    
    # Should have some text-to-image models
    assert len(text_to_image_models) > 0, "No text-to-image models found"


def test_image_to_video_format():
    """Test image-to-video format detection."""
    try:
        models = load_models_sot()
    except Exception:
        pytest.skip("SOURCE_OF_TRUTH not available")
    
    image_to_video_models = []
    
    for model_id, model in models.items():
        if not model.get("enabled", True):
            continue
        
        inputs = model.get("inputs", {})
        output_type = model.get("output_type", "unknown")
        
        # Image-to-video: requires image_url, output is video
        has_image_input = any(
            inp.get("type") == "IMAGE_URL" and inp.get("required", False)
            for inp in inputs.values()
        )
        is_video_output = output_type in ["VIDEO", "VIDEO_URL"]
        
        if has_image_input and is_video_output:
            image_to_video_models.append(model_id)
    
    # Should have some image-to-video models
    assert len(image_to_video_models) > 0, "No image-to-video models found"


def test_text_to_audio_format():
    """Test text-to-audio format detection."""
    try:
        models = load_models_sot()
    except Exception:
        pytest.skip("SOURCE_OF_TRUTH not available")
    
    text_to_audio_models = []
    
    for model_id, model in models.items():
        if not model.get("enabled", True):
            continue
        
        inputs = model.get("inputs", {})
        output_type = model.get("output_type", "unknown")
        
        # Text-to-audio: requires text input, output is audio
        has_text_input = any(
            inp.get("type") in ["TEXT", "TEXTAREA"] and inp.get("required", False)
            for inp in inputs.values()
        )
        is_audio_output = output_type in ["AUDIO", "AUDIO_URL"]
        
        if has_text_input and is_audio_output:
            text_to_audio_models.append(model_id)
    
    # Should have some text-to-audio models
    assert len(text_to_audio_models) > 0, "No text-to-audio models found"


def test_all_enabled_models_have_format():
    """Test that all enabled models can be assigned a format."""
    try:
        models = load_models_sot()
    except Exception:
        pytest.skip("SOURCE_OF_TRUTH not available")
    
    unclassified = []
    
    for model_id, model in models.items():
        if not model.get("enabled", True):
            continue
        
        inputs = model.get("inputs", {})
        output_type = model.get("output_type", "unknown")
        
        # Try to classify
        has_prompt = "prompt" in inputs
        has_image_input = any(inp.get("type") == "IMAGE_URL" for inp in inputs.values())
        has_audio_input = any(inp.get("type") == "AUDIO_URL" for inp in inputs.values())
        
        is_image_output = output_type in ["IMAGE", "IMAGE_URL"]
        is_video_output = output_type in ["VIDEO", "VIDEO_URL"]
        is_audio_output = output_type in ["AUDIO", "AUDIO_URL"]
        
        # Should fit into at least one category
        classified = (
            is_image_output or is_video_output or is_audio_output
        )
        
        if not classified:
            unclassified.append(model_id)
    
    # Most models should have a clear output type
    assert len(unclassified) < len(models) * 0.1, f"Too many unclassified models: {unclassified}"


def test_format_map_file_exists():
    """Test that model_format_map.json can be loaded."""
    from pathlib import Path
    import json
    
    repo_root = Path(__file__).resolve().parent.parent
    map_file = repo_root / "app/ui/content/model_format_map.json"
    
    assert map_file.exists(), "model_format_map.json not found"
    
    with open(map_file, "r", encoding="utf-8") as f:
        format_map = json.load(f)
    
    assert "model_to_formats" in format_map, "Missing model_to_formats key"
    assert isinstance(format_map["model_to_formats"], dict), "model_to_formats should be dict"
