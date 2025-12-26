"""
Zero-silence guarantee handlers - ensure bot always responds.
Contract: Every user action MUST receive a response.
"""
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
import logging

logger = logging.getLogger(__name__)

router = Router(name="zero_silence")


def _fallback_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Генерация", callback_data="menu:generate")],
            [InlineKeyboardButton(text="💳 Баланс / Оплата", callback_data="menu:balance")],
            [InlineKeyboardButton(text="ℹ️ Поддержка", callback_data="menu:support")],
        ]
    )


@router.message(StateFilter(None), F.content_type.in_(["photo", "video", "audio", "document", "voice", "video_note"]))
async def handle_non_text_messages(message: Message):
    """
    Handle non-text messages - always respond.
    """
    await message.answer(
        "📎 Файл получен, но сейчас я жду команды.\n\n"
        "Нажмите /start или выберите действие из меню.",
        reply_markup=_fallback_menu(),
    )


@router.message(StateFilter(None), F.text)
async def handle_text_messages(message: Message):
    """
    Handle text messages - always respond.
    """
    text = message.text or ""
    if text.startswith("/"):
        return
    await message.answer(
        "Я готов начать работу.\n\n"
        "Нажмите /start или выберите действие из меню.",
        reply_markup=_fallback_menu(),
    )



from aiogram.fsm.context import FSMContext


@router.message(~StateFilter(None), F.text)
async def handle_text_unmatched_state(message: Message, state: FSMContext):
    """Fallback for text when user is in some FSM state but no handler matched.

    Prevents 'silence' situations where state expects something else.
    """
    text = message.text or ""
    if text.startswith("/"):
        return

    st = None
    try:
        st = await state.get_state()
    except Exception:
        st = None

    logger.warning("E_INPUT unmatched text in state=%s uid=%s len=%s", st, getattr(message.from_user, "id", None), len(text))
    await message.answer(
        "Я вижу сообщение, но сейчас ожидается другой шаг.\n\nНажмите /start чтобы вернуться в меню, или выберите действие кнопками ниже.",
        reply_markup=_fallback_menu(),
    )
