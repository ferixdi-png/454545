"""
Marketing-focused handlers - полный UX flow для маркетологов.

Интеграция с DatabaseService для баланса и истории.
НЕ заменяет существующие handlers - работает параллельно.
"""
import logging
from decimal import Decimal
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.ui.marketing_menu import (
    MARKETING_CATEGORIES,
    build_ui_tree,
    get_category_info,
    get_model_by_id
)
from app.payments.pricing import calculate_user_price, calculate_kie_cost, format_price_rub

logger = logging.getLogger(__name__)

router = Router(name="marketing")


class MarketingStates(StatesGroup):
    """FSM states for marketing flow."""
    select_category = State()
    select_model = State()
    enter_prompt = State()
    confirm_price = State()


# Global services (будут установлены в main_render.py)
_db_service = None
_free_manager = None


def set_database_service(db_service):
    """Set database service for handlers."""
    global _db_service
    _db_service = db_service


def set_free_manager(free_manager):
    """Set free model manager for handlers."""
    global _free_manager
    _free_manager = free_manager


def _get_db_service():
    """Get database service or None if not available."""
    return _db_service


def _get_free_manager():
    """Get free manager or None."""
    return _free_manager


@router.message(Command("marketing"))
async def cmd_marketing(message: Message, state: FSMContext):
    """Marketing main menu."""
    await state.clear()
    
    text = (
        "🚀 <b>Маркетинговые инструменты</b>\n\n"
        "Выберите категорию креативов:"
    )
    
    keyboard = _build_marketing_menu()
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "marketing:main")
async def cb_marketing_main(callback: CallbackQuery, state: FSMContext):
    """Marketing main menu callback."""
    await state.clear()
    
    text = (
        "🚀 <b>Маркетинговые инструменты</b>\n\n"
        "Выберите категорию креативов:"
    )
    
    keyboard = _build_marketing_menu()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


def _build_marketing_menu() -> InlineKeyboardMarkup:
    """Build marketing categories menu."""
    tree = build_ui_tree()
    rows = []
    
    for cat_key, cat_data in MARKETING_CATEGORIES.items():
        count = len(tree.get(cat_key, []))
        if count == 0:
            continue  # Skip empty categories
        
        emoji = cat_data.get("emoji", "")
        title = cat_data.get("title", "")
        button_text = f"{emoji} {title} ({count})"
        
        rows.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"mcat:{cat_key}"
            )
        ])
    
    # Additional buttons
    rows.append([
        InlineKeyboardButton(text="🎁 Бесплатно попробовать", callback_data="marketing:free")
    ])
    rows.append([
        InlineKeyboardButton(text="💳 Баланс", callback_data="balance:main"),
        InlineKeyboardButton(text="📜 История", callback_data="history:main")
    ])
    rows.append([
        InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "marketing:free")
async def cb_marketing_free(callback: CallbackQuery):
    """Show free models."""
    free_manager = _get_free_manager()
    
    if not free_manager:
        await callback.answer("Сервис временно недоступен", show_alert=True)
        return
    
    free_models_list = await free_manager.get_all_free_models()
    
    if not free_models_list:
        text = (
            f"🎁 <b>Бесплатные модели</b>\n\n"
            f"Сейчас нет доступных бесплатных моделей.\n"
            f"Следите за обновлениями!"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="marketing:main")]
        ])
    else:
        text = (
            f"🎁 <b>Попробуйте бесплатно!</b>\n\n"
            f"Эти модели можно использовать без оплаты.\n"
            f"Идеально для знакомства с сервисом.\n\n"
            f"Доступно моделей: {len(free_models_list)}"
        )
        
        # Build keyboard with free models
        rows = []
        for fm in free_models_list[:10]:
            model_id = fm['model_id']
            daily_limit = fm['daily_limit']
            
            # Get model info
            model = get_model_by_id(model_id)
            if model:
                name = model.get('name', model_id)
                button_text = f"🎁 {name} ({daily_limit}/день)"
                rows.append([
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=f"mmodel:{model_id}"
                    )
                ])
        
        rows.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data="marketing:main")
        ])
        keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("mcat:"))
