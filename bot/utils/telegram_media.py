"""Robust Telegram media extraction utilities.

Handles all edge cases:
- Photo arrays (choose highest resolution)
- Documents with images
- Video notes and voice messages
- Forwarded messages
- Multiple media types in one message
"""
from typing import Optional
from aiogram.types import Message


def extract_image_file_id(message: Message) -> Optional[str]:
    """Extract image file_id from message (photo or document with image MIME)."""
    # Photo (array of sizes)
    if message.photo:
        # Choose highest resolution (last in array)
        return message.photo[-1].file_id
    
    # Document with image MIME
    if message.document and message.document.mime_type:
        if message.document.mime_type.startswith("image/"):
            return message.document.file_id
    
    return None


def extract_video_file_id(message: Message) -> Optional[str]:
    """Extract video file_id from message."""
    if message.video:
        return message.video.file_id
    
    # Video note (round video)
    if message.video_note:
        return message.video_note.file_id
    
    # Document with video MIME
    if message.document and message.document.mime_type:
        if message.document.mime_type.startswith("video/"):
            return message.document.file_id
    
    return None


def extract_audio_file_id(message: Message) -> Optional[str]:
    """Extract audio file_id from message (audio, voice, or document)."""
    if message.audio:
        return message.audio.file_id
    
    if message.voice:
        return message.voice.file_id
    
    # Document with audio MIME
    if message.document and message.document.mime_type:
        if message.document.mime_type.startswith("audio/"):
            return message.document.file_id
    
    return None


def extract_text(message: Message) -> Optional[str]:
    """Extract text from message (text, caption, or None)."""
    # Priority: text > caption
    if message.text:
        return message.text.strip()
    
    if message.caption:
        return message.caption.strip()
    
    return None


def get_media_type(message: Message) -> Optional[str]:
    """Detect primary media type in message.
    
    Returns: 'image' | 'video' | 'audio' | 'text' | None
    """
    if extract_image_file_id(message):
        return "image"
    
    if extract_video_file_id(message):
        return "video"
    
    if extract_audio_file_id(message):
        return "audio"
    
    if extract_text(message):
        return "text"
    
    return None


def explain_expected_input(format_type: str, input_name: str) -> str:
    """Generate user-friendly explanation for expected input type."""
    format_lower = format_type.lower()
    
    if "image" in format_lower or "photo" in format_lower:
        return f"📸 Пришли фото для поля «{input_name}»"
    
    if "video" in format_lower:
        return f"🎥 Пришли видео для поля «{input_name}»"
    
    if "audio" in format_lower:
        return f"🎵 Пришли аудио для поля «{input_name}»"
    
    if "text" in format_lower or "prompt" in format_lower:
        return f"✍️ Напиши текст для поля «{input_name}»"
    
    return f"Отправь {format_type} для поля «{input_name}»"
