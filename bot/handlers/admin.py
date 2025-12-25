"""
Admin panel handlers - полное управление системой.
"""
import logging
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.payments.pricing import format_price_rub
from app.admin.permissions import is_admin

logger = logging.getLogger(__name__)

router = Router(name="admin")

# Global services
_db_service = None
_admin_service = None
_free_manager = None


def set_services(db_service, admin_service, free_manager):
    """Set services for handlers."""
    global _db_service, _admin_service, _free_manager
    _db_service = db_service
    _admin_service = admin_service
    _free_manager = free_manager


class AdminStates(StatesGroup):
    """FSM states for admin operations."""
    select_model_for_free = State()
    enter_free_limits = State()
    select_user_for_action = State()
    enter_topup_amount = State()
    enter_charge_amount = State()
    enter_ban_reason = State()


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """Admin panel entry point."""
    await state.clear()
    
    # Check admin
    if not await is_admin(message.from_user.id, _db_service):
        await message.answer("⛔️ Доступ запрещён")
        return
    
    text = (
        f"🛠 <b>Админ-панель</b>\n\n"
        f"Добро пожаловать, {message.from_user.first_name}!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Управление моделями", callback_data="admin:models")],
        [InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin:users")],
        [InlineKeyboardButton(text="📊 Аналитика", callback_data="admin:analytics")],
        [InlineKeyboardButton(text="📜 Лог действий", callback_data="admin:log")],
        [InlineKeyboardButton(text="◀️ Закрыть", callback_data="admin:close")]
    ])
    
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "admin:close")
async def cb_admin_close(callback: CallbackQuery, state: FSMContext):
    """Close admin panel."""
    await callback.message.delete()
    await callback.answer("Админ-панель закрыта")
    await state.clear()


# ========== MODELS MANAGEMENT ==========

@router.callback_query(F.data == "admin:models")
async def cb_admin_models(callback: CallbackQuery, state: FSMContext):
    """Models management."""
    if not await is_admin(callback.from_user.id, _db_service):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    # Get free models count
    free_models = await _free_manager.get_all_free_models()
    
    text = (
        f"🎨 <b>Управление моделями</b>\n\n"
        f"Бесплатных моделей: {len(free_models)}\n\n"
        f"Выберите действие:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Список бесплатных", callback_data="admin:models:list_free")],
        [InlineKeyboardButton(text="➕ Сделать модель бесплатной", callback_data="admin:models:add_free")],
        [InlineKeyboardButton(text="� Ресинк моделей из Kie API", callback_data="admin:models:resync")],
        [InlineKeyboardButton(text="�📊 Статистика моделей", callback_data="admin:models:stats")],
        [InlineKeyboardButton(text="⚠️ Модели без schema", callback_data="admin:models:broken")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:models:list_free")
async def cb_admin_models_list_free(callback: CallbackQuery):
    """List free models."""
    if not await is_admin(callback.from_user.id, _db_service):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    free_models = await _free_manager.get_all_free_models()
    
    if not free_models:
        text = "🎁 <b>Бесплатные модели</b>\n\nСписок пуст"
    else:
        text = f"🎁 <b>Бесплатные модели</b> ({len(free_models)})\n\n"
        for model in free_models:
            model_id = model['model_id']
            daily = model['daily_limit']
            hourly = model.get('hourly_limit', '—')
            text += f"• <code>{model_id}</code>\n  Лимиты: {daily}/день, {hourly}/час\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:models")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:models:add_free")
async def cb_admin_models_add_free(callback: CallbackQuery, state: FSMContext):
    """Add free model."""
    if not await is_admin(callback.from_user.id, _db_service):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    text = (
        f"➕ <b>Сделать модель бесплатной</b>\n\n"
        f"Введите ID модели (например: <code>gemini_flash_2_0</code>)"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:models")]
    ])
    
    await state.set_state(AdminStates.select_model_for_free)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(AdminStates.select_model_for_free)
