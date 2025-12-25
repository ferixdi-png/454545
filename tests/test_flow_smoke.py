"""
Smoke tests for full user flow.
Tests: start → category → model → inputs → confirm → generation (stub)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, CallbackQuery, User, Chat, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers.flow import (
    start_cmd,
    main_menu_cb,
    category_cb,
    model_cb,
    generate_cb,
    confirm_cb,
    _is_valid_model,
    _models_by_category,
)


@pytest.fixture
def storage():
    """Create memory storage for FSM."""
    return MemoryStorage()


@pytest.fixture
def user():
    """Create mock user."""
    return User(id=123456, is_bot=False, first_name="Test")


@pytest.fixture
def chat():
    """Create mock chat."""
    return Chat(id=123456, type="private")


@pytest.fixture
def state(storage, user, chat):
    """Create FSM state context."""
    return FSMContext(
        storage=storage,
        key=f"{user.id}:{chat.id}"
    )


@pytest.fixture
def message(user, chat):
    """Create mock message."""
    msg = MagicMock(spec=Message)
    msg.from_user = user
    msg.chat = chat
    msg.message_id = 1
    msg.answer = AsyncMock()
    msg.edit_text = AsyncMock()
    msg.text = None
    msg.photo = None
    msg.document = None
    msg.video = None
    msg.audio = None
    return msg


@pytest.fixture
def callback(user, chat, message):
    """Create mock callback query."""
    cb = MagicMock(spec=CallbackQuery)
    cb.from_user = user
    cb.message = message
    cb.answer = AsyncMock()
    cb.data = ""
    return cb


def test_model_filtering():
    """Test that invalid models are filtered out."""
    # Valid models: vendor/name format AND pricing dict AND enabled
    assert _is_valid_model({
        "model_id": "flux/pro",
        "pricing": {"rub_per_use": 15.0, "usd_per_use": 0.2, "credits_per_use": 2.0},
        "enabled": True
    }) is True
    
    # Invalid: disabled
    assert _is_valid_model({
        "model_id": "kling/v1",
        "pricing": {"rub_per_use": 100.0, "usd_per_use": 1.0, "credits_per_use": 10.0},
        "enabled": False
    }) is False
    
    # Invalid: no pricing
    assert _is_valid_model({"model_id": "flux/pro", "enabled": True}) is False
    
    # Invalid: pricing is None
    assert _is_valid_model({"model_id": "flux/pro", "pricing": None, "enabled": True}) is False
    
    # Invalid: empty pricing dict
    assert _is_valid_model({"model_id": "flux/pro", "pricing": {}, "enabled": True}) is False
    assert _is_valid_model({"model_id": "ARCHITECTURE", "price": 10.0}) is False
    assert _is_valid_model({"model_id": "image_processor", "price": 10.0}) is False
    assert _is_valid_model({"model_id": "", "price": 10.0}) is False
    assert _is_valid_model({}) is False


def test_models_by_category():
    """Test that models are grouped by category and filtered."""
    grouped = _models_by_category()
    
    # Should have some categories
    assert len(grouped) > 0
    
    # All models should be valid
    for category, models in grouped.items():
        for model in models:
            assert _is_valid_model(model)
            assert model.get("category") == category or model.get("category") is None


@pytest.mark.asyncio
async def test_start_command(message, state):
    """Test /start command."""
    await start_cmd(message, state)
    
    # Should answer with welcome message
    assert message.answer.called
    call_args = message.answer.call_args
    # Updated canonical text
    assert "создать сегодня" in call_args[0][0] or "нейросеть" in call_args[0][0]
    
    # Should have keyboard
    assert "reply_markup" in call_args[1]


@pytest.mark.asyncio
async def test_main_menu(callback, state):
    """Test main menu callback."""
    callback.data = "main_menu"
    await main_menu_cb(callback, state)
    
    # Should answer callback
    assert callback.answer.called
    
    # Should edit message
    assert callback.message.edit_text.called
    call_args = callback.message.edit_text.call_args
    assert "Главное меню" in call_args[0][0]


@pytest.mark.asyncio
async def test_category_flow(callback, state):
    """Test category selection."""
    # Get first valid category
    grouped = _models_by_category()
    if not grouped:
        pytest.skip("No valid categories in registry")
    
    category = list(grouped.keys())[0]
    callback.data = f"cat:{category}"
    
    await category_cb(callback, state)
    
    # Should answer
    assert callback.answer.called
    
    # Should edit message with models
    assert callback.message.edit_text.called
    call_args = callback.message.edit_text.call_args
    assert "Выберите модель" in call_args[0][0]


@pytest.mark.asyncio
async def test_model_selection(callback, state):
    """Test model selection."""
    # Get first valid model
    grouped = _models_by_category()
    if not grouped:
        pytest.skip("No valid models in registry")
    
    first_category = list(grouped.keys())[0]
    models = grouped[first_category]
    if not models:
        pytest.skip("No models in first category")
    
    model_id = models[0].get("model_id")
    callback.data = f"model:{model_id}"
    
    # Set category in state
    await state.update_data(category=first_category)
    
    await model_cb(callback, state)
    
    # Should answer
    assert callback.answer.called
    
    # Should show model details
    assert callback.message.edit_text.called
    call_args = callback.message.edit_text.call_args
    text = call_args[0][0]
    # Should contain some model info
    assert len(text) > 0


@pytest.mark.asyncio
async def test_generation_no_inputs(callback, state):
    """Test generation for model with no required inputs."""
    # Find model with no required inputs
    grouped = _models_by_category()
    target_model = None
    
    for category, models in grouped.items():
        for model in models:
            schema = model.get("input_schema", {})
            required = schema.get("required", [])
            if not required:
                target_model = model
                break
        if target_model:
            break
    
    if not target_model:
        pytest.skip("No model without required inputs")
    
    model_id = target_model.get("model_id")
    callback.data = f"gen:{model_id}"
    
    await generate_cb(callback, state)
    
    # Should answer
    assert callback.answer.called
    
    # Should show confirmation (since no inputs needed)
    # Check state or message was called
    assert callback.message.answer.called or callback.message.edit_text.called


@pytest.mark.asyncio
async def test_confirm_insufficient_balance(callback, state):
    """Test confirmation with insufficient balance."""
    # Get a model
    grouped = _models_by_category()
    if not grouped:
        pytest.skip("No models")
    
    first_category = list(grouped.keys())[0]
    models = grouped[first_category]
    if not models:
        pytest.skip("No models in category")
    
    model = models[0]
    model_id = model.get("model_id")
    
    # Set state
    from bot.handlers.flow import InputContext
    ctx = InputContext(
        model_id=model_id,
        required_fields=[],
        optional_fields=[],
        properties={},
        collected={},
        collecting_optional=False
    )
    await state.update_data(flow_ctx=ctx.__dict__)
    
    callback.data = "confirm"
    
    # Mock model to have price > user balance
    # User has WELCOME_BALANCE_RUB (200) by default
    # Set Kie price to 150 => user price = 300 (x2 markup)
    with patch("bot.handlers.flow._source_of_truth") as mock_sot:
        mock_sot.return_value = {
            "models": [{
                **model,
                "price": 150.0  # Kie cost 150 => user pays 300 RUB
            }]
        }
        
        # Force user balance to 100 (less than 300)
        from app.payments.charges import get_charge_manager
        charge_mgr = get_charge_manager()
        charge_mgr._balances[callback.from_user.id] = 100.0
        
        await confirm_cb(callback, state)
    
    # Should answer
    assert callback.answer.called
    
    # Should show insufficient funds message
    assert callback.message.edit_text.called
    call_args = callback.message.edit_text.call_args
    text = call_args[0][0]
    assert "Недостаточно средств" in text or "недостаточно" in text.lower()


@pytest.mark.asyncio
async def test_confirm_with_balance(callback, state):
    """Test confirmation with sufficient balance (stub generation)."""
    # Get a model
    grouped = _models_by_category()
    if not grouped:
        pytest.skip("No models")
    
    first_category = list(grouped.keys())[0]
    models = grouped[first_category]
    if not models:
        pytest.skip("No models in category")
    
    model = models[0]
    model_id = model.get("model_id")
    
    # Set state
    from bot.handlers.flow import InputContext
    ctx = InputContext(
        model_id=model_id,
        required_fields=[],
        optional_fields=[],
        properties={},
        collected={},
        collecting_optional=False
    )
    await state.update_data(flow_ctx=ctx.__dict__)
    
    callback.data = "confirm"
    
    # Give user balance
    from app.payments.charges import get_charge_manager
    mgr = get_charge_manager()
    mgr.adjust_balance(callback.from_user.id, 1000.0)
    
    # Mock generation to succeed
    with patch("bot.handlers.flow.generate_with_payment") as mock_gen:
        mock_gen.return_value = {
            "success": True,
            "result_urls": ["https://example.com/result.jpg"],
            "message": "Success"
        }
        
        await confirm_cb(callback, state)
    
    # Should answer
    assert callback.answer.called
    
    # Should start generation
    assert mock_gen.called
    
    # Should send result
    assert callback.message.answer.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
