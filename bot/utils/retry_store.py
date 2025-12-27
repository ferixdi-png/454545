"""Store last successful generation inputs for retry functionality."""
import logging
from typing import Dict, Any, Optional
from collections import defaultdict
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

# In-memory storage: {user_id: {model_id: last_inputs}}
_last_inputs: Dict[int, Dict[str, Dict[str, Any]]] = defaultdict(dict)
_last_updated: Dict[int, Dict[str, datetime]] = defaultdict(dict)

# TTL for stored inputs (7 days)
_INPUT_TTL = timedelta(days=7)


def store_last_inputs(user_id: int, model_id: str, inputs: Dict[str, Any]) -> None:
    """Store last successful inputs for user+model."""
    _last_inputs[user_id][model_id] = inputs.copy()
    _last_updated[user_id][model_id] = datetime.now()
    log.debug(f"Stored last inputs for user={user_id}, model={model_id}")


def get_last_inputs(user_id: int, model_id: str) -> Optional[Dict[str, Any]]:
    """Get last successful inputs for user+model (if within TTL)."""
    if user_id not in _last_inputs or model_id not in _last_inputs[user_id]:
        return None
    
    # Check TTL
    last_update = _last_updated[user_id].get(model_id)
    if last_update and datetime.now() - last_update > _INPUT_TTL:
        # Expired
        del _last_inputs[user_id][model_id]
        del _last_updated[user_id][model_id]
        return None
    
    return _last_inputs[user_id][model_id].copy()


def clear_last_inputs(user_id: int, model_id: Optional[str] = None) -> None:
    """Clear stored inputs for user (optionally specific model)."""
    if user_id not in _last_inputs:
        return
    
    if model_id:
        _last_inputs[user_id].pop(model_id, None)
        _last_updated[user_id].pop(model_id, None)
    else:
        _last_inputs.pop(user_id, None)
        _last_updated.pop(user_id, None)


def cleanup_old_inputs(max_age: timedelta = None) -> int:
    """Clean up old input records.
    
    Returns: Number of records cleaned
    """
    if max_age is None:
        max_age = _INPUT_TTL
    
    now = datetime.now()
    cleaned = 0
    
    users_to_remove = []
    for user_id in list(_last_updated.keys()):
        models_to_remove = []
        
        for model_id, last_update in _last_updated[user_id].items():
            if now - last_update > max_age:
                models_to_remove.append(model_id)
        
        for model_id in models_to_remove:
            _last_inputs[user_id].pop(model_id, None)
            _last_updated[user_id].pop(model_id, None)
            cleaned += 1
        
        # Remove user if no models left
        if not _last_updated[user_id]:
            users_to_remove.append(user_id)
    
    for user_id in users_to_remove:
        _last_inputs.pop(user_id, None)
        _last_updated.pop(user_id, None)
    
    if cleaned > 0:
        log.debug(f"Cleaned up {cleaned} old input records")
    
    return cleaned