async def process_free_model_id(message: Message, state: FSMContext):
    """Process model ID for free."""
    if not await is_admin(message.from_user.id, _db_service):
        await message.answer("⛔️ Доступ запрещён")
        await state.clear()
        return
    
    model_id = message.text.strip()
    
    # Save to state
    await state.update_data(free_model_id=model_id)
    await state.set_state(AdminStates.enter_free_limits)
    
    text = (
        f"➕ <b>Настройка лимитов</b>\n\n"
        f"Модель: <code>{model_id}</code>\n\n"
        f"Введите лимиты в формате:\n"
        f"<code>daily hourly</code>\n\n"
        f"Например: <code>5 2</code> (5 в день, 2 в час)\n"
        f"Или просто <code>5</code> (только дневной лимит)"
    )
    
    await message.answer(text)


@router.message(AdminStates.enter_free_limits)
async def process_free_limits(message: Message, state: FSMContext):
    """Process free limits."""
    if not await is_admin(message.from_user.id, _db_service):
        await message.answer("⛔️ Доступ запрещён")
        await state.clear()
        return
    
    data = await state.get_data()
    model_id = data.get("free_model_id")
    
    parts = message.text.strip().split()
    
    try:
        daily_limit = int(parts[0])
        hourly_limit = int(parts[1]) if len(parts) > 1 else 2
    except (ValueError, IndexError) as e:
        # MASTER PROMPT: No bare except - specific exception types for parseInt errors
        logger.error(f"Failed to parse free model limits from '{message.text}': {e}")
        await message.answer("❌ Неверный формат. Попробуйте ещё раз:")
        return
    
    # Add free model
    await _admin_service.set_model_free(
        admin_id=message.from_user.id,
        model_id=model_id,
        daily_limit=daily_limit,
        hourly_limit=hourly_limit
    )
    
    text = (
        f"✅ <b>Модель настроена</b>\n\n"
        f"<code>{model_id}</code>\n"
        f"Лимиты: {daily_limit}/день, {hourly_limit}/час"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Управление моделями", callback_data="admin:models")],
        [InlineKeyboardButton(text="◀️ В админку", callback_data="admin:main")]
    ])
    
    await message.answer(text, reply_markup=keyboard)
    await state.clear()


@router.callback_query(F.data == "admin:models:stats")
async def cb_admin_models_stats(callback: CallbackQuery):
    """Show models statistics."""
    if not await is_admin(callback.from_user.id, _db_service):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    from app.admin.analytics import Analytics
    
    analytics = Analytics(_db_service)
    top_models = await analytics.get_top_models(limit=10)
    
    text = f"📊 <b>Топ-10 моделей</b>\n\n"
    
    for i, model in enumerate(top_models, 1):
        model_id = model['model_id']
        uses = model['total_uses']
        revenue = model['revenue']
        success_rate = model['success_rate']
        
        text += f"{i}. <code>{model_id}</code>\n"
        text += f"   Использований: {uses}, Revenue: {format_price_rub(revenue)}\n"
        text += f"   Success rate: {success_rate:.1f}%\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:models")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# ========== USERS MANAGEMENT ==========

@router.callback_query(F.data == "admin:users")
async def cb_admin_users(callback: CallbackQuery):
    """Users management."""
    if not await is_admin(callback.from_user.id, _db_service):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    text = (
        f"👥 <b>Управление пользователями</b>\n\n"
        f"Выберите действие:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin:users:find")],
        [InlineKeyboardButton(text="💰 Начислить баланс", callback_data="admin:users:topup")],
        [InlineKeyboardButton(text="💸 Списать баланс", callback_data="admin:users:charge")],
        [InlineKeyboardButton(text="🚫 Заблокировать", callback_data="admin:users:ban")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:users:find")
async def cb_admin_users_find(callback: CallbackQuery, state: FSMContext):
    """Find user."""
    if not await is_admin(callback.from_user.id, _db_service):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    text = (
        f"🔍 <b>Поиск пользователя</b>\n\n"
        f"Введите user_id:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:users")]
    ])
    
    await state.set_state(AdminStates.select_user_for_action)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(AdminStates.select_user_for_action)
