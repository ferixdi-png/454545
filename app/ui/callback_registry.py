"""Callback registry for short, stable callback_data keys.

Telegram callback_data limit: 64 bytes
Long model IDs like 'elevenlabs/text-to-speech-multilingual-v2' exceed this.

Solution: Generate short keys (prefix:HASH) and maintain in-memory mapping.
"""
import hashlib
import base64
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# In-memory registry: short_key -> original_id
_registry: Dict[str, str] = {}
_reverse: Dict[str, str] = {}  # original_id -> short_key


def _hash_id(raw_id: str) -> str:
    """Generate short hash from ID (10 chars base64url)."""
    digest = hashlib.sha1(raw_id.encode('utf-8')).digest()
    b64 = base64.urlsafe_b64encode(digest[:8]).decode('ascii').rstrip('=')
    return b64[:10]  # 10 chars max


def make_key(prefix: str, raw_id: str) -> str:
    """
    Create short callback key from prefix and raw ID.
    
    Format: prefix:HASH (e.g., "m:Ab12Cd34Ef")
    
    Args:
        prefix: Category prefix (m=model, f=format, etc.)
        raw_id: Original ID (may be long)
        
    Returns:
        Short key suitable for callback_data (<= 20 chars)
    """
    if not raw_id:
        return prefix
    
    # Check if already registered
    cache_key = f"{prefix}:{raw_id}"
    if cache_key in _reverse:
        return _reverse[cache_key]
    
    # Generate new short key
    short_hash = _hash_id(raw_id)
    short_key = f"{prefix}:{short_hash}"
    
    # Register both directions
    _registry[short_key] = raw_id
    _reverse[cache_key] = short_key
    
    logger.debug(f"Registered callback: {short_key} -> {raw_id}")
    
    return short_key


def resolve_key(key: str) -> Optional[str]:
    """
    Resolve short key back to original ID.
    
    Args:
        key: Short callback key (e.g., "m:Ab12Cd34Ef")
        
    Returns:
        Original ID or None if not found
    """
    if not key or ':' not in key:
        return None
    
    original = _registry.get(key)
    if not original:
        logger.warning(f"Callback key not found in registry: {key}")
    
    return original


def init_registry_from_models(models_dict: Dict[str, dict]) -> None:
    """
    Pre-populate registry from SOURCE_OF_TRUTH models.
    
    Args:
        models_dict: Dict of model_id -> model config
    """
    logger.info(f"Initializing callback registry with {len(models_dict)} models")
    
    for model_id in models_dict.keys():
        make_key("m", model_id)  # m: = model
        make_key("gen", model_id)  # gen: = generation
        make_key("card", model_id)  # card: = model card
    
    logger.info(f"Callback registry initialized: {len(_registry)} keys")


def validate_callback_length(callback_data: str) -> bool:
    """
    Validate callback_data doesn't exceed Telegram's 64-byte limit.
    
    Args:
        callback_data: Callback data string
        
    Returns:
        True if valid length
        
    Raises:
        ValueError if exceeds limit
    """
    byte_length = len(callback_data.encode('utf-8'))
    
    if byte_length > 64:
        raise ValueError(
            f"callback_data exceeds 64 bytes: {byte_length} bytes\n"
            f"Data: {callback_data[:100]}"
        )
    
    return True


def get_stats() -> Dict[str, int]:
    """Get registry statistics."""
    return {
        "total_keys": len(_registry),
        "unique_ids": len(set(_registry.values()))
    }
