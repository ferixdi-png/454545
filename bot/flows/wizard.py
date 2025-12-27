"""Wizard flow for guided model input."""
import logging
import hmac
import hashlib
import os
from typing import Dict, List, Optional, Any
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.ui.input_spec import get_input_spec, InputType
from bot.flows.wizard_presets import (
    get_presets_for_format,
    get_preset_by_id,
    detect_model_format,
)

logger = logging.getLogger(__name__)
router = Router(name="wizard")


class WizardState(StatesGroup):
    """Wizard FSM states."""
    collecting_input = State()
    confirming = State()


def _sign_file_id(file_id: str) -> str:
    """Sign file ID for secure media proxy."""
    secret = os.getenv("MEDIA_PROXY_SECRET", "default_proxy_secret_change_me")
    signature = hmac.new(secret.encode(), file_id.encode(), hashlib.sha256).hexdigest()[:16]
    return signature


def _get_public_base_url() -> str:
    """Get PUBLIC_BASE_URL for media proxy."""
    return os.getenv("PUBLIC_BASE_URL", os.getenv("WEBHOOK_BASE_URL", "https://unknown.render.com")).rstrip("/")


# Wizard start handler (callback: wizard:start:<model_id>)
@router.callback_query(F.data.startswith("wizard:start:"))
async def wizard_start_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Start wizard from callback."""
    model_id = callback.data.split(":", 2)[2]
    
    from app.ui.catalog import get_model
    model = get_model(model_id)
    
    if not model:
        await callback.answer("❌ Модель не найдена", show_alert=True)
        return
    
    await start_wizard(callback, state, model)


# Try example handler (callback: wizard:example:<model_id>)
@router.callback_query(F.data.startswith("wizard:example:"))
async def wizard_example_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Start wizard with example prompt filled in."""
    model_id = callback.data.split(":", 2)[2]
    
    from app.ui.catalog import get_model
    from app.ui.model_profile import build_profile
    
    model = get_model(model_id)
    if not model:
        await callback.answer("❌ Модель не найдена", show_alert=True)
        return
    
    profile = build_profile(model)
    example_prompt = None
    
    if profile.get('examples'):
        example_prompt = profile['examples'][0]  # Use first example
    
    # Start wizard with pre-filled example
    await start_wizard(callback, state, model, prefill_prompt=example_prompt)


async def start_wizard(
    callback: CallbackQuery,
    state: FSMContext,
    model_config: Dict[str, Any],
    prefill_prompt: Optional[str] = None,
) -> None:
    """
    Start wizard flow for model input.
    
    Args:
        callback: Callback query that triggered wizard
        model_config: Model configuration from KIE_SOURCE_OF_TRUTH
        prefill_prompt: Optional pre-filled prompt (for examples)
    """
    await callback.answer()
    
    model_id = model_config.get("model_id", "unknown")
    display_name = model_config.get("display_name", model_id)
    
    # Get input spec
    spec = get_input_spec(model_config)
    
    if not spec.fields:
        # No inputs needed, go straight to generation
        await callback.message.edit_text(
            f"🚀 <b>{display_name}</b>\n\n"
            "Запускаю генерацию...",
            parse_mode="HTML"
        )
        
        # Save state and trigger generation
        await state.update_data(
            model_id=model_id,
            model_config=model_config,
            wizard_inputs={}
        )
        
        # Import and call generator
        from bot.handlers.flow import trigger_generation
        await trigger_generation(callback.message, state)
        return
    
    # Prefill if provided
    initial_inputs = {}
    if prefill_prompt and spec.fields:
        # Try to fill first text field with example
        for field in spec.fields:
            if field.type == InputType.TEXT and field.name in ["prompt", "text", "description"]:
                initial_inputs[field.name] = prefill_prompt
                break
    
    # Save wizard state
    await state.update_data(
        model_id=model_id,
        model_config=model_config,
        wizard_spec=spec,
        wizard_inputs=initial_inputs,
        wizard_current_field_index=0,
    )
    
    # Show overview screen FIRST (what inputs are needed)
    await show_wizard_overview(callback.message, state, spec, model_config)
    await state.set_state(WizardState.collecting_input)