async def process_user_find(message: Message, state: FSMContext):
    """Process user search."""
    if not await is_admin(message.from_user.id, _db_service):
        await message.answer("⛔️ Доступ запрещён")
        await state.clear()
        return
    
    try:
        user_id = int(message.text.strip())
    except ValueError as e:
        # MASTER PROMPT: No bare except - specific exception type for parseInt
        logger.error(f"Failed to parse user_id from '{message.text}': {e}")
        await message.answer("❌ Неверный формат. Введите числовой user_id:")
        return
    
    # Get user info
    user_info = await _admin_service.get_user_info(user_id)
    
    if not user_info:
        await message.answer(f"❌ Пользователь {user_id} не найден")
        await state.clear()
        return
    
    # Format info
    text = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"ID: <code>{user_info['user_id']}</code>\n"
        f"Username: @{user_info['username'] or '—'}\n"
        f"Имя: {user_info['first_name'] or '—'}\n"
        f"Роль: {user_info['role']}\n\n"
        f"<b>Баланс:</b>\n"
        f"💰 Доступно: {format_price_rub(user_info['balance']['balance_rub'])}\n"
        f"🔒 В резерве: {format_price_rub(user_info['balance']['hold_rub'])}\n\n"
        f"<b>Статистика:</b>\n"
        f"Генераций: {user_info['stats']['total_jobs']} (успешных: {user_info['stats']['success_jobs']})\n"
        f"Потрачено: {format_price_rub(user_info['stats']['total_spent'])}\n"
        f"Free использований: {user_info['free_usage']['total_all_time']} (сегодня: {user_info['free_usage']['total_today']})\n\n"
        f"Зарегистрирован: {user_info['created_at'].strftime('%d.%m.%Y %H:%M')}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:users")]
    ])
    
    await message.answer(text, reply_markup=keyboard)
    await state.clear()


# ========== ANALYTICS ==========

@router.callback_query(F.data == "admin:analytics")
async def cb_admin_analytics(callback: CallbackQuery):
    """Show analytics."""
    if not await is_admin(callback.from_user.id, _db_service):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    from app.admin.analytics import Analytics
    
    analytics = Analytics(_db_service)
    
    # Get stats
    revenue_stats = await analytics.get_revenue_stats(period_days=30)
    activity_stats = await analytics.get_user_activity(period_days=7)
    conversion = await analytics.get_free_to_paid_conversion()
    
    text = (
        f"📊 <b>Аналитика</b>\n\n"
        f"<b>Выручка (30 дней):</b>\n"
        f"💰 Revenue: {format_price_rub(revenue_stats['total_revenue'])}\n"
        f"💵 Topups: {format_price_rub(revenue_stats['total_topups'])}\n"
        f"↩️ Refunds: {format_price_rub(revenue_stats['total_refunds'])}\n"
        f"👥 Платящих: {revenue_stats['paying_users']}\n"
        f"📈 ARPU: {format_price_rub(revenue_stats['avg_revenue_per_user'])}\n\n"
        f"<b>Активность (7 дней):</b>\n"
        f"👤 Новых: {activity_stats['new_users']}\n"
        f"✅ Активных: {activity_stats['active_users']}\n"
        f"📊 Всего: {activity_stats['total_users']}\n\n"
        f"<b>Free → Paid конверсия:</b>\n"
        f"Free users: {conversion['total_free_users']}\n"
        f"Converted: {conversion['converted_users']}\n"
        f"Rate: {conversion['conversion_rate']:.1f}%"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Топ моделей", callback_data="admin:models:stats")],
        [InlineKeyboardButton(text="❌ Ошибки", callback_data="admin:analytics:errors")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:analytics:errors")
async def cb_admin_analytics_errors(callback: CallbackQuery):
    """Show error stats."""
    if not await is_admin(callback.from_user.id, _db_service):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    from app.admin.analytics import Analytics
    
    analytics = Analytics(_db_service)
    errors = await analytics.get_error_stats(limit=10)
    
    text = f"❌ <b>Ошибки генерации</b>\n\n"
    
    if not errors:
        text += "<i>Нет ошибок</i>"
    else:
        for error in errors:
            model_id = error['model_id']
            count = error['fail_count']
            last_fail = error['last_fail'].strftime('%d.%m %H:%M')
            text += f"• <code>{model_id}</code>\n  Ошибок: {count}, последняя: {last_fail}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:analytics")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# ========== ADMIN LOG ==========

@router.callback_query(F.data == "admin:log")
async def cb_admin_log(callback: CallbackQuery):
    """Show admin actions log."""
    if not await is_admin(callback.from_user.id, _db_service):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    log = await _admin_service.get_admin_log(limit=20)
    
    text = f"📜 <b>Лог действий</b> (последние 20)\n\n"
    
    if not log:
        text += "<i>Лог пуст</i>"
    else:
        for entry in log:
            admin_id = entry['admin_id']
            action = entry['action_type']
            target = entry['target_id'] or '—'
            created = entry['created_at'].strftime('%d.%m %H:%M')
            
            text += f"• {created}: Admin {admin_id}\n  {action} → {target}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:models:broken")
