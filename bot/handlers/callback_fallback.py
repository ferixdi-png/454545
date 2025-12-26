"""Catch-all fallback for callback queries to avoid 'infinite loading' buttons.

Must be included AFTER specific routers (flow, marketing, etc).
"""

from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
import logging

logger = logging.getLogger(__name__)
router = Router(name="callback_fallback")



def _fallback_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")],
            [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu:help")],
        ]
    )


@router.callback_query()
async def handle_unknown_callback(callback: CallbackQuery):
    data = callback.data or ""
    uid = callback.from_user.id if callback.from_user else "-"
    logger.warning(f"E_CALLBACK unknown callback | uid={uid} data={data[:200]}")
    try:
        await callback.answer("Кнопка устарела. Обновляю…", show_alert=False)
    except Exception:
        pass

    # Prefer editing message if possible; otherwise send a new one.
    msg = callback.message
    if not msg:
        return
    text = "⚠️ Эта кнопка уже устарела (старое меню).\n\nНажмите /start и выберите действие заново."
    try:
        await msg.edit_text(text, reply_markup=_fallback_menu())
    except Exception:
        try:
            await msg.answer(text, reply_markup=_fallback_menu())
        except Exception:
            pass