async def show_wizard_overview(message: Message, state: FSMContext, spec, model_config: Dict) -> None:
    """
    Show wizard overview - what inputs will be collected.
    
    Args:
        message: Message to edit
        state: FSM state
        spec: InputSpec object
        model_config: Model configuration
    """
    from app.ui import tone_ru
    from app.ui.profile import build_profile
    
    model_id = model_config.get("model_id", "unknown")
    display_name = model_config.get("display_name", model_id)
    profile = build_profile(model_config)
    
    # Build checklist of required inputs
    input_emojis = {
        InputType.TEXT: "✍️",
        InputType.IMAGE_URL: "🖼",
        InputType.IMAGE_FILE: "🖼",
        InputType.VIDEO_URL: "🎬",
        InputType.VIDEO_FILE: "🎬",
        InputType.AUDIO_URL: "🎙",
        InputType.AUDIO_FILE: "🎙",
        InputType.NUMBER: "🔢",
        InputType.ENUM: "📋",
        InputType.BOOLEAN: "✅",
    }
    
    text = tone_ru.WIZARD_OVERVIEW_TITLE.format(model_name=display_name)
    
    for idx, field in enumerate(spec.fields, 1):
        emoji = input_emojis.get(field.type, "📝")
        required_mark = "" if field.required else " (опционально)"
        text += f"\\n{idx}. {emoji} <b>{field.description or field.name}</b>{required_mark}"
    
    # Show price info
    price_label = profile.get("price", {}).get("label", "—")
    text += f"\\n\\n💰 <b>Цена:</b> {price_label}"
    
    # Presets if available
    model_format = detect_model_format(model_config)
    presets = get_presets_for_format(model_format) if model_format else []
    
    text += "\\n\\n👇 Выберите действие:"
    
    # Build keyboard
    buttons = []
    
    # Presets button if available
    if presets:
        buttons.append([InlineKeyboardButton(
            text=tone_ru.WIZARD_PRESETS_BTN,
            callback_data=f"wizard:presets:{model_id}"
        )])
    
    # Start collecting
    buttons.append([InlineKeyboardButton(
        text=tone_ru.WIZARD_START_BTN,
        callback_data="wizard:start_collecting"
    )])
    
    # Navigation
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"card:{model_id}"),
        InlineKeyboardButton(text="🏠 В меню", callback_data="menu:main"),
    ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    try:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "wizard:start_collecting")
