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
from app.ui.callback_registry import make_key, resolve_key

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
# ГЛАВНОЕ МЕНЮ (НОВАЯ СТРУКТУРА - Format-First UX)
# ============================================================================

def _build_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Build main menu - format-first UX."""
    from app.ui import tone_ru
    
    free_count = len(_get_free_models())
    
    buttons = [
        # Топ-ряд: Популярные / Форматы / Бесплатные
        [
            InlineKeyboardButton(text=tone_ru.MENU_POPULAR, callback_data="menu:popular"),
            InlineKeyboardButton(text=tone_ru.MENU_FORMATS, callback_data="menu:formats"),
        ],
        [
            InlineKeyboardButton(text=tone_ru.MENU_FREE.replace("(5)", f"({free_count})"), callback_data="menu:free"),
        ],
        
        # Быстрый доступ по форматам
        [
            InlineKeyboardButton(text=tone_ru.MENU_VIDEO, callback_data="format_catalog:video"),
            InlineKeyboardButton(text=tone_ru.MENU_IMAGES, callback_data="format_catalog:image"),
        ],
        [
            InlineKeyboardButton(text=tone_ru.MENU_AUDIO, callback_data="format_catalog:audio"),
        ],
        
        # Управление
        [
            InlineKeyboardButton(text=tone_ru.MENU_HISTORY, callback_data="menu:history"),
            InlineKeyboardButton(text=tone_ru.MENU_BALANCE, callback_data="menu:balance"),
        ],
        [
            InlineKeyboardButton(text=tone_ru.MENU_PRICING, callback_data="menu:pricing"),
            InlineKeyboardButton(text=tone_ru.MENU_SUPPORT, callback_data="menu:help"),
        ],
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("start"))
async def start_marketing(message: Message, state: FSMContext) -> None:
    """Start - marketing UX with onboarding."""
    await state.clear()
    
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "друг"
    username = message.from_user.username
    last_name = message.from_user.last_name
    
    logger.info(f"Marketing /start: user_id={user_id}")
    
    # CRITICAL: Ensure user exists before any generation/payment operations
    try:
        from app.payments.charges import get_charge_manager
        cm = get_charge_manager()
        if cm and hasattr(cm, "db_service"):
            from app.database.users import ensure_user_exists
            await ensure_user_exists(
                db_service=cm.db_service,
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
    except Exception as e:
        logger.warning(f"User upsert failed (non-critical): {e}")
    
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
    
    from app.ui.style import StyleGuide
    style = StyleGuide()
    
    # Check if admin
    from app.admin.permissions import is_admin
    is_admin_user = is_admin(user_id)
    
    # Onboarding for newcomers: clear 3-step process
    text = (
        f"{style.header('Главная')}\\n\\n"
        f"👋 <b>{first_name}</b>! Добро пожаловать в AI Studio.\\n\\n"
        f"<b>🚀 Как это работает:</b>\\n"
        f"1️⃣ <b>Выберите формат</b> (видео/фото/аудио/утилиты)\\n"
        f"2️⃣ <b>Выберите модель</b> из каталога\\n"
        f"3️⃣ <b>Отправьте данные</b> → получите результат\\n\\n"
        f"<b>📝 Примеры:</b>\\n"
        f"• <i>Текст</i> → 🎬 <b>Видео</b> для Reels/TikTok\\n"
        f"• <i>Фото</i> → 🎥 <b>Анимация</b> (движение в кадре)\\n"
        f"• <i>Текст</i> → 🖼 <b>Изображение</b> (креативы, баннеры)\\n\\n"
        f"🎁 <b>{free_count} моделей бесплатно</b> • 💎 {total} всего"
    )
    
    # Admin build info
    if is_admin_user:
        from app.utils.version import get_admin_version_info
        version_info = get_admin_version_info()
        text += f"\n\n🔧 Build: {version_info}"
    
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
    
    from app.ui.style import StyleGuide
    style = StyleGuide()
    
    text = (
        f"{style.header('Партнёрка')}\\n\\n"
        f"🎁 <b>Дай другу ссылку — получишь бонусы</b>\\n\\n"
        f"За каждого друга:\\n"
        f"• +3 бесплатные генерации\\n"
        f"• Лимит: до 50₽ за генерацию\\n\\n"
        f"📊 <b>Твоя статистика:</b>\\n"
        f"Приглашено: {stats['invites']} • Бонусов: {stats['free_uses']} • Лимит: {stats['max_rub']:.0f}₽\\n\\n"
    )
    
    buttons = []
    
    if ref_link:
        text += f"<b>Твоя ссылка:</b>\\n<code>{ref_link}</code>"
        buttons.append([InlineKeyboardButton(text="📋 Открыть ссылку", url=ref_link)])
    else:
        text += "<i>Ссылка временно недоступна, попробуй позже</i>"
    
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
        [InlineKeyboardButton(text="🚀 Запустить", callback_data=make_key("gen", model_id))],
    ]
    
    if not profile['price']['is_free']:
        buttons.append([InlineKeyboardButton(text="💳 Пополнить", callback_data="menu:balance")])
    
    buttons.append(build_back_row(f"cat:{profile['category']}", "main_menu"))
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


# ============================================================================
# FORMATS CATALOG (новый UX)
# ============================================================================

@router.callback_query(F.data == "menu:formats")
async def formats_menu(callback: CallbackQuery) -> None:
    """Formats catalog menu."""
    await callback.answer()
    
    from app.ui import tone_ru
    
    text = (
        f"🧩 <b>Форматы</b>\n\n"
        f"Выберите тип задачи:"
    )
    
    buttons = [
        [InlineKeyboardButton(text=tone_ru.FORMAT_TEXT_TO_IMAGE, callback_data="format_catalog:text-to-image")],
        [InlineKeyboardButton(text=tone_ru.FORMAT_IMAGE_TO_IMAGE, callback_data="format_catalog:image-to-image")],
        [InlineKeyboardButton(text=tone_ru.FORMAT_TEXT_TO_VIDEO, callback_data="format_catalog:text-to-video")],
        [InlineKeyboardButton(text=tone_ru.FORMAT_IMAGE_TO_VIDEO, callback_data="format_catalog:image-to-video")],
        [InlineKeyboardButton(text=tone_ru.FORMAT_TEXT_TO_AUDIO, callback_data="format_catalog:text-to-audio")],
        [InlineKeyboardButton(text=tone_ru.FORMAT_AUDIO_PROCESSING, callback_data="format_catalog:audio")],
        [InlineKeyboardButton(text=tone_ru.FORMAT_IMAGE_UPSCALE, callback_data="format_catalog:image-upscale")],
        [InlineKeyboardButton(text=tone_ru.FORMAT_BACKGROUND_REMOVE, callback_data="format_catalog:background-remove")],
        build_back_row("main_menu"),
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.callback_query(F.data.startswith("format_catalog:"))
async def format_catalog_screen(callback: CallbackQuery) -> None:
    """Show models by format."""
    await callback.answer()
    
    format_key = callback.data.split(":", 1)[1]
    
    # Load format map
    import json
    from pathlib import Path
    
    # Use relative path from repo root
    repo_root = Path(__file__).resolve().parent.parent.parent
    map_file = repo_root / "app/ui/content/model_format_map.json"
    
    if not map_file.exists():
        await callback.message.edit_text("❌ Каталог форматов недоступен", parse_mode="HTML")
        return
    
    with open(map_file, "r", encoding="utf-8") as f:
        format_map = json.load(f)
    
    # Find models matching format
    matching_models = []
    for model_id, formats in format_map.get("model_to_formats", {}).items():
        if format_key in formats or (format_key == "video" and any(f in formats for f in ["text-to-video", "image-to-video", "video-editing"])) \
           or (format_key == "image" and any(f in formats for f in ["text-to-image", "image-to-image", "image-upscale", "background-remove"])) \
           or (format_key == "audio" and any(f in formats for f in ["text-to-audio", "audio-editing", "audio-to-video"])):
            
            try:
                model = get_model(model_id)
                if model and model.get("enabled", True):
                    matching_models.append(model)
            except Exception:
                continue
    
    if not matching_models:
        await callback.message.edit_text(f"❌ Модели для формата <b>{format_key}</b> не найдены", parse_mode="HTML")
        return
    
    # Format name mapping
    format_names = {
        "text-to-image": "Текст → Изображение",
        "image-to-image": "Изображение → Изображение",
        "text-to-video": "Текст → Видео",
        "image-to-video": "Изображение → Видео",
        "text-to-audio": "Текст → Аудио (TTS/SFX)",
        "audio-editing": "Обработка аудио",
        "audio-to-video": "Аудио → Видео",
        "video-editing": "Обработка видео",
        "image-upscale": "Увеличение изображений",
        "background-remove": "Удаление фона",
        "video": "🎬 Видео (все)",
        "image": "🖼 Изображения (все)",
        "audio": "🎙 Аудио (все)",
    }
    
    format_display = format_names.get(format_key, format_key)
    
    text = f"🧩 <b>{format_display}</b>\n\n🎨 Найдено моделей: {len(matching_models)}"
    
    buttons = [[build_model_button(m)] for m in matching_models[:15]]
    buttons.append(build_back_row("menu:formats", "main_menu"))
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


# ============================================================================
# MODEL CARD (перед запуском wizard)
# ============================================================================

async def show_model_card(callback: CallbackQuery, model_id: str) -> None:
    """Show Model Card screen before wizard."""
    from app.ui import tone_ru
    
    try:
        model = get_model(model_id)
        if not model:
            await callback.message.edit_text("❌ Модель не найдена", parse_mode="HTML")
            return
        
        profile = build_profile(model)
        
        # Load format info
        import json
        from pathlib import Path
        
        repo_root = Path(__file__).resolve().parent.parent.parent
        map_file = repo_root / "app/ui/content/model_format_map.json"
        format_str = "—"
        
        if map_file.exists():
            with open(map_file, "r", encoding="utf-8") as f:
                format_map = json.load(f)
            
            formats = format_map.get("model_to_formats", {}).get(model_id, [])
            if formats:
                format_names = {
                    "text-to-image": "Текст → Изображение",
                    "image-to-image": "Изображение → Изображение",
                    "text-to-video": "Текст → Видео",
                    "image-to-video": "Изображение → Видео",
                    "text-to-audio": "Текст → Аудио",
                    "audio-editing": "Обработка аудио",
                    "image-upscale": "Увеличение изображений",
                    "background-remove": "Удаление фона",
                }
                format_str = ", ".join([format_names.get(f, f) for f in formats[:2]])
        
        # Build required inputs list
        required_inputs = []
        inputs = model.get("inputs", {})
        
        for inp_name, inp_spec in inputs.items():
            if inp_spec.get("required", False):
                input_type = inp_spec.get("type", "TEXT")
                emoji = tone_ru.get_emoji_for_input_type(input_type)
                display = inp_spec.get("display", inp_name)
                required_inputs.append(f"{emoji} {display}")
        
        inputs_text = "\n".join(required_inputs) if required_inputs else "—"
        
        # Popularity heuristic
        price_val = profile["price"].get("value", 999)
        if price_val == 0:
            popularity = tone_ru.POPULARITY_HIGH
        elif price_val < 10:
            popularity = tone_ru.POPULARITY_MEDIUM
        else:
            popularity = tone_ru.POPULARITY_LOW
        
        # Build card
        text = tone_ru.MSG_MODEL_CARD_TEMPLATE.format(
            display_name=profile["display_name"],
            description=profile["description"] or "AI-модель для креативных задач",
            format=format_str,
            price=profile["price"]["label"],
            popularity=popularity,
            required_inputs=inputs_text,
        )
        
        # Buttons
        buttons = [
            [InlineKeyboardButton(text=tone_ru.BTN_GENERATE, callback_data=make_key("gen", model_id))],
        ]
        
        # Add presets if available
        # TODO: load from presets_ru.json
        
        buttons.append(build_back_row("menu:popular", "main_menu"))
        
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Model card error: {e}", exc_info=True)
        await callback.message.edit_text(f"❌ Ошибка загрузки карточки модели", parse_mode="HTML")


# ============================================================================
# POPULAR (теперь с Model Card)
# ============================================================================

@router.callback_query(F.data == "menu:popular")
async def popular_screen(callback: CallbackQuery) -> None:
    """Popular models."""
    await callback.answer()
    
    models = get_all_enabled_models()
    models.sort(key=lambda m: (not m.get("pricing", {}).get("is_free", False), m.get("pricing", {}).get("rub_per_gen", 999999)))
    
    text = "⭐ <b>Популярные модели</b>\n\nТоп для креативных задач"
    
    buttons = [[InlineKeyboardButton(text=build_model_button(m).text, callback_data=make_key("card", m['id']))] for m in models[:10]]
    buttons = add_navigation(buttons, "main_menu")
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.callback_query(F.data.startswith("card:"))
async def model_card_handler(callback: CallbackQuery) -> None:
    """Model Card callback - resolves short key."""
    await callback.answer()
    
    short_key = callback.data
    model_id = resolve_key(short_key)
    
    if not model_id:
        logger.error(f"Failed to resolve model card key: {short_key}")
        await callback.message.edit_text("❌ Модель не найдена", parse_mode="HTML")
        return
    
    await show_model_card(callback, model_id)


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
    
    from app.ui.style import StyleGuide
    style = StyleGuide()
    
    text = (
        f"{style.header('Поиск')}\\n\\n"
        "Введи что ищешь:\\n\\n"
        "<b>Примеры:</b>\\n"
        "• <code>видео</code> → модели для видео\\n"
        "• <code>озвучка</code> → голос и TTS\\n"
        "• <code>апскейл</code> → улучшение качества\\n"
        "• <code>фон</code> → удаление фона"
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
