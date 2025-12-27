"""Test file upload support for *_URL fields in wizard."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, PhotoSize, Document, Video, Audio, Voice
from aiogram.fsm.context import FSMContext
from bot.flows.wizard import wizard_process_input
from bot.flows.input_parser import InputType


@pytest.fixture
def mock_message():
    """Mock Telegram message."""
    msg = MagicMock(spec=Message)
    msg.from_user = MagicMock(id=12345, first_name="Test")
    msg.text = None
    msg.photo = None
    msg.document = None
    msg.video = None
    msg.audio = None
    msg.voice = None
    msg.answer = AsyncMock()
    msg.edit_text = AsyncMock()
    return msg


@pytest.fixture
def mock_state():
    """Mock FSM state."""
    state = MagicMock(spec=FSMContext)
    state.get_data = AsyncMock(return_value={
        "wizard_spec": MagicMock(fields=[
            MagicMock(name="image_url", type=InputType.IMAGE_URL, required=True)
        ]),
        "wizard_current_field_index": 0,
        "wizard_inputs": {},
        "model_config": {"id": "test-model"}
    })
    state.update_data = AsyncMock()
    return state


@pytest.mark.asyncio
async def test_image_url_accepts_photo_upload(mock_message, mock_state):
    """IMAGE_URL field should accept photo uploads and generate signed URL."""
    
    # Mock photo upload
    mock_photo = MagicMock(spec=PhotoSize)
    mock_photo.file_id = "PHOTO_FILE_ID_123"
    mock_message.photo = [mock_photo]
    
    with patch("bot.flows.wizard.sign_media_url", return_value="signed_url_token"), \
         patch("app.utils.config.get_config") as mock_config:
        
        mock_cfg = MagicMock()
        mock_cfg.base_url = "https://example.com"
        mock_config.return_value = mock_cfg
        
        await wizard_process_input(mock_message, mock_state)
        
        # Verify state was updated with signed URL
        update_call = mock_state.update_data.call_args
        inputs = update_call[1]["wizard_inputs"]
        
        assert "image_url" in inputs
        assert "https://example.com/media/telegram/PHOTO_FILE_ID_123" in inputs["image_url"]
        assert "sig=signed_url_token" in inputs["image_url"]


@pytest.mark.asyncio
async def test_video_url_accepts_video_upload(mock_message, mock_state):
    """VIDEO_URL field should accept video uploads."""
    
    mock_video = MagicMock(spec=Video)
    mock_video.file_id = "VIDEO_FILE_ID_456"
    mock_message.video = mock_video
    
    # Update state for VIDEO_URL field
    mock_state.get_data = AsyncMock(return_value={
        "wizard_spec": MagicMock(fields=[
            MagicMock(name="video_url", type=InputType.VIDEO_URL, required=True)
        ]),
        "wizard_current_field_index": 0,
        "wizard_inputs": {},
        "model_config": {"id": "test-model"}
    })
    
    with patch("bot.flows.wizard.sign_media_url", return_value="video_sig"), \
         patch("app.utils.config.get_config") as mock_config:
        
        mock_cfg = MagicMock()
        mock_cfg.base_url = "https://example.com"
        mock_config.return_value = mock_cfg
        
        await wizard_process_input(mock_message, mock_state)
        
        update_call = mock_state.update_data.call_args
        inputs = update_call[1]["wizard_inputs"]
        
        assert "video_url" in inputs
        assert "VIDEO_FILE_ID_456" in inputs["video_url"]


@pytest.mark.asyncio
async def test_url_field_accepts_http_text(mock_message, mock_state):
    """*_URL fields should accept direct http(s) URLs as text."""
    
    mock_message.text = "https://example.com/my-image.png"
    
    await wizard_process_input(mock_message, mock_state)
    
    update_call = mock_state.update_data.call_args
    inputs = update_call[1]["wizard_inputs"]
    
    assert inputs["image_url"] == "https://example.com/my-image.png"


@pytest.mark.asyncio
async def test_url_field_fallback_no_base_url(mock_message, mock_state):
    """If BASE_URL not configured, show error asking for URL."""
    
    mock_photo = MagicMock(spec=PhotoSize)
    mock_photo.file_id = "PHOTO_123"
    mock_message.photo = [mock_photo]
    
    with patch("bot.flows.wizard.sign_media_url", return_value="sig"), \
         patch("app.utils.config.get_config") as mock_config:
        
        mock_cfg = MagicMock()
        mock_cfg.base_url = None  # Not configured
        mock_config.return_value = mock_cfg
        
        await wizard_process_input(mock_message, mock_state)
        
        # Should send error message
        assert mock_message.answer.called
        error_text = mock_message.answer.call_args[0][0]
        assert "недоступна" in error_text.lower()
        assert "ссылку" in error_text.lower()


@pytest.mark.asyncio
async def test_audio_url_accepts_document_with_mime(mock_message, mock_state):
    """AUDIO_URL should accept document with audio/* MIME type."""
    
    mock_doc = MagicMock(spec=Document)
    mock_doc.file_id = "AUDIO_DOC_789"
    mock_doc.mime_type = "audio/mpeg"
    mock_message.document = mock_doc
    
    mock_state.get_data = AsyncMock(return_value={
        "wizard_spec": MagicMock(fields=[
            MagicMock(name="audio_url", type=InputType.AUDIO_URL, required=True)
        ]),
        "wizard_current_field_index": 0,
        "wizard_inputs": {},
        "model_config": {"id": "test-model"}
    })
    
    with patch("bot.flows.wizard.sign_media_url", return_value="audio_sig"), \
         patch("app.utils.config.get_config") as mock_config:
        
        mock_cfg = MagicMock()
        mock_cfg.base_url = "https://example.com"
        mock_config.return_value = mock_cfg
        
        await wizard_process_input(mock_message, mock_state)
        
        update_call = mock_state.update_data.call_args
        inputs = update_call[1]["wizard_inputs"]
        
        assert "audio_url" in inputs
        assert "AUDIO_DOC_789" in inputs["audio_url"]
