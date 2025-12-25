"""
Input validation utilities for security and data integrity.

MASTER PROMPT compliance:
- Validate all user inputs before processing
- Prevent security vulnerabilities
- Protect against malicious inputs
"""

import re
from typing import Optional, Tuple
from urllib.parse import urlparse


# Allowed file extensions
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.webm'}
ALLOWED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.m4a', '.flac'}

# Maximum file sizes (in bytes)
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_AUDIO_SIZE = 50 * 1024 * 1024   # 50 MB

# Allowed URL schemes
ALLOWED_URL_SCHEMES = {'http', 'https'}

# Blocked domains (known malicious/spam)
BLOCKED_DOMAINS = {
    'localhost',
    '127.0.0.1',
    '0.0.0.0',
    '192.168.',
    '10.',
    '172.16.',
    # Add more as needed
}


def validate_url(url: str, allow_local: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Validate URL for security and correctness.
    
    Args:
        url: URL to validate
        allow_local: Whether to allow localhost/private IPs
        
    Returns:
        (is_valid, error_message)
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string"
    
    # Basic length check
    if len(url) > 2048:
        return False, "URL is too long (max 2048 characters)"
    
    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"
    
    # Check scheme
    if parsed.scheme not in ALLOWED_URL_SCHEMES:
        return False, f"URL scheme must be {' or '.join(ALLOWED_URL_SCHEMES)}"
    
    # Check domain
    if not parsed.netloc:
        return False, "URL must have a valid domain"
    
    # Block local/private IPs unless explicitly allowed
    if not allow_local:
        domain_lower = parsed.netloc.lower()
        for blocked in BLOCKED_DOMAINS:
            if blocked in domain_lower:
                return False, "Local/private URLs are not allowed"
    
    # Check for suspicious patterns
    if '..' in url or url.count('//') > 1:
        return False, "URL contains suspicious patterns"
    
    return True, None


def validate_file_url(url: str, file_type: str = "image") -> Tuple[bool, Optional[str]]:
    """
    Validate file URL with extension check.
    
    Args:
        url: File URL to validate
        file_type: Expected file type (image/video/audio)
        
    Returns:
        (is_valid, error_message)
    """
    # First validate URL itself
    is_valid, error = validate_url(url)
    if not is_valid:
        return is_valid, error
    
    # Extract extension
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    # Find extension
    ext = None
    for possible_ext in ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS | ALLOWED_AUDIO_EXTENSIONS:
        if path.endswith(possible_ext):
            ext = possible_ext
            break
    
    if not ext:
        return False, f"File must have a valid {file_type} extension"
    
    # Check extension matches expected type
    if file_type == "image" and ext not in ALLOWED_IMAGE_EXTENSIONS:
        return False, f"Expected image file, got {ext}"
    elif file_type == "video" and ext not in ALLOWED_VIDEO_EXTENSIONS:
        return False, f"Expected video file, got {ext}"
    elif file_type == "audio" and ext not in ALLOWED_AUDIO_EXTENSIONS:
        return False, f"Expected audio file, got {ext}"
    
    return True, None


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and other attacks.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    if not filename:
        return "unnamed"
    
    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # Remove null bytes
    filename = filename.replace('\0', '')
    
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    
    # Replace problematic characters
    filename = re.sub(r'[<>:"|?*]', '_', filename)
    
    # Limit length
    if len(filename) > 255:
        filename = filename[:255]
    
    return filename or "unnamed"


def validate_text_input(text: str, max_length: int = 10000) -> Tuple[bool, Optional[str]]:
    """
    Validate text input for length and content.
    
    Args:
        text: Text to validate
        max_length: Maximum allowed length
        
    Returns:
        (is_valid, error_message)
    """
    if not text or not isinstance(text, str):
        return False, "Text must be a non-empty string"
    
    if len(text) > max_length:
        return False, f"Text is too long (max {max_length} characters)"
    
    # Check for null bytes
    if '\0' in text:
        return False, "Text contains invalid characters"
    
    return True, None


def validate_integer(value: str, min_val: Optional[int] = None, max_val: Optional[int] = None) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Validate and parse integer input.
    
    Args:
        value: String value to validate
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        
    Returns:
        (is_valid, error_message, parsed_value)
    """
    try:
        parsed = int(value)
    except (ValueError, TypeError):
        return False, "Must be a valid integer", None
    
    if min_val is not None and parsed < min_val:
        return False, f"Must be at least {min_val}", None
    
    if max_val is not None and parsed > max_val:
        return False, f"Must be at most {max_val}", None
    
    return True, None, parsed


def validate_float(value: str, min_val: Optional[float] = None, max_val: Optional[float] = None) -> Tuple[bool, Optional[str], Optional[float]]:
    """
    Validate and parse float input.
    
    Args:
        value: String value to validate
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        
    Returns:
        (is_valid, error_message, parsed_value)
    """
    try:
        parsed = float(value)
    except (ValueError, TypeError):
        return False, "Must be a valid number", None
    
    if min_val is not None and parsed < min_val:
        return False, f"Must be at least {min_val}", None
    
    if max_val is not None and parsed > max_val:
        return False, f"Must be at most {max_val}", None
    
    return True, None, parsed
