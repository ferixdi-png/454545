"""Normalize KIE API responses to handle all edge cases.

KIE API inconsistencies:
- Sometimes "data" missing
- Sometimes taskId vs recordId
- Sometimes failCode present
- Poll responses vary by model/state
"""
from typing import Optional, Dict, Any, List, Tuple
import logging

log = logging.getLogger(__name__)


def normalize_create_response(resp: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Normalize task creation response.
    
    Returns: (task_id, record_id)
    - task_id: for polling
    - record_id: for reference (optional)
    """
    # Common patterns:
    # 1. {"data": {"taskId": "...", "recordId": "..."}}
    # 2. {"taskId": "...", "recordId": "..."}
    # 3. {"data": {"id": "..."}}
    # 4. {"id": "..."}
    
    data = resp.get("data", resp)
    
    task_id = (
        data.get("taskId") or 
        data.get("task_id") or 
        data.get("id") or
        data.get("recordId") or
        data.get("record_id")
    )
    
    record_id = (
        data.get("recordId") or 
        data.get("record_id") or
        data.get("id")
    )
    
    if not task_id:
        log.warning(f"Failed to extract task_id from response: {resp}")
    
    return task_id, record_id


def normalize_poll_response(resp: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize polling response.
    
    Returns dict with:
    - state: 'pending' | 'processing' | 'success' | 'fail' | 'timeout' | 'unknown'
    - outputs: list of output URLs/data (if success)
    - fail_code: error code (if fail)
    - message: error message (if fail)
    - raw: original response
    """
    data = resp.get("data", resp)
    
    # Extract state
    state_raw = (
        data.get("state") or 
        data.get("status") or 
        data.get("taskStatus") or
        "unknown"
    )
    state_raw = str(state_raw).lower()
    
    # Normalize state to standard values
    if state_raw in ("pending", "queued", "waiting"):
        state = "pending"
    elif state_raw in ("processing", "running", "in_progress"):
        state = "processing"
    elif state_raw in ("success", "completed", "done", "finished"):
        state = "success"
    elif state_raw in ("fail", "failed", "error"):
        state = "fail"
    elif state_raw in ("timeout", "expired"):
        state = "timeout"
    else:
        state = "unknown"
    
    # Check for failCode (overrides state)
    fail_code = data.get("failCode") or data.get("fail_code") or data.get("errorCode")
    if fail_code:
        state = "fail"
    
    # Extract outputs
    outputs = []
    if state == "success":
        # Common output patterns:
        # 1. {"outputs": [{"url": "..."}, ...]}
        # 2. {"output": "url"}
        # 3. {"imageUrl": "...", "imageUrl_2": "..."}
        # 4. {"result": {"images": [...]}}
        
        outputs_raw = data.get("outputs") or data.get("output") or data.get("result")
        
        if isinstance(outputs_raw, list):
            for item in outputs_raw:
                if isinstance(item, dict):
                    url = item.get("url") or item.get("imageUrl") or item.get("videoUrl") or item.get("audioUrl")
                    if url:
                        outputs.append(url)
                elif isinstance(item, str):
                    outputs.append(item)
        elif isinstance(outputs_raw, str):
            outputs.append(outputs_raw)
        elif isinstance(outputs_raw, dict):
            # Extract all *Url fields
            for key, value in outputs_raw.items():
                if key.endswith("Url") or key.endswith("url"):
                    if isinstance(value, str):
                        outputs.append(value)
                    elif isinstance(value, list):
                        outputs.extend([v for v in value if isinstance(v, str)])
        
        # Fallback: search for common URL keys
        if not outputs:
            for key in ("imageUrl", "videoUrl", "audioUrl", "url", "image_url", "video_url"):
                val = data.get(key)
                if val:
                    if isinstance(val, str):
                        outputs.append(val)
                    elif isinstance(val, list):
                        outputs.extend([v for v in val if isinstance(v, str)])
    
    # Extract error message
    message = None
    if state == "fail":
        message = (
            data.get("message") or 
            data.get("error") or 
            data.get("errorMessage") or
            data.get("failReason") or
            f"Failed with code: {fail_code}" if fail_code else "Unknown error"
        )
    
    return {
        "state": state,
        "outputs": outputs,
        "fail_code": fail_code,
        "message": message,
        "raw": resp,
    }


def detect_output_type(url: str) -> str:
    """Detect output type from URL.
    
    Returns: 'image' | 'video' | 'audio' | 'unknown'
    """
    url_lower = url.lower()
    
    # Image extensions
    if any(ext in url_lower for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")):
        return "image"
    
    # Video extensions
    if any(ext in url_lower for ext in (".mp4", ".mov", ".avi", ".webm", ".mkv")):
        return "video"
    
    # Audio extensions
    if any(ext in url_lower for ext in (".mp3", ".wav", ".ogg", ".m4a", ".flac")):
        return "audio"
    
    # Fallback: check URL path segments
    if "/image" in url_lower or "/img" in url_lower:
        return "image"
    
    if "/video" in url_lower or "/vid" in url_lower:
        return "video"
    
    if "/audio" in url_lower or "/sound" in url_lower:
        return "audio"
    
    return "unknown"
