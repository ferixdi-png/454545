"""
Marketing-focused bot handlers - НОВЫЙ UX СЛОЙ v1.

Полностью переработанный UX под маркетологов/SMM.
"""
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup

from app.ui.catalog import (
    build_ui_tree,
    get_counts,
    get_model,
    search_models,
    UI_CATEGORIES,
    get_all_enabled_models,
)
from app.ui.model_profile import build_profile
from app.ui.nav import (
    build_back_row,
    add_navigation,
    build_model_button,
    build_category_button,
    validate_callback,
)

logger = logging.getLogger(__name__)
router = Router(name="marketing_v2")


class SearchState(StatesGroup):
    """FSM states for search."""
    waiting_for_query = State()


def _get_free_models() -> list:
    """Get list of free models."""
    try:
        from app.pricing.free_models import get_free_models
        free_ids = get_free_models()
        
        from app.ui.catalog import load_models_sot
        models_dict = load_models_sot()
        
        return [
            models_dict[mid] for mid in free_ids
            if mid in models_dict and models_dict[mid].get("enabled", True)
        ]
    except Exception as e:
        logger.error(f"Failed to load free models: {e}")
        return []


def _get_bot_username() -> str:
    """Get bot username - DEPRECATED, use bot.utils.bot_info.get_bot_username instead."""
    try:
        from app.utils.config import get_config
        cfg = get_config()
        username = cfg.telegram_bot_username
        if username:
            return username.lstrip('@')
    except Exception:
        pass
    return "bot"  # Fallback (will be replaced by async version)


async def _get_referral_stats(user_id: int) -> dict:
    """Get referral stats."""
    try:
        from app.payments.charges import get_charge_manager
        cm = get_charge_manager()
        
        if not cm or not hasattr(cm, "db_service"):
            return {"invites": 0, "free_uses": 0, "max_rub": 0}
        
        async with cm.db_service.get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT referral_invites, referral_free_uses, referral_max_rub FROM users WHERE user_id = $1",
                user_id
            )
            
            if row:
                return {
                    "invites": row["referral_invites"] or 0,
                    "free_uses": row["referral_free_uses"] or 0,
                    "max_rub": row["referral_max_rub"] or 0,
                }
    except Exception as e:
        logger.debug(f"Referral stats error: {e}")
    
    return {"invites": 0, "free_uses": 0, "max_rub": 0}


# ============================================================================
# ГЛАВНОЕ МЕНЮ
# ============================================================================

