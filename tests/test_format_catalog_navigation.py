"""Test format-based catalog navigation."""
import pytest
from unittest.mock import MagicMock, patch
from aiogram.types import CallbackQuery
from bot.handlers.marketing import format_catalog_screen


@pytest.fixture
def mock_callback():
    """Mock Telegram callback query."""
    cb = MagicMock(spec=CallbackQuery)
    cb.answer = pytest.mock.AsyncMock()
    cb.message = MagicMock()
    cb.message.edit_text = pytest.mock.AsyncMock()
    cb.from_user = MagicMock(id=12345)
    return cb


@pytest.mark.asyncio
async def test_format_catalog_text_to_image(mock_callback):
    """Format catalog should show models for text-to-image format."""
    
    mock_callback.data = "format_catalog:text-to-image"
    
    with patch("bot.handlers.marketing.Path") as mock_path, \
         patch("bot.handlers.marketing.get_model") as mock_get_model, \
         patch("builtins.open", pytest.mock.mock_open(read_data='{"model_to_formats": {"z-image": ["text-to-image"], "flux-2/pro-text-to-image": ["text-to-image"]}}')):
        
        mock_path.return_value.exists.return_value = True
        
        # Mock models
        def mock_get(model_id):
            models = {
                "z-image": {"id": "z-image", "display_name": "Z-Image", "enabled": True},
                "flux-2/pro-text-to-image": {"id": "flux-2/pro-text-to-image", "display_name": "Flux Pro", "enabled": True}
            }
            return models.get(model_id)
        
        mock_get_model.side_effect = mock_get
        
        await format_catalog_screen(mock_callback)
        
        # Verify response
        assert mock_callback.message.edit_text.called
        call_args = mock_callback.message.edit_text.call_args
        text = call_args[0][0]
        
        assert "Текст → Изображение" in text
        assert "Найдено моделей: 2" in text


@pytest.mark.asyncio
async def test_format_catalog_image_to_video(mock_callback):
    """Format catalog should filter image-to-video models."""
    
    mock_callback.data = "format_catalog:image-to-video"
    
    with patch("bot.handlers.marketing.Path") as mock_path, \
         patch("bot.handlers.marketing.get_model") as mock_get_model, \
         patch("builtins.open", pytest.mock.mock_open(read_data='{"model_to_formats": {"sora-2-image-to-video": ["image-to-video"], "z-image": ["text-to-image"]}}')):
        
        mock_path.return_value.exists.return_value = True
        
        def mock_get(model_id):
            models = {
                "sora-2-image-to-video": {"id": "sora-2-image-to-video", "display_name": "Sora", "enabled": True},
                "z-image": {"id": "z-image", "display_name": "Z-Image", "enabled": True}
            }
            return models.get(model_id)
        
        mock_get_model.side_effect = mock_get
        
        await format_catalog_screen(mock_callback)
        
        call_args = mock_callback.message.edit_text.call_args
        text = call_args[0][0]
        
        # Only image-to-video model should be shown
        assert "Найдено моделей: 1" in text


@pytest.mark.asyncio
async def test_format_catalog_video_aggregate(mock_callback):
    """Format catalog 'video' should show all video-related formats."""
    
    mock_callback.data = "format_catalog:video"
    
    with patch("bot.handlers.marketing.Path") as mock_path, \
         patch("bot.handlers.marketing.get_model") as mock_get_model, \
         patch("builtins.open", pytest.mock.mock_open(read_data='{"model_to_formats": {"sora-2-text-to-video": ["text-to-video"], "sora-2-image-to-video": ["image-to-video"], "z-image": ["text-to-image"]}}')):
        
        mock_path.return_value.exists.return_value = True
        
        def mock_get(model_id):
            models = {
                "sora-2-text-to-video": {"id": "sora-2-text-to-video", "enabled": True},
                "sora-2-image-to-video": {"id": "sora-2-image-to-video", "enabled": True},
                "z-image": {"id": "z-image", "enabled": True}
            }
            return models.get(model_id)
        
        mock_get_model.side_effect = mock_get
        
        await format_catalog_screen(mock_callback)
        
        call_args = mock_callback.message.edit_text.call_args
        text = call_args[0][0]
        
        # Both video models should be shown
        assert "Найдено моделей: 2" in text


@pytest.mark.asyncio
async def test_format_catalog_no_models(mock_callback):
    """Format catalog should handle empty results gracefully."""
    
    mock_callback.data = "format_catalog:nonexistent-format"
    
    with patch("bot.handlers.marketing.Path") as mock_path, \
         patch("builtins.open", pytest.mock.mock_open(read_data='{"model_to_formats": {}}')):
        
        mock_path.return_value.exists.return_value = True
        
        await format_catalog_screen(mock_callback)
        
        call_args = mock_callback.message.edit_text.call_args
        text = call_args[0][0]
        
        assert "не найдены" in text