async def wizard_start_collecting_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Start collecting inputs after overview."""
    await callback.answer()
    
    data = await state.get_data()
    spec = data.get("wizard_spec")
    
    if not spec or not spec.fields:
        await callback.message.edit_text("❌ Ошибка: спецификация не найдена", parse_mode="HTML")
        return
    
    # Show first field
    await show_field_input(callback.message, state, spec.fields[0])


@router.callback_query(F.data.startswith("wizard:presets:"))
async def wizard_show_presets(callback: CallbackQuery, state: FSMContext) -> None:
    """Show presets for model."""
    await callback.answer()
    
    model_id = callback.data.split(":", 2)[2]
    
    from app.ui.catalog import get_model
    model = get_model(model_id)
    
    if not model:
        await callback.message.edit_text("❌ Модель не найдена", parse_mode="HTML")
        return
    
    # Detect format
    model_format = detect_model_format(model)
    if not model_format:
        await callback.answer("Пресеты недоступны для этой модели", show_alert=True)
        return
    
    presets = get_presets_for_format(model_format)
    
    if not presets:
        await callback.answer("Пресеты не найдены", show_alert=True)
        return
    
    # Show presets
    text = (
        f"🔥 <b>Готовые пресеты</b>\\n\\n"
        f"Выберите шаблон для быстрого старта:"
    )
    
    buttons = []
    for preset in presets:
        buttons.append([InlineKeyboardButton(
            text=preset["name"],
            callback_data=f"wizard:use_preset:{preset['id']}"
        )])
    
    # Back
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=f"wizard:start:{model_id}"
    )])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("wizard:use_preset:"))
async def wizard_use_preset(callback: CallbackQuery, state: FSMContext) -> None:
    """Use preset prompt."""
    await callback.answer()
    
    preset_id = callback.data.split(":", 2)[2]
    preset = get_preset_by_id(preset_id)
    
    if not preset:
        await callback.answer("❌ Пресет не найден", show_alert=True)
        return
    
    # Get wizard state
    data = await state.get_data()
    spec = data.get("wizard_spec")
    
    if not spec:
        await callback.message.edit_text("❌ Ошибка: спецификация не найдена", parse_mode="HTML")
        return
    
    # Fill first text field with preset prompt
    preset_prompt = preset.get("prompt", "")
    wizard_inputs = data.get("wizard_inputs", {})
    
    for field in spec.fields:
        if field.type == InputType.TEXT and field.name in ["prompt", "text", "description"]:
            wizard_inputs[field.name] = preset_prompt
            break
    
    await state.update_data(wizard_inputs=wizard_inputs)
    
    # Show confirmation
    await callback.message.edit_text(
        f"✅ Применён пресет:\\n<b>{preset['name']}</b>\\n\\n"
        f"<i>{preset_prompt}</i>\\n\\n"
        f"Продолжаем сбор остальных параметров...",
        parse_mode="HTML"
    )
    
    # Continue with next field or confirmation
    current_idx = 0
    # Find first unfilled required field
    for idx, field in enumerate(spec.fields):
        if field.name not in wizard_inputs and field.required:
            current_idx = idx
            break
    
    if current_idx < len(spec.fields):
        await state.update_data(wizard_current_field_index=current_idx)
        await show_field_input(callback.message, state, spec.fields[current_idx])
    else:
        # All fields filled, show confirmation
        from bot.handlers.flow import wizard_show_confirmation
        await wizard_show_confirmation(callback, state)


async def show_field_input(message: Message, state: FSMContext, field) -> None:
    """
    Show input prompt for a field.
    
    Args:
        message: Message to edit
        state: FSM state
        field: InputField object
    """
    data = await state.get_data()
    model_config = data.get("model_config", {})
    display_name = model_config.get("display_name", "Модель")
    spec = data.get("wizard_spec")
    current_idx = data.get("wizard_current_field_index", 0)
    
    # Calculate step number
    total_fields = len(spec.fields) if spec else 1
    step_num = current_idx + 1
    
    # Build field description
    field_emoji = {
        InputType.TEXT: "✍️",
        InputType.IMAGE_URL: "🖼",
        InputType.IMAGE_FILE: "🖼",
        InputType.VIDEO_URL: "🎬",
        InputType.VIDEO_FILE: "🎬",
        InputType.AUDIO_URL: "🎙",
        InputType.AUDIO_FILE: "🎙",
        InputType.NUMBER: "🔢",
        InputType.ENUM: "📋",
        InputType.BOOLEAN: "✅",
    }.get(field.type, "📝")
    
    # Educational header
    text = (
        f"🧠 <b>{display_name}</b>  •  Шаг {step_num}/{total_fields}\n\n"
        f"{field_emoji} <b>{field.description or field.name}</b>\n\n"
    )
    
    if field.example:
        text += f"💡 <b>Пример:</b> <i>{field.example}</i>\n\n"
    
    if field.enum_values:
        text += "<b>Варианты:</b>\n"
        for val in field.enum_values:
            text += f"• {val}\n"
        text += "\n"
    
    if field.type == InputType.NUMBER:
        if field.min_value is not None and field.max_value is not None:
            text += f"📊 Диапазон: {field.min_value}–{field.max_value}\n\n"
        if field.default is not None:
            text += f"По умолчанию: {field.default}\n\n"
    
    # Format-specific hints (улучшенные - "файл ИЛИ ссылка")
    if field.type in [InputType.IMAGE_FILE, InputType.VIDEO_FILE, InputType.AUDIO_FILE]:
        text += "📎 Загрузите файл из галереи\n\n"
    elif field.type in [InputType.IMAGE_URL, InputType.VIDEO_URL, InputType.AUDIO_URL]:
        text += "📎 Загрузите файл ИЛИ отправьте ссылку\n\n"
    elif field.type == InputType.TEXT:
        text += "✍️ Опишите что хотите получить\n\n"
    
    text += "👇 Отправь ответ:"
    
    # Build keyboard
    buttons = []
    
    # Skip button for optional fields
    if not field.required:
        buttons.append([InlineKeyboardButton(text="⏭ Пропустить", callback_data="wizard:skip")])
    
    # Use default button if available
    if field.default is not None:
        buttons.append([InlineKeyboardButton(
            text=f"✨ Использовать по умолчанию ({field.default})",
            callback_data="wizard:use_default"
        )])
    
    # Navigation
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="wizard:back"),
        InlineKeyboardButton(text="🏠 В меню", callback_data="menu:main"),
    ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    try:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "wizard:skip", WizardState.collecting_input)
async def wizard_skip_field(callback: CallbackQuery, state: FSMContext) -> None:
    """Skip optional field."""
    await callback.answer()
    
    data = await state.get_data()
    spec = data.get("wizard_spec")
    current_index = data.get("wizard_current_field_index", 0)
    
    if current_index >= len(spec.fields):
        await wizard_show_confirmation(callback, state)
        return
    
    current_field = spec.fields[current_index]
    
    if current_field.required:
        await callback.answer("❌ Это поле обязательно!", show_alert=True)
        return
    
    # Move to next field
    next_index = current_index + 1
    await state.update_data(wizard_current_field_index=next_index)
    
    if next_index >= len(spec.fields):
        await wizard_show_confirmation(callback, state)
    else:
        await show_field_input(callback.message, state, spec.fields[next_index])


@router.callback_query(F.data == "wizard:use_default", WizardState.collecting_input)
async def wizard_use_default(callback: CallbackQuery, state: FSMContext) -> None:
    """Use default value for field."""
    await callback.answer()
    
    data = await state.get_data()
    spec = data.get("wizard_spec")
    current_index = data.get("wizard_current_field_index", 0)
    inputs = data.get("wizard_inputs", {})
    
    if current_index >= len(spec.fields):
        return
    
    current_field = spec.fields[current_index]
    
    if current_field.default is None:
        await callback.answer("❌ Нет значения по умолчанию", show_alert=True)
        return
    
    # Save default value
    inputs[current_field.name] = current_field.default
    
    # Move to next field
    next_index = current_index + 1
    await state.update_data(
        wizard_inputs=inputs,
        wizard_current_field_index=next_index
    )
    
    if next_index >= len(spec.fields):
        await wizard_show_confirmation(callback, state)
    else:
        await show_field_input(callback.message, state, spec.fields[next_index])


@router.callback_query(F.data == "wizard:back", WizardState.collecting_input)
async def wizard_go_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Go back to previous field."""
    await callback.answer()
    
    data = await state.get_data()
    current_index = data.get("wizard_current_field_index", 0)
    
    if current_index <= 0:
        # Go back to model card
        await state.clear()
        model_id = data.get("model_id")
        
        # Show model card again
        from bot.handlers.formats import show_model_card
        await show_model_card(callback, model_id)
        return
    
    # Go to previous field
    spec = data.get("wizard_spec")
    prev_index = current_index - 1
    await state.update_data(wizard_current_field_index=prev_index)
    await show_field_input(callback.message, state, spec.fields[prev_index])