async def cb_marketing_category(callback: CallbackQuery, state: FSMContext):
    """Show models in marketing category."""
    cat_key = callback.data.split(":", 1)[1]
    cat_info = get_category_info(cat_key)
    
    if not cat_info:
        await callback.answer("Категория не найдена", show_alert=True)
        return
    
    tree = build_ui_tree()
    models = tree.get(cat_key, [])
    
    if not models:
        await callback.answer("В этой категории пока нет доступных моделей", show_alert=True)
        return
    
    emoji = cat_info.get("emoji", "")
    title = cat_info.get("title", "")
    desc = cat_info.get("desc", "")
    
    # Add TOP-3 models preview with descriptions
    top_models_preview = ""
    if len(models) > 0:
        top_models_preview = "\n\n<b>Топ модели:</b>\n"
        for i, model in enumerate(models[:3], 1):
            model_name = model.get("display_name") or model.get("name") or model.get("model_id", "")
            model_desc = model.get("description", "")[:60]  # 60 chars max
            if model_desc:
                top_models_preview += f"{i}. {model_name} — {model_desc}...\n"
            else:
                top_models_preview += f"{i}. {model_name}\n"
    
    text = (
        f"{emoji} <b>{title}</b>\n\n"
        f"{desc}"
        f"{top_models_preview}\n"
        f"Всего моделей: {len(models)}"
    )
    
    keyboard = _build_models_keyboard(cat_key, models)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


def _build_models_keyboard(cat_key: str, models: list) -> InlineKeyboardMarkup:
    """Build models selection keyboard with FREE badges and prices."""
    rows = []
    
    for model in models[:10]:  # Limit to 10 for now
        model_id = model.get("model_id", "")
        name = model.get("display_name") or model.get("name") or model_id
        
        # Check if FREE from SOURCE_OF_TRUTH pricing
        pricing = model.get("pricing", {})
        rub_price = pricing.get("rub_per_gen", 0)
        
        # FREE if rub_per_gen == 0
        is_free = (rub_price == 0)
        
        # Get price
        if is_free:
            button_text = f"🎁 {name} • БЕСПЛАТНО"
        else:
            if rub_price:
                button_text = f"{name} • {rub_price:.2f}₽"
            else:
                button_text = name
        
        rows.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"mmodel:{model_id}"
            )
        ])
    
    if len(models) > 10:
        rows.append([
            InlineKeyboardButton(
                text=f"... ещё {len(models) - 10} моделей",
                callback_data=f"mcat_page:{cat_key}:1"
            )
        ])
    
    rows.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="marketing:main")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("mcat_page:"))
