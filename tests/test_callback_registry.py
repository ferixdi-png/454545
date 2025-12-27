"""Tests for callback registry (short keys for Telegram's 64-byte limit)."""
import pytest
from app.ui.callback_registry import (
    make_key,
    resolve_key,
    validate_callback_length,
    init_registry_from_models,
    _registry,
    _reverse,
)


def test_make_key_creates_short_keys():
    """Test that make_key generates keys under 64 bytes."""
    # Long model IDs that would exceed limit
    long_model_ids = [
        "elevenlabs/text-to-speech-multilingual-v2",
        "some-very-long-organization/model-name-that-is-way-too-long-for-telegram-callbacks",
        "a" * 100,  # Extreme case
    ]
    
    for model_id in long_model_ids:
        # Make keys for different prefixes
        for prefix in ["m", "gen", "card"]:
            key = make_key(prefix, model_id)
            
            # Key should be short (prefix + ":" + 10-char hash = ~14 bytes)
            assert len(key) < 20, f"Key too long: {len(key)} bytes for {model_id}"
            assert key.startswith(f"{prefix}:"), f"Key doesn't start with {prefix}:"
            assert len(key.encode('utf-8')) <= 64, "Key exceeds Telegram's 64-byte limit"


def test_resolve_key_roundtrip():
    """Test that resolve_key can retrieve original model_id."""
    model_ids = [
        "elevenlabs/text-to-speech-multilingual-v2",
        "black-forest-labs/flux-1.1-pro",
        "simple-model",
    ]
    
    for model_id in model_ids:
        short_key = make_key("m", model_id)
        resolved = resolve_key(short_key)
        
        assert resolved == model_id, f"Roundtrip failed: {model_id} → {short_key} → {resolved}"


def test_resolve_key_returns_none_for_unknown():
    """Test that resolve_key returns None for unknown keys."""
    unknown_keys = [
        "m:UNKNOWN123",
        "gen:NOTEXIST",
        "invalid",
    ]
    
    for key in unknown_keys:
        resolved = resolve_key(key)
        assert resolved is None, f"Expected None for unknown key {key}, got {resolved}"


def test_validate_callback_length_accepts_short():
    """Test that validate_callback_length accepts short callbacks."""
    short_callbacks = [
        "menu:main",
        "home",
        "m:Ab12Cd34Ef",
        "gen:1234567890",
    ]
    
    for callback in short_callbacks:
        # Should not raise
        validate_callback_length(callback)


def test_validate_callback_length_rejects_long():
    """Test that validate_callback_length rejects long callbacks."""
    long_callback = "x" * 100  # Way over 64 bytes
    
    with pytest.raises(ValueError, match="exceeds 64 bytes"):
        validate_callback_length(long_callback)


def test_init_registry_from_models():
    """Test that init_registry_from_models populates registry."""
    mock_models = {
        "model-1": {"id": "model-1", "enabled": True},
        "model-2": {"id": "model-2", "enabled": True},
        "elevenlabs/text-to-speech-multilingual-v2": {"id": "elevenlabs/text-to-speech-multilingual-v2", "enabled": True},
    }
    
    # Clear registry
    _registry.clear()
    _reverse.clear()
    
    # Initialize from models
    init_registry_from_models(mock_models)
    
    # Check that keys were created for all prefixes
    for model_id in mock_models.keys():
        # Should create: m:HASH, gen:HASH, card:HASH
        m_key = make_key("m", model_id)
        gen_key = make_key("gen", model_id)
        card_key = make_key("card", model_id)
        
        # Resolve should work
        assert resolve_key(m_key) == model_id
        assert resolve_key(gen_key) == model_id
        assert resolve_key(card_key) == model_id


def test_duplicate_prefixes_dont_collide():
    """Test that same model_id with different prefixes creates different keys."""
    model_id = "test-model"
    
    m_key = make_key("m", model_id)
    gen_key = make_key("gen", model_id)
    card_key = make_key("card", model_id)
    
    # All should resolve to same model_id
    assert resolve_key(m_key) == model_id
    assert resolve_key(gen_key) == model_id
    assert resolve_key(card_key) == model_id
    
    # But keys should be distinct
    assert m_key != gen_key
    assert m_key != card_key
    assert gen_key != card_key


def test_callback_key_length_real_world():
    """Test real-world callback patterns don't exceed limit."""
    from app.ui.catalog import load_models_sot
    
    try:
        models = load_models_sot()
    except Exception:
        pytest.skip("SOURCE_OF_TRUTH not available")
    
    # Test all enabled models
    for model_id, model in models.items():
        if not model.get("enabled", True):
            continue
        
        # Create callbacks for all patterns
        callbacks = [
            make_key("m", model_id),
            make_key("gen", model_id),
            make_key("card", model_id),
        ]
        
        for callback in callbacks:
            byte_length = len(callback.encode('utf-8'))
            assert byte_length <= 64, f"Callback exceeds limit: {callback} ({byte_length} bytes)"