@router.message(WizardState.collecting_input)
async def wizard_process_input(message: Message, state: FSMContext) -> None:
    """Process user input for current field (text or file upload)."""
    data = await state.get_data()
    spec = data.get("wizard_spec")
    current_index = data.get("wizard_current_field_index", 0)
    inputs = data.get("wizard_inputs", {})
    
    if current_index >= len(spec.fields):
        return
    
    current_field = spec.fields[current_index]
    
    # Handle file uploads (IMAGE_FILE, VIDEO_FILE, AUDIO_FILE, IMAGE_URL, VIDEO_URL, AUDIO_URL)
    if current_field.type in (InputType.IMAGE_FILE, InputType.VIDEO_FILE, InputType.AUDIO_FILE, 
                              InputType.IMAGE_URL, InputType.VIDEO_URL, InputType.AUDIO_URL):
        file_id = None
        
        # Check for IMAGE
        if current_field.type in (InputType.IMAGE_FILE, InputType.IMAGE_URL):
            if message.photo:
                file_id = message.photo[-1].file_id
            elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
                file_id = message.document.file_id
        
        # Check for VIDEO
        elif current_field.type in (InputType.VIDEO_FILE, InputType.VIDEO_URL):
            if message.video:
                file_id = message.video.file_id
            elif message.document and message.document.mime_type and message.document.mime_type.startswith("video/"):
                file_id = message.document.file_id
        
        # Check for AUDIO
        elif current_field.type in (InputType.AUDIO_FILE, InputType.AUDIO_URL):
            if message.audio:
                file_id = message.audio.file_id
            elif message.voice:
                file_id = message.voice.file_id
            elif message.document and message.document.mime_type and message.document.mime_type.startswith("audio/"):
                file_id = message.document.file_id
        
        if file_id:
            # Generate signed URL for media proxy
            base_url = _get_public_base_url()
            if base_url and base_url != "https://unknown.render.com":
                sig = _sign_file_id(file_id)
                media_url = f"{base_url}/media/telegram/{file_id}?sig={sig}"
                
                # Save URL (will be passed to KIE API)
                inputs[current_field.name] = media_url
                
                # Acknowledge upload
                await message.answer(
                    f"✅ <b>Файл принят!</b>\n\n"
                    f"📎 {current_field.description or current_field.name}",
                    parse_mode="HTML"
                )
            else:
                # Fallback: no BASE_URL configured, ask for URL
                await message.answer(
                    f"⚠️ <b>Загрузка файлов недоступна</b>\n\n"
                    f"Пришлите прямую ссылку на {current_field.description or current_field.name}:",
                    parse_mode="HTML"
                )
                return
        elif message.text and message.text.startswith(("http://", "https://")):
            # User sent URL as text - accept it
            inputs[current_field.name] = message.text
            await message.answer(
                f"✅ <b>Ссылка принята!</b>\n\n"
                f"🔗 {current_field.description or current_field.name}",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ <b>Неверный формат</b>\n\n"
                f"Ожидается: файл ИЛИ ссылка\n\n"
                f"📎 Загрузите файл или отправьте http(s) URL",
                parse_mode="HTML"
            )
            return
    else:
        # Text input
        user_input = message.text
        
        if not user_input:
            await message.answer("❌ Пустой ввод. Попробуйте снова.", parse_mode="HTML")
            return
        
        # Validate input
        is_valid, error = current_field.validate(user_input)
        
        if not is_valid:
            await message.answer(
                f"❌ <b>Ошибка валидации:</b>\n{error}\n\n"
                "Попробуйте снова:",
                parse_mode="HTML"
            )
            return
        
        # Save input
        inputs[current_field.name] = user_input
    
    # Move to next field
    next_index = current_index + 1
    await state.update_data(
        wizard_inputs=inputs,
        wizard_current_field_index=next_index
    )
    
    if next_index >= len(spec.fields):
        await wizard_show_confirmation(message, state)
    else:
        await show_field_input(message, state, spec.fields[next_index])