def _build_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Build main menu - FORMAT-FIRST premium UX."""
    from app.ui.formats import FORMATS, get_popular_models
    from app.ui.catalog import load_models_sot
    
    buttons = []
    
    # Section 1: 🚀 Popular Now (top 6, curated)
    models_dict = load_models_sot()
    popular = get_popular_models(models_dict, limit=6)
    
    if popular:
        buttons.append([InlineKeyboardButton(text="🚀 ПОПУЛЯРНОЕ СЕЙЧАС", callback_data="menu:popular_section")])
        # Show 2x3 grid of top popular
        for i in range(0, min(6, len(popular)), 2):
            row = []
            for j in range(2):
                if i + j < len(popular):
                    m = popular[i + j]
                    row.append(_build_compact_model_button(m))
            if row:
                buttons.append(row)
    
    # Section 2: 🎬 Formats (grid)
    buttons.append([InlineKeyboardButton(text="🎬 ФОРМАТЫ", callback_data="menu:formats_section")])
    
    format_buttons = [
        InlineKeyboardButton(text="✍️🖼 Text→Image", callback_data="format:text-to-image"),
        InlineKeyboardButton(text="🖼 Image→Image", callback_data="format:image-to-image"),
    ]
    buttons.append(format_buttons)
    
    format_buttons2 = [
        InlineKeyboardButton(text="🖼🎬 Image→Video", callback_data="format:image-to-video"),
        InlineKeyboardButton(text="✍️🎬 Text→Video", callback_data="format:text-to-video"),
    ]
    buttons.append(format_buttons2)
    
    format_buttons3 = [
        InlineKeyboardButton(text="🎙 Audio/TTS", callback_data="format:text-to-audio"),
        InlineKeyboardButton(text="🎚 Audio Tools", callback_data="format:audio-to-audio"),
    ]
    buttons.append(format_buttons3)
    
    # Section 3: 🔥 Free models
    free_count = len(_get_free_models())
    buttons.append([InlineKeyboardButton(text=f"🔥 Бесплатные ({free_count})", callback_data="menu:free")])
    
    # Section 4: Referral, Balance, Support
    buttons.extend([
        [InlineKeyboardButton(text="🤝 Партнёрка (бонусы)", callback_data="menu:referral")],
        [
            InlineKeyboardButton(text="💳 Баланс", callback_data="menu:balance"),
            InlineKeyboardButton(text="⭐ Тарифы", callback_data="menu:pricing"),
        ],
        [InlineKeyboardButton(text="🧑‍💻 Поддержка", callback_data="menu:help")],
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_compact_model_button(model: dict) -> InlineKeyboardButton:
    """Build compact model button for grid display."""
    model_id = model.get("model_id", "unknown")
    display_name = model.get("display_name", model_id)
    pricing = model.get("pricing", {})
    
    # Shorten name for grid
    short_name = display_name[:20] + ".." if len(display_name) > 20 else display_name
    
    # Price badge
    if pricing.get("is_free"):
        badge = "FREE"
    else:
        price = pricing.get("rub_per_gen", 0)
        badge = f"{price:.0f}₽"
    
    # Emoji from category/tags
    emoji = "🎨"
    category = model.get("category", "").lower()
    if "video" in category:
        emoji = "🎬"
    elif "image" in category:
        emoji = "🖼"
    elif "audio" in category or "voice" in category:
        emoji = "🎙"
    
    label = f"{emoji} {short_name} · {badge}"
    
    return InlineKeyboardButton(text=label, callback_data=f"model:{model_id}")


@router.message(Command("start"))
async def start_marketing(message: Message, state: FSMContext) -> None:
    """Start - marketing UX."""
    await state.clear()
    
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "друг"
    username = message.from_user.username
    
    logger.info(f"Marketing /start: user_id={user_id}")
    
    # CRITICAL: Ensure user exists in DB to prevent FK violations
    try:
        from app.database.services import ensure_user_exists
        from app.payments.charges import get_charge_manager
        
        cm = get_charge_manager()
        if cm and hasattr(cm, "db_service"):
            await ensure_user_exists(cm.db_service, user_id, username, first_name)
    except Exception as e:
        logger.warning(f"Failed to ensure user exists: {e}")
    
    # Welcome bonus
    try:
        from app.payments.charges import get_charge_manager
        from app.utils.config import get_config
        
        cfg = get_config()
        start_bonus = getattr(cfg, 'start_bonus_rub', 0.0)
        
        cm = get_charge_manager()
        if cm and start_bonus > 0:
            await cm.ensure_welcome_credit(user_id, start_bonus)
    except Exception as e:
        logger.debug(f"Welcome bonus: {e}")
    
    # Referral
    try:
        from app.referral.service import apply_referral_from_start
        from app.payments.charges import get_charge_manager
        
        cm = get_charge_manager()
        if cm and hasattr(cm, "db_service"):
            await apply_referral_from_start(
                db_service=cm.db_service,
                new_user_id=user_id,
                start_text=message.text or ""
            )
    except Exception as e:
        logger.debug(f"Referral: {e}")
    
    # Stats
    counts = get_counts()
    total = sum(counts.values())
    free_count = len(_get_free_models())
    
    text = (
        f"👋 <b>{first_name}</b>, добро пожаловать в <b>AI Studio</b>!\n\n"
        f"🚀 <b>{total} премиальных нейросетей</b> для креативных задач\n\n"
        f"<b>Создавайте за минуты:</b>\n"
        f"• Креативы, просмотры, клиенты\n"
        f"• Видео для Reels, TikTok, YouTube\n"
        f"• Изображения для рекламы\n"
        f"• Тексты, озвучку, музыку\n\n"
        f"🎁 <b>{free_count} моделей бесплатно</b>\n"
        f"🤝 <b>Партнёрка:</b> приглашай → получай бонусы"
    )
    
    await message.answer(text, reply_markup=_build_main_menu_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "main_menu")
async def main_menu_cb(callback: CallbackQuery) -> None:
    """Main menu callback."""
    await callback.answer()
    
    counts = get_counts()
    total = sum(counts.values())
    free_count = len(_get_free_models())
    
    text = (
        f"🏠 <b>Главное меню</b>\n\n"
        f"🚀 {total} нейросетей • 🎁 {free_count} бесплатно"
    )
    
    await callback.message.edit_text(text, reply_markup=_build_main_menu_keyboard(), parse_mode="HTML")


# ============================================================================
# FREE MODELS
# ============================================================================

@router.callback_query(F.data == "menu:free")
async def free_screen(callback: CallbackQuery) -> None:
    """FREE models screen."""
    await callback.answer()
    
    free_models = _get_free_models()
    
    text = (
        f"🔥 <b>Бесплатные модели</b>\n\n"
        f"🎁 {len(free_models)} моделей без оплаты\n\n"
        f"<i>Хотите больше? Откройте ⭐ Популярные</i>"
    )
    
    buttons = [[build_model_button(m)] for m in free_models[:10]]
    buttons = add_navigation(buttons, "main_menu")
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


# ============================================================================
# REFERRAL
# ============================================================================

@router.callback_query(F.data == "menu:referral")
async def referral_screen(callback: CallbackQuery) -> None:
    """Referral program screen."""
    await callback.answer()
    
    user_id = callback.from_user.id
    stats = await _get_referral_stats(user_id)
    
    # Get bot username properly (NEVER show placeholder)
    from bot.utils.bot_info import get_bot_username, get_referral_link
    username = None
    ref_link = None
    
    try:
        username = await get_bot_username(callback.bot)
        if username:
            ref_link = get_referral_link(username, user_id)
        else:
            logger.error("Bot username is None, cannot generate referral link")
    except Exception as e:
        logger.error(f"Failed to get bot username: {e}")
    
    text = (
        f"🤝 <b>Партнёрская программа</b>\n\n"
        f"<b>Приглашай — получай бонусы!</b>\n\n"
        f"🎁 +3 бесплатные генерации за друга\n"
        f"💰 Лимит: модели до 50₽/ген\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Приглашено: {stats['invites']}\n"
        f"• Бесплатных: {stats['free_uses']}\n"
        f"• Лимит: {stats['max_rub']:.0f}₽\n\n"
    )
    
    buttons = []
    
    if ref_link:
        text += f"🔗 <code>{ref_link}</code>"
        buttons.append([InlineKeyboardButton(text="📋 Открыть ссылку", url=ref_link)])
    else:
        text += "⚠️ <i>Не удалось получить реферальную ссылку. Попробуйте позже.</i>"
    
    buttons.append(build_back_row("main_menu"))
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


# ============================================================================
# CATEGORIES
# ============================================================================

@router.callback_query(F.data.startswith("cat:"))
async def category_screen(callback: CallbackQuery) -> None:
    """Category screen."""
    await callback.answer()
    
    cat_key = callback.data.split(":")[1]
    if cat_key not in UI_CATEGORIES:
        return
    
    cat_info = UI_CATEGORIES[cat_key]
    tree = build_ui_tree()
    models = tree.get(cat_key, [])
    
    text = f"{cat_info['emoji']} <b>{cat_info['title']}</b>\n\n{cat_info['desc']}\n\n📦 {len(models)} моделей"
    
    buttons = [[build_model_button(m)] for m in models[:15]]
    buttons = add_navigation(buttons, "main_menu")
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


# ============================================================================
# MODEL CARD
# ============================================================================

@router.callback_query(F.data.startswith("model:"))
async def model_card(callback: CallbackQuery, state: FSMContext) -> None:
    """Model card (premium product page)."""
    await callback.answer()
    
    model_id = callback.data.split(":")[1]
    model = get_model(model_id)
    
    if not model:
        await callback.answer("❌ Модель не найдена", show_alert=True)
        return
    
    profile = build_profile(model)
    
    # Premium product page layout
    text = f"<b>{profile['display_name']}</b>\n\n"
    
    # What it does (1 line)
    text += f"📝 {profile.get('short_pitch', 'Создание контента с помощью ИИ')}\n\n"
    
    # Best for (3 bullets)
    text += "<b>📌 Подходит для:</b>\n"
    for use_case in profile['best_for'][:3]:
        text += f"{use_case}\n"
    text += "\n"
    
    # Required inputs (from InputSpec)
    from app.ui.input_spec import get_input_spec
    spec = get_input_spec(model)
    required_fields = spec.get_required_fields()
    
    if required_fields:
        text += "<b>📋 Требуется для запуска:</b>\n"
        for field in required_fields[:3]:
            emoji_map = {"text": "✍️", "image_url": "🖼", "image_file": "🖼", 
                        "video_url": "🎬", "video_file": "🎬", "audio_url": "🎙", "audio_file": "🎙"}
            emoji = emoji_map.get(field.type, "📝")
            text += f"{emoji} {field.description or field.name}\n"
        text += "\n"
    
    # Examples (2-3)
    if profile.get('examples'):
        text += "<b>💡 Примеры промптов:</b>\n"
        for i, ex in enumerate(profile['examples'][:2], 1):
            text += f"{i}. <i>{ex}</i>\n"
        text += "\n"
    
    # Price and time
    text += f"<b>💰 Цена:</b> {profile['price']['label']}\n"
    
    # Expected time (if available in metadata)
    expected_time = model.get("expected_time_sec")
    if expected_time:
        text += f"<b>⏱ Время:</b> ~{expected_time} сек\n"
    
    # Action buttons
    buttons = [
        [InlineKeyboardButton(text="🚀 Запустить", callback_data=validate_callback(f"wizard:start:{model_id}"))],
    ]
    
    # Try example button (if examples exist)
    if profile.get('examples'):
        buttons.append([InlineKeyboardButton(text="🔁 Попробовать пример", callback_data=f"wizard:example:{model_id}")])
    
    # Navigation
    buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="main_menu"), 
                   InlineKeyboardButton(text="🏠 Домой", callback_data="main_menu")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


# ============================================================================
# FORMAT SCREENS
# ============================================================================

@router.callback_query(F.data.startswith("format:"))
async def format_screen(callback: CallbackQuery) -> None:
    """Format-based model listing (PREMIUM UX)."""
    await callback.answer()
    
    format_key = callback.data.split(":")[1]
    
    from app.ui.formats import FORMATS, get_recommended_models, get_popular_models
    from app.ui.catalog import load_models_sot
    
    if format_key not in FORMATS:
        await callback.answer("❌ Формат не найден", show_alert=True)
        return
    
    format_obj = FORMATS[format_key]
    models_dict = load_models_sot()
    
    # Get recommended (top 3) + popular for this format
    recommended = get_recommended_models(models_dict, format_key, limit=3)
    all_popular = get_popular_models(models_dict, limit=20, format_key=format_key)
    
    # Remove duplicates (recommended already in popular)
    remaining = [m for m in all_popular if m not in recommended]
    
    text = (\n        f\"{format_obj.emoji} <b>{format_obj.name}</b>\\n\\n\"\n        f\"{format_obj.description}\\n\\n\"\n        f\"📊 {len(all_popular)} доступных моделей\"\n    )\n    \n    buttons = []\n    \n    # Recommended section\n    if recommended:\n        buttons.append([InlineKeyboardButton(text=\"⭐ РЕКОМЕНДУЕМ\", callback_data=\"noop\")])\n        for model in recommended:\n            buttons.append([_build_compact_model_button(model)])\n    \n    # Remaining models (sorted by popularity/price)\n    if remaining:\n        buttons.append([InlineKeyboardButton(text=\"📋 ВСЕ МОДЕЛИ\", callback_data=\"noop\")])\n        for model in remaining[:10]:\n            buttons.append([_build_compact_model_button(model)])\n    \n    # Navigation\n    buttons.append([InlineKeyboardButton(text=\"◀ Назад\", callback_data=\"main_menu\"), \n                   InlineKeyboardButton(text=\"🏠 Домой\", callback_data=\"main_menu\")])\n    \n    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=\"HTML\")\n\n\n# ============================================================================\n# POPULAR\n# ============================================================================\n\n@router.callback_query(F.data == \"menu:popular\")\nasync def popular_screen(callback: CallbackQuery) -> None:\n    \"\"\"Popular models (top 10 curated).\"\"\"\n    await callback.answer()\n    \n    from app.ui.formats import get_popular_models\n    from app.ui.catalog import load_models_sot\n    \n    models_dict = load_models_sot()\n    popular = get_popular_models(models_dict, limit=10)\n    \n    text = \"🚀 <b>Популярные модели</b>\\n\\nТоп для креативных задач\"\n    \n    buttons = [[_build_compact_model_button(m)] for m in popular]\n    buttons.append([InlineKeyboardButton(text=\"◀ Назад\", callback_data=\"main_menu\"), \n                   InlineKeyboardButton(text=\"🏠 Домой\", callback_data=\"main_menu\")])\n    \n    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=\"HTML\")\n\n\n@router.callback_query(F.data == \"menu:popular_section\")\nasync def popular_section_expanded(callback: CallbackQuery) -> None:\n    \"\"\"Expanded popular section (alias for menu:popular).\"\"\"\n    await popular_screen(callback)


# ============================================================================
# FALLBACKS
# ============================================================================

@router.callback_query(F.data == "menu:history")
async def history_screen(callback: CallbackQuery) -> None:
    """History fallback."""
    await callback.answer()
    text = "📜 <b>История</b>\n\nФункция в разработке."
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[build_back_row("main_menu")]), parse_mode="HTML")


@router.callback_query(F.data == "menu:help")
async def help_screen(callback: CallbackQuery) -> None:
    """Help screen."""
    await callback.answer()
    
    text = (
        "🆘 <b>Поддержка</b>\n\n"
        "<b>Как получить бесплатное?</b>\n"
        "Нажмите 🔥 Бесплатные\n\n"
        "<b>Как работает партнёрка?</b>\n"
        "Нажмите 🤝 Партнёрка\n\n"
        "<b>Как пополнить?</b>\n"
        "Нажмите 💳 Баланс\n\n"
        "Вопросы: @support"
    )
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[build_back_row("main_menu")]), parse_mode="HTML")


@router.callback_query(F.data == "menu:pricing")
async def pricing_screen(callback: CallbackQuery) -> None:
    """Pricing screen."""
    await callback.answer()
    
    free_count = len(_get_free_models())
    
    text = (
        "💎 <b>Тарифы AI Studio</b>\n\n"
        f"🎁 <b>{free_count} моделей бесплатно</b>\n\n"
        "💰 <b>Платные:</b> от 3₽ до 600₽\n"
        "• Премиум качество\n"
        "• Без лимитов\n\n"
        "🤝 <b>Партнёрка:</b> бонусы за друзей\n\n"
        "💳 Пополняйте удобным способом"
    )
    
    buttons = [
        [InlineKeyboardButton(text="💳 Пополнить", callback_data="menu:balance")],
        [InlineKeyboardButton(text="🤝 Партнёрка", callback_data="menu:referral")],
        build_back_row("main_menu")
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.callback_query(F.data == "menu:search")
async def search_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Start search flow."""
    await callback.answer()
    
    text = (
        "🔍 <b>Поиск модели</b>\n\n"
        "Отправьте запрос (текст):\n"
        "• название модели\n"
        "• тип контента (видео, аудио)\n"
        "• задача (реклама, музыка)\n\n"
        "Например: <code>видео</code> или <code>flux</code>"
    )
    
    await state.set_state(SearchState.waiting_for_query)
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[build_back_row("main_menu")]), parse_mode="HTML")


@router.message(SearchState.waiting_for_query)
async def search_results(message: Message, state: FSMContext) -> None:
    """Show search results."""
    query = message.text.strip() if message.text else ""
    
    if not query:
        await message.answer("Пустой запрос. Попробуйте ещё раз.")
        return
    
    results = search_models(query)
    
    if not results:
        text = f"❌ Ничего не найдено по запросу: <code>{query}</code>\n\nПопробуйте другие слова"
        buttons = [build_back_row("main_menu")]
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        await state.clear()
        return
    
    text = f"🔍 Найдено: {len(results)}\n\nПо запросу: <code>{query}</code>"
    buttons = [[build_model_button(m)] for m in results[:15]]
    buttons = add_navigation(buttons, "main_menu")
    
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await state.clear()