async def cb_category_page(callback: CallbackQuery, state: FSMContext):
    """
    Handle pagination for model lists.
    
    Format: mcat_page:cat_key:page_num
    """
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer("Неверный формат", show_alert=True)
        return
    
    cat_key = parts[1]
    try:
        page = int(parts[2])
    except ValueError:
        page = 0
    
    # Get category models
    tree = build_ui_tree()
    models = tree.get(cat_key, [])
    
    if not models:
        await callback.answer("Модели не найдены", show_alert=True)
        return
    
    # Pagination: 10 per page
    page_size = 10
    start_idx = page * page_size
    end_idx = start_idx + page_size
    page_models = models[start_idx:end_idx]
    
    if not page_models:
        await callback.answer("Нет моделей на этой странице", show_alert=True)
        return
    
    # Build keyboard with pagination
    # Load FREE tier models from SOURCE_OF_TRUTH
    import json
    try:
        with open("models/KIE_SOURCE_OF_TRUTH.json", 'r') as f:
            sot = json.load(f)
            # FREE models are those with rub_per_gen == 0
            free_tier_ids = set()
            for mid, mdata in sot.get('models', {}).items():
                pricing = mdata.get('pricing', {})
                if pricing.get('rub_per_gen') == 0:
                    free_tier_ids.add(mid)
    except Exception:
        free_tier_ids = set()
    
    rows = []
    for model in page_models:
        model_id = model.get("model_id", "")
        name = model.get("display_name") or model.get("name") or model_id
        
        # Check if FREE (rub_per_gen == 0 from SOT)
        is_free = model_id in free_tier_ids
        
        # Get price
        pricing = model.get("pricing", {})
        
        if is_free:
            button_text = f"🎁 {name} • БЕСПЛАТНО"
        elif pricing and pricing.get("rub_per_generation"):
            kie_cost_rub = calculate_kie_cost(model, {}, None)
            user_price = calculate_user_price(kie_cost_rub)
            button_text = f"{name} • {format_price_rub(user_price)}"
        else:
            button_text = name
        
        rows.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"mmodel:{model_id}"
            )
        ])
    
    # Navigation buttons
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"mcat_page:{cat_key}:{page-1}"
        ))
    if end_idx < len(models):
        nav_row.append(InlineKeyboardButton(
            text="Вперёд ▶️",
            callback_data=f"mcat_page:{cat_key}:{page+1}"
        ))
    
    if nav_row:
        rows.append(nav_row)
    
    rows.append([
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="marketing:main")
    ])
    
    # Update message
    cat_info = get_category_info(cat_key)
    emoji = cat_info.get("emoji", "")
    title = cat_info.get("title", "")
    
    text = (
        f"{emoji} <b>{title}</b>\n\n"
        f"Страница {page + 1}/{(len(models) + page_size - 1) // page_size}\n"
        f"Всего моделей: {len(models)}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("mmodel:"))
async def cb_model_details(callback: CallbackQuery, state: FSMContext):
    """Show model details and start generation flow."""
    model_id = callback.data.split(":", 1)[1]
    model = get_model_by_id(model_id)
    
    if not model:
        await callback.answer("Модель не найдена", show_alert=True)
        return
    
    # Check if FREE from SOURCE_OF_TRUTH
    pricing = model.get("pricing", {})
    rub_price = pricing.get("rub_per_gen", 0)
    
    # FREE if rub_per_gen == 0
    is_free = (rub_price == 0)
    
    name = model.get("display_name") or model.get("name") or model_id
    description = model.get("description", "AI генерация контента")
    category = model.get("category", "unknown")
    
    # Get price
    if is_free:
        price_text = "<b>🎁 БЕСПЛАТНО</b>"
    else:
        rub_price = pricing.get("rub_per_gen")
        if rub_price:
            price_text = f"<b>{rub_price:.2f} ₽</b>"
        else:
            price_text = "Цена уточняется"
    
    # Extract UI example prompts (added in enrichment)
    ui_prompts = model.get("ui_example_prompts", [])
    examples_text = ""
    if ui_prompts:
        examples_text = "\n\n💡 <b>Примеры промптов:</b>\n"
        for i, prompt in enumerate(ui_prompts[:2], 1):
            examples_text += f"{i}. <i>{prompt}</i>\n"
    
    # Build rich model card
    text = f"<b>{name}</b>\n\n"
    
    # Truncate long descriptions
    if len(description) > 200:
        description = description[:197] + "..."
    text += f"📝 {description}"
    
    text += examples_text
    
    text += f"\n💰 <b>Стоимость:</b> {price_text}\n"
    text += f"📂 Категория: {category}"
    
    # Add tags for search
    tags = model.get("tags", [])
    if tags:
        tags_str = " ".join(f"#{tag}" for tag in tags[:5])
        text += f"\n\n🏷 {tags_str}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🚀 Запустить генерацию",
            callback_data=f"mgen:start:{model_id}"
        )],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="marketing:main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("mgen:start:"))
async def cb_start_generation(callback: CallbackQuery, state: FSMContext):
    """
    Start generation flow - redirect to flow.py for proper input_schema handling.
    
    MASTER PROMPT compliance:
    - "Ввод ВСЕХ параметров (без автоподстановок)"
    - flow.py correctly implements input_schema with required and optional fields
    - marketing.py should NOT duplicate this logic, use flow.py instead
    """
    model_id = callback.data.split(":", 2)[2]
    model = get_model_by_id(model_id)
    
    if not model:
        await callback.answer("Модель не найдена", show_alert=True)
        return
    
    # Clear marketing state and redirect to flow.py handler
    await state.clear()
    
    # Trigger flow.py's gen: handler by modifying callback data
    # This ensures proper input_schema handling for ALL parameters
    callback.data = f"gen:{model_id}"
    
    # Import and call flow.py's generate_cb handler
    from bot.handlers.flow import generate_cb
    await generate_cb(callback, state)