async def wizard_show_confirmation(message_or_callback, state: FSMContext) -> None:
    """Show confirmation screen with summary."""
    data = await state.get_data()
    model_config = data.get("model_config", {})
    inputs = data.get("wizard_inputs", {})
    
    model_id = model_config.get("model_id", "unknown")
    display_name = model_config.get("display_name", model_id)
    
    # Get price
    pricing = model_config.get("pricing", {})
    price_rub = pricing.get("rub_per_use", 0)
    is_free = pricing.get("is_free", False)
    
    # Build summary
    text = (
        f"✅ <b>Подтверждение запуска</b>\n\n"
        f"🎯 <b>Модель:</b> {display_name}\n\n"
        f"<b>Параметры:</b>\n"
    )
    
    for field_name, value in inputs.items():
        text += f"• {field_name}: {value}\n"
    
    text += "\n"
    
    if is_free:
        text += "🆓 <b>Бесплатно</b>\n\n"
    else:
        text += f"💰 <b>Стоимость:</b> {price_rub:.2f} ₽\n\n"
    
    text += "🚀 Всё готово к запуску!"
    
    buttons = [
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="wizard:confirm")],
        [InlineKeyboardButton(text="✏️ Изменить", callback_data="wizard:edit")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="menu:main")],
    ]
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await state.set_state(WizardState.confirming)
    
    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message_or_callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "wizard:confirm", WizardState.confirming)