async def cb_admin_models_broken(callback: CallbackQuery, state: FSMContext):
    """Show models without valid input_schema."""
    if not await is_admin(callback.from_user.id, _db_service):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    # Load registry and find broken models
    from app.ui.marketing_menu import load_registry
    
    registry = load_registry()
    broken_models = []
    
    for model in registry:
        if model.get("type") != "model":
            continue
        
        # Check if model has valid schema
        input_schema = model.get("input_schema", {})
        properties = input_schema.get("properties", {})
        
        if not input_schema or not properties:
            model_id = model.get("model_id", "unknown")
            price = model.get("price", 0)
            is_pricing_known = model.get("is_pricing_known", False)
            broken_models.append({
                "model_id": model_id,
                "price": price,
                "enabled": is_pricing_known
            })
    
    if not broken_models:
        text = (
            f"✅ <b>Все модели валидны</b>\n\n"
            f"Нет моделей без input_schema"
        )
    else:
        text = (
            f"⚠️ <b>Модели без input_schema</b>\n\n"
            f"Найдено: {len(broken_models)}\n\n"
            f"Эти модели скрыты от пользователей:\n\n"
        )
        
        for m in broken_models[:10]:  # Limit to 10
            status = "🟢" if m["enabled"] else "🔴"
            text += f"{status} {m['model_id']}\n"
            text += f"   Цена: {m['price']} RUB\n\n"
        
        if len(broken_models) > 10:
            text += f"... ещё {len(broken_models) - 10} моделей\n\n"
        
        text += (
            f"<b>Решение:</b>\n"
            f"• Enrichment через KIE API\n"
            f"• Ручное добавление schema\n"
            f"• Используется fallback (prompt-only)"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:models")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:main")
async def cb_admin_main(callback: CallbackQuery, state: FSMContext):
    """Return to admin main menu."""
    await state.clear()
    
    if not await is_admin(callback.from_user.id, _db_service):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    text = (
        f"🛠 <b>Админ-панель</b>\n\n"
        f"Главное меню"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Управление моделями", callback_data="admin:models")],
        [InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin:users")],
        [InlineKeyboardButton(text="📊 Аналитика", callback_data="admin:analytics")],
        [InlineKeyboardButton(text="📜 Лог действий", callback_data="admin:log")],
        [InlineKeyboardButton(text="◀️ Закрыть", callback_data="admin:close")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:models:resync")
async def cb_admin_models_resync(callback: CallbackQuery):
    """Resync models from Kie API."""
    if not await is_admin(callback.from_user.id, _db_service):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer("🔄 Запуск ресинка...", show_alert=True)
    
    # Показываем процесс
    await callback.message.edit_text(
        "🔄 <b>Ресинк моделей</b>\n\n"
        "⏳ Загрузка моделей из Kie API...\n"
        "Это может занять несколько минут."
    )
    
    try:
        import subprocess
        import asyncio
        
        # Запускаем скрипт синхронизации
        process = await asyncio.create_subprocess_exec(
            "python3",
            "scripts/build_registry_v3.py",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd="/workspaces/5656"
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            # Успех
            output = stdout.decode('utf-8')
            
            # Парсим результаты (простой подсчёт строк с "• ")
            models_count = output.count("• ")
            
            text = (
                f"✅ <b>Ресинк завершён!</b>\n\n"
                f"📊 Синхронизировано моделей: {models_count}\n\n"
                f"<i>Source of truth обновлён</i>"
            )
        else:
            # Ошибка
            error = stderr.decode('utf-8')
            text = (
                f"❌ <b>Ошибка ресинка</b>\n\n"
                f"<code>{error[:500]}</code>"
            )
    
    except Exception as e:
        logger.error(f"Resync error: {e}", exc_info=True)
        text = (
            f"❌ <b>Ошибка</b>\n\n"
            f"{str(e)}"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к моделям", callback_data="admin:models")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


# Export
__all__ = ["router", "set_services"]


