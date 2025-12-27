"""Centralized navigation handler - ensures menu:main/home always works."""
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)
router = Router(name="navigation")


def _build_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Build main menu keyboard."""
    from app.ui import tone_ru
    from app.ui.catalog import get_counts
    from app.pricing.free_models import get_free_models
    
    free_count = len(get_free_models())
    
    buttons = [
        # Top row: Popular / Formats
        [
            InlineKeyboardButton(text=tone_ru.MENU_POPULAR, callback_data="menu:popular"),
            InlineKeyboardButton(text=tone_ru.MENU_FORMATS, callback_data="menu:formats"),
        ],
        # Free models
        [
            InlineKeyboardButton(
                text=tone_ru.MENU_FREE.replace("(5)", f"({free_count})"),
                callback_data="menu:free"
            ),
        ],
        # Quick access by type
        [
            InlineKeyboardButton(text=tone_ru.MENU_VIDEO, callback_data="format_catalog:video"),
            InlineKeyboardButton(text=tone_ru.MENU_IMAGES, callback_data="format_catalog:image"),
        ],
        [
            InlineKeyboardButton(text=tone_ru.MENU_AUDIO, callback_data="format_catalog:audio"),
        ],
        # Management
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


@router.callback_query(F.data == "main_menu")
@router.callback_query(F.data == "menu:main")
@router.callback_query(F.data == "home")
async def handle_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Centralized main menu handler.
    
    Handles: main_menu, menu:main, home
    Always works, clears FSM state.
    """
    await callback.answer()
    await state.clear()  # Clear any wizard/flow state
    
    logger.info(f"Main menu requested: {callback.from_user.id}")
    
    from app.ui.catalog import get_counts
    from app.pricing.free_models import get_free_models
    
    counts = get_counts()
    total = sum(counts.values())
    free_count = len(get_free_models())
    
    text = (
        f"🏠 <b>Главное меню</b>\\n\\n"
        f"🚀 {total} нейросетей • 🎁 {free_count} бесплатно"
    )
    
    try:
        await callback.message.edit_text(
            text,
            reply_markup=_build_main_menu_keyboard(),
            parse_mode="HTML"
        )
    except Exception:
        # If can't edit (old message), send new
        await callback.message.answer(
            text,
            reply_markup=_build_main_menu_keyboard(),
            parse_mode="HTML"
        )