async def wizard_confirm_and_generate(callback: CallbackQuery, state: FSMContext) -> None:
    """Confirm and start generation."""
    await callback.answer()
    
    data = await state.get_data()
    model_config = data.get("model_config", {})
    inputs = data.get("wizard_inputs", {})
    
    model_id = model_config.get("model_id", "unknown")
    display_name = model_config.get("display_name", model_id)
    
    # Show "starting..." message
    await callback.message.edit_text(
        f"🚀 <b>{display_name}</b>\n\n"
        "Запускаю генерацию...",
        parse_mode="HTML"
    )
    
    # Build payload from inputs
    payload = dict(inputs)  # Copy wizard inputs
    
    # Add defaults from schema if missing
    schema = model_config.get("input_schema", {})
    properties = schema.get("properties", {})
    
    for field_name, field_spec in properties.items():
        if field_name not in payload and "default" in field_spec:
            payload[field_name] = field_spec["default"]
    
    # Save generation context
    await state.update_data(
        model_id=model_id,
        payload=payload,
        is_free_selected=False,  # Will be determined by pricing
    )
    
    # Clear wizard state
    await state.clear()
    
    # Trigger generation via payment integration
    # Note: payload arg kept for backward compat in integration.py
    from app.payments.integration import generate_with_payment
    from app.payments.charges import get_charge_manager
    
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    try:
        cm = get_charge_manager()
        
        result = await generate_with_payment(
            user_id=user_id,
            model_id=model_id,
            user_inputs=payload,
            amount=0.0,  # Will be calculated inside
            charge_manager=cm,
        )
        
        # Send result
        if result.get("success"):
            output_url = result.get("output_url")
            
            success_text = (
                f"✅ <b>Готово!</b>\n\n"
                f"🎨 Модель: {display_name}\n\n"
            )
            
            # Build result keyboard
            buttons = [
                [InlineKeyboardButton(text="🔁 Повторить", callback_data=f"launch:{model_id}")],
                [
                    InlineKeyboardButton(text="🏠 В меню", callback_data="menu:main"),
                    InlineKeyboardButton(text="💳 Баланс", callback_data="menu:balance"),
                ],
            ]
            kb = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            # Send text message
            await callback.message.answer(success_text, reply_markup=kb, parse_mode="HTML")
            
            # Send media result
            if output_url:
                output_type = model_config.get("output_type", "").lower()
                
                try:
                    if "video" in output_type:
                        await callback.message.answer_video(output_url)
                    elif "image" in output_type:
                        await callback.message.answer_photo(output_url)
                    elif "audio" in output_type:
                        await callback.message.answer_audio(output_url)
                    else:
                        await callback.message.answer(f"📎 Результат: {output_url}")
                except Exception as e:
                    logger.error(f"Failed to send media result: {e}")
                    await callback.message.answer(f"📎 Результат: {output_url}")
        else:
            # Error
            error_msg = result.get("error", "Неизвестная ошибка")
            error_code = result.get("error_code", "unknown")
            
            # Sanitize error message for user
            user_error = _sanitize_error_for_user(error_msg, error_code)
            
            error_text = (
                f"❌ <b>Ошибка генерации</b>\n\n"
                f"🎨 Модель: {display_name}\n\n"
                f"<b>Что произошло:</b>\n{user_error}\n\n"
                f"💡 Попробуйте изменить параметры и запустить снова"
            )
            
            buttons = [
                [InlineKeyboardButton(text="🔁 Повторить", callback_data=f"launch:{model_id}")],
                [
                    InlineKeyboardButton(text="🏠 В меню", callback_data="menu:main"),
                    InlineKeyboardButton(text="🆘 Поддержка", callback_data="menu:help"),
                ],
            ]
            kb = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            await callback.message.answer(error_text, reply_markup=kb, parse_mode="HTML")
            
    except Exception as e:
        logger.error(f"Generation failed: {e}", exc_info=True)
        
        error_text = (
            f"❌ <b>Ошибка генерации</b>\n\n"
            f"🎨 Модель: {display_name}\n\n"
            f"Произошла непредвиденная ошибка. Попробуйте ещё раз.\n\n"
            f"Если проблема повторяется, свяжитесь с поддержкой."
        )
        
        buttons = [
            [InlineKeyboardButton(text="🔁 Повторить", callback_data=f"launch:{model_id}")],
            [
                InlineKeyboardButton(text="🏠 В меню", callback_data="menu:main"),
                InlineKeyboardButton(text="🆘 Поддержка", callback_data="menu:help"),
            ],
        ]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.answer(error_text, reply_markup=kb, parse_mode="HTML")