@router.message(MarketingStates.enter_prompt)
async def process_prompt(message: Message, state: FSMContext):
    """Process user prompt and show price confirmation."""
    prompt = message.text.strip()
    
    if not prompt:
        await message.answer("❌ Промпт не может быть пустым. Попробуйте ещё раз:")
        return
    
    data = await state.get_data()
    model_id = data.get("model_id")
    model = get_model_by_id(model_id)
    
    if not model:
        await message.answer("❌ Ошибка: модель не найдена")
        await state.clear()
        return
    
    # Calculate price
    price = model.get("price")
    if not price:
        await message.answer("❌ Ошибка: цена модели не определена")
        await state.clear()
        return
    
    # CORRECT FORMULA: price_usd × 78 (USD→RUB) × 2 (markup)
    kie_cost_rub = calculate_kie_cost(model, {}, None)
    user_price = calculate_user_price(kie_cost_rub)
    
    # Check if model is free
    free_manager = _get_free_manager()
    is_free = False
    free_limits_info = {}
    
    if free_manager:
        is_free = await free_manager.is_model_free(model_id)
        
        if is_free:
            # Check free limits
            limits_check = await free_manager.check_limits(message.from_user.id, model_id)
            free_limits_info = limits_check
            
            if not limits_check['allowed']:
                reason = limits_check['reason']
                if reason == 'daily_limit_exceeded':
                    text = (
                        f"⏰ <b>Лимит исчерпан</b>\n\n"
                        f"Вы использовали все бесплатные генерации этой модели на сегодня.\n\n"
                        f"Использовано: {limits_check['daily_used']}/{limits_check['daily_limit']}\n\n"
                        f"Вы можете:\n"
                        f"• Подождать до завтра\n"
                        f"• Пополнить баланс и продолжить\n\n"
                        f"Стоимость: {format_price_rub(user_price)}"
                    )
                elif reason == 'hourly_limit_exceeded':
                    text = (
                        f"⏰ <b>Временный лимит</b>\n\n"
                        f"Достигнут часовой лимит.\n\n"
                        f"Использовано: {limits_check['hourly_used']}/{limits_check['hourly_limit']}\n\n"
                        f"Попробуйте через час или пополните баланс."
                    )
                else:
                    text = "❌ Лимит использования исчерпан"
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Пополнить", callback_data="balance:topup")],
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="marketing:main")]
                ])
                await message.answer(text, reply_markup=keyboard)
                await state.clear()
                return
    
    # Check balance (skip for free models)
    db_service = _get_db_service()
    balance_text = ""
    
    if not is_free and db_service:
        from app.database.services import UserService, WalletService
        
        user_service = UserService(db_service)
        wallet_service = WalletService(db_service)
        
        # Ensure user exists
        await user_service.get_or_create(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name
        )
        
        # Get balance
        balance_data = await wallet_service.get_balance(message.from_user.id)
        balance = balance_data.get("balance_rub", Decimal("0.00"))
        
        balance_text = f"\n💰 Ваш баланс: {format_price_rub(balance)}"
        
        if balance < user_price:
            text = (
                f"❌ <b>Недостаточно средств</b>\n\n"
                f"Стоимость: {format_price_rub(user_price)}\n"
                f"Ваш баланс: {format_price_rub(balance)}\n\n"
                f"Необходимо пополнить баланс на {format_price_rub(user_price - balance)}"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Пополнить", callback_data="balance:topup")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="marketing:main")]
            ])
            await message.answer(text, reply_markup=keyboard)
            await state.clear()
            return
    
    # Save prompt and show confirmation
    await state.update_data(prompt=prompt, price=float(user_price), is_free=is_free, free_limits=free_limits_info)
    await state.set_state(MarketingStates.confirm_price)
    
    # Build confirmation text
    if is_free:
        price_text = (
            f"💰 Стоимость: <b>БЕСПЛАТНО</b> 🎁\n"
            f"Осталось попыток:\n"
            f"  • Сегодня: {free_limits_info['daily_limit'] - free_limits_info['daily_used']}/{free_limits_info['daily_limit']}\n"
            f"  • В час: {free_limits_info['hourly_limit'] - free_limits_info['hourly_used']}/{free_limits_info['hourly_limit']}"
        )
    else:
        price_text = f"💰 Стоимость: {format_price_rub(user_price)}{balance_text}"
    
    text = (
        f"<b>Подтверждение генерации</b>\n\n"
        f"Модель: {model.get('name', model_id)}\n"
        f"Промпт: {prompt}\n\n"
        f"{price_text}\n\n"
        f"Подтвердите запуск генерации:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="mgen:confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="marketing:main")]
    ])
    
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "mgen:confirm")
async def cb_confirm_generation(callback: CallbackQuery, state: FSMContext):
    """Confirm and start actual KIE generation with full database integration + free tier support."""
    import uuid
    from datetime import datetime, timezone
    
    data = await state.get_data()
    model_id = data.get("model_id")
    prompt = data.get("prompt")
    price_float = data.get("price", 0.0)
    is_free = data.get("is_free", False)
    user_price = Decimal(str(price_float))
    
    await state.clear()
    
    db_service = _get_db_service()
    free_manager = _get_free_manager()
    
    if not db_service:
        await callback.answer("⚠️ База данных недоступна", show_alert=True)
        return
    
    from app.database.services import UserService, WalletService, JobService
    from app.kie.generator import KieGenerator
    
    user_service = UserService(db_service)
    wallet_service = WalletService(db_service)
    job_service = JobService(db_service)
    
    user_id = callback.from_user.id
    job_id = str(uuid.uuid4())
    
    model = get_model_by_id(model_id)
    if not model:
        await callback.answer("❌ Модель не найдена", show_alert=True)
        return
    
    # Ensure user exists
    await user_service.get_or_create(
        user_id,
        callback.from_user.username,
        callback.from_user.first_name
    )
    
    # Hold balance (SKIP for free models)
    hold_ref = f"hold_{job_id}"
    
    if not is_free:
        hold_ok = await wallet_service.hold_balance(user_id, user_price, hold_ref)
        
        if not hold_ok:
            text = (
                f"❌ <b>Недостаточно средств</b>\n\n"
                f"Стоимость: {format_price_rub(user_price)}\n\n"
                f"Пополните баланс и попробуйте снова"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Пополнить", callback_data="balance:topup")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="marketing:main")]
            ])
            await callback.message.edit_text(text, reply_markup=keyboard)
            return
    else:
        # Log free usage BEFORE generation for tracking
        if free_manager:
            await free_manager.log_usage(user_id, model_id, job_id)
            logger.info(f"Free usage logged for user {user_id}, model {model_id}, job {job_id}")
    
    # Create job
    job_params = {
        "prompt": prompt,
        "model_id": model_id
    }
    
    await job_service.create_job(
        job_id=job_id,
        user_id=user_id,
        model_id=model_id,
        params=job_params,
        price_rub=user_price
    )
    
    await job_service.update_status(job_id, "queued")
    
    # Update UI
    await callback.message.edit_text(
        f"🔄 <b>Генерация запущена</b>\n\n"
        f"Модель: {model.get('name', model_id)}\n"
        f"Промпт: {prompt}\n\n"
        f"⏳ Ожидаем результат..."
    )
    await callback.answer("Генерация запущена!")
    
    # Generate in background with proper timeout and retry logic
    try:
        # Initialize KIE generator
        generator = KieGenerator()
        
        # Update status
        await job_service.update_status(job_id, "running")
        
        # Prepare user inputs for KIE API
        user_inputs = {"prompt": prompt}
        
        # Call KIE API with timeout=300s and progress updates
        async def progress_update(msg: str):
            """Send progress updates to user."""
            try:
                await callback.message.edit_text(
                    f"🔄 <b>Генерация в процессе</b>\n\n"
                    f"Модель: {model.get('name', model_id)}\n"
                    f"Промпт: {prompt}\n\n"
                    f"{msg}"
                )
            except Exception:
                pass  # Ignore edit errors
        
        result = await generator.generate(
            model_id=model_id,
            user_inputs=user_inputs,
            progress_callback=progress_update,
            timeout=300  # 5 minutes max
        )
        
        # Validate result structure
        if not isinstance(result, dict):
            raise ValueError(f"Invalid KIE result type: {type(result)}")
        
        success = result.get("success", False)
        result_urls = result.get("result_urls", [])
        error_code = result.get("error_code")
        error_message = result.get("error_message")
        
        # Check result
        if success and result_urls:
            # SUCCESS: Charge balance (SKIP for free models)
            if not is_free:
                charge_ref = f"charge_{job_id}"
                charge_ok = await wallet_service.charge(user_id, user_price, charge_ref, hold_ref=hold_ref)
                if not charge_ok:
                    logger.error(f"Failed to charge user {user_id} for job {job_id} after successful generation!")
                    # Refund immediately
                    refund_ref = f"refund_{job_id}"
                    await wallet_service.refund(user_id, user_price, refund_ref, hold_ref=hold_ref)
            
            # Update job
            await job_service.update_status(job_id, "succeeded")
            await job_service.update_result(job_id, result)
            
            # Send result to user
            if is_free:
                cost_text = "Стоимость: <b>БЕСПЛАТНО</b> 🎁"
            else:
                cost_text = f"Списано: {format_price_rub(user_price)}"
            
            result_text = (
                f"✅ <b>Генерация завершена!</b>\n\n"
                f"Модель: {model.get('name', model_id)}\n"
                f"{cost_text}\n\n"
                f"Результат готов!"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎨 Новая генерация", callback_data="marketing:main")],
                [InlineKeyboardButton(text="💳 Баланс", callback_data="balance:main")],
                [InlineKeyboardButton(text="📜 История", callback_data="history:main")]
            ])
            
            # Send result URLs
            for url in result_urls[:3]:  # Max 3 results
                await callback.message.answer(url)
            
            await callback.message.answer(result_text, reply_markup=keyboard)
        
        else:
            # FAILURE: Refund (SKIP for free models)
            if not is_free:
                refund_ref = f"refund_{job_id}"
                await wallet_service.refund(user_id, user_price, refund_ref, hold_ref=hold_ref)
                # Enhanced refund message with reason
                refund_reason = "генерация не удалась"
                if error_code == "TIMEOUT":
                    refund_reason = "превышено время ожидания"
                elif error_code == "INVALID_INPUT":
                    refund_reason = "некорректные параметры"
                elif error_code:
                    refund_reason = f"ошибка: {error_code}"
                
                refund_text = (
                    f"💰 <b>Средства возвращены</b>: {format_price_rub(user_price)}\n"
                    f"Причина: {refund_reason}"
                )
            else:
                # Don't count failed free attempt against limits
                if free_manager:
                    # Delete the usage record to allow retry
                    logger.info(f"Free usage NOT counted due to failure: job {job_id}")
                refund_text = "🎁 Бесплатная попытка не засчитана (ошибка не по вашей вине)"
            
            await job_service.update_status(job_id, "failed")
            await job_service.update_result(job_id, result)
            
            # Format error message with helpful hints
            if error_code == "TIMEOUT":
                error_text = (
                    "⏱️ Превышено время ожидания (5 минут)\n\n"
                    "Возможные причины:\n"
                    "• Сложная генерация требует больше времени\n"
                    "• Перегрузка Kie.ai API\n\n"
                    "💡 Попробуйте упростить промпт или повторить позже"
                )
            elif error_code == "INVALID_INPUT":
                error_text = (
                    f"❌ Некорректные параметры\n\n"
                    f"Причина: {error_message}\n\n"
                    f"💡 Проверьте формат ввода и попробуйте снова"
                )
            elif error_code == "INSUFFICIENT_BALANCE":
                error_text = (
                    "💳 Недостаточно средств\n\n"
                    "Пополните баланс и попробуйте снова"
                )
            elif error_message:
                error_text = f"❌ Ошибка: {error_message}\n\n💡 Попробуйте изменить параметры"
            else:
                error_text = "❌ Неизвестная ошибка KIE API\n\n💡 Попробуйте позже"
            
            fail_text = (
                f"❌ <b>Генерация не удалась</b>\n\n"
                f"Модель: {model.get('name', model_id)}\n"
                f"{error_text}\n\n"
                f"{refund_text}"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"mmodel:{model_id}")],
                [InlineKeyboardButton(text="◀️ В меню", callback_data="marketing:main")]
            ])
            
            await callback.message.answer(fail_text, reply_markup=keyboard)
    
    except Exception as e:
        logger.exception(f"Critical exception in generation for job {job_id}: {e}")
        
        # Refund on exception (SKIP for free models)
        if not is_free:
            try:
                refund_ref = f"refund_{job_id}"
                await wallet_service.refund(user_id, user_price, refund_ref, hold_ref=hold_ref)
                refund_text = f"💰 Средства возвращены: {format_price_rub(user_price)}"
            except Exception as refund_err:
                logger.error(f"Failed to refund user {user_id} after exception: {refund_err}")
                refund_text = "⚠️ Свяжитесь с поддержкой для возврата средств"
        else:
            refund_text = "🎁 Бесплатная попытка не засчитана"
        
        try:
            await job_service.update_status(job_id, "failed")
        except Exception:
            pass
        
        error_text = (
            f"❌ <b>Критическая ошибка</b>\n\n"
            f"Не удалось выполнить генерацию.\n"
            f"{refund_text}\n\n"
            f"Попробуйте позже или обратитесь в поддержку"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ В меню", callback_data="marketing:main")]
        ])
        
        await callback.message.answer(error_text, reply_markup=keyboard)


# Export router
__all__ = ["router", "set_database_service", "set_free_manager"]
