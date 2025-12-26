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
    """Build main menu - marketing focused."""
    counts = get_counts()
    buttons = []
    
    # Top priority: Formats (NEW UX)
    buttons.append([InlineKeyboardButton(text="🧩 Форматы", callback_data="menu:formats")])
    
    # Популярное и бесплатное
    free_count = len(_get_free_models())
    buttons.extend([
        [
            InlineKeyboardButton(text="🔥 Популярные", callback_data="menu:popular"),
            InlineKeyboardButton(text=f"🎁 Бесплатные ({free_count})", callback_data="menu:free"),
        ],
    ])
    
    # Категории (2x2) - legacy support
    row1, row2, row3 = [], [], []
    
    if counts.get("video", 0) > 0:
        row1.append(build_category_button("video", UI_CATEGORIES["video"]))
    if counts.get("image", 0) > 0:
        row1.append(build_category_button("image", UI_CATEGORIES["image"]))
    
    if counts.get("text_ads", 0) > 0:
        row2.append(build_category_button("text_ads", UI_CATEGORIES["text_ads"]))
    if counts.get("audio_voice", 0) > 0:
        row2.append(build_category_button("audio_voice", UI_CATEGORIES["audio_voice"]))
    
    if counts.get("music", 0) > 0:
        row3.append(build_category_button("music", UI_CATEGORIES["music"]))
    if counts.get("tools", 0) > 0:
        row3.append(build_category_button("tools", UI_CATEGORIES["tools"]))
    
    if row1: buttons.append(row1)
    if row2: buttons.append(row2)
    if row3: buttons.append(row3)
    
    # Партнёрка и прочее
    buttons.extend([
        [InlineKeyboardButton(text="🤝 Партнёрка (бонусы)", callback_data="menu:referral")],
        [
            InlineKeyboardButton(text="📜 История", callback_data="menu:history"),
            InlineKeyboardButton(text="💳 Баланс", callback_data="menu:balance"),
        ],
        [
            InlineKeyboardButton(text="💎 Тарифы", callback_data="menu:pricing"),
            InlineKeyboardButton(text="🆘 Поддержка", callback_data="menu:help"),
        ],
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("start"))
async def start_marketing(message: Message, state: FSMContext) -> None:
    """Start - marketing UX."""
    await state.clear()
    
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "друг"
    
    logger.info(f"Marketing /start: user_id={user_id}")
    
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
    
    # Get bot username properly
    from bot.utils.bot_info import get_bot_username, get_referral_link
    try:
        username = await get_bot_username(callback.bot)
        ref_link = get_referral_link(username, user_id)
    except Exception as e:
        logger.error(f"Failed to get bot username: {e}")
        ref_link = None
        username = None
    
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
async def model_card(callback: CallbackQuery) -> None:
    """Model card (marketing)."""
    await callback.answer()
    
    model_id = callback.data.split(":")[1]
    model = get_model(model_id)
    
    if not model:
        await callback.answer("❌ Модель не найдена", show_alert=True)
        return
    
    profile = build_profile(model)
    
    text = f"<b>{profile['display_name']}</b>\n\n{profile['short_pitch']}\n\n"
    text += "<b>📌 Подходит для:</b>\n" + "\n".join(profile['best_for']) + "\n\n"
    text += f"<b>📦 Результат:</b> {profile['output_format']}\n"
    text += f"<b>💰 Цена:</b> {profile['price']['label']}\n"
    
    if profile['upsell_line']:
        text += f"\n{profile['upsell_line']}\n"
    
    if profile['examples']:
        text += "\n<b>💡 Примеры:</b>\n"
        for i, ex in enumerate(profile['examples'][:2], 1):
            text += f"{i}. {ex}\n"
    
    buttons = [
        [InlineKeyboardButton(text="🚀 Запустить", callback_data=validate_callback(f"gen:{model_id}"))],
    ]
    
    if not profile['price']['is_free']:
        buttons.append([InlineKeyboardButton(text="💳 Пополнить", callback_data="menu:balance")])
    
    buttons.append(build_back_row(f"cat:{profile['category']}", "main_menu"))
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


# ============================================================================
# POPULAR
# ============================================================================

@router.callback_query(F.data == "menu:popular")
async def popular_screen(callback: CallbackQuery) -> None:
    """Popular models."""
    await callback.answer()
    
    models = get_all_enabled_models()
    models.sort(key=lambda m: (not m.get("pricing", {}).get("is_free", False), m.get("pricing", {}).get("rub_per_gen", 999999)))
    
    text = "⭐ <b>Популярные модели</b>\n\nТоп для креативных задач"
    
    buttons = [[build_model_button(m)] for m in models[:10]]
    buttons = add_navigation(buttons, "main_menu")
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


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