def _sanitize_error_for_user(error_msg: str, error_code: str) -> str:
    """
    Convert technical error to user-friendly message.
    
    Args:
        error_msg: Raw error message
        error_code: Error code
    
    Returns:
        User-friendly error message
    """
    error_lower = error_msg.lower()
    
    if "required" in error_lower or "field" in error_lower:
        return "Не хватает обязательного поля. Пожалуйста, заполните все данные."
    
    if "invalid" in error_lower or "validation" in error_lower:
        return "Некорректные данные. Проверьте введённые значения."
    
    if "timeout" in error_lower or "timed out" in error_lower:
        return "Превышено время ожидания. Попробуйте ещё раз."
    
    if "rate limit" in error_lower or "too many" in error_lower:
        return "Слишком много запросов. Подождите немного и попробуйте снова."
    
    if "balance" in error_lower or "insufficient" in error_lower:
        return "Недостаточно средств. Пополните баланс."
    
    # Generic fallback
    return "Произошла ошибка. Попробуйте изменить параметры или обратитесь в поддержку."


@router.callback_query(F.data == "wizard:edit", WizardState.confirming)
async def wizard_edit_inputs(callback: CallbackQuery, state: FSMContext) -> None:
    """Go back to edit inputs."""
    await callback.answer()
    
    data = await state.get_data()
    spec = data.get("wizard_spec")
    
    # Go back to first field
    await state.update_data(wizard_current_field_index=0)
    await state.set_state(WizardState.collecting_input)
    await show_field_input(callback.message, state, spec.fields[0])
