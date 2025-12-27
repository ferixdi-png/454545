"""Unified keyboard helpers for consistent UX."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List


def btn_back(callback_data: str = "menu:main") -> InlineKeyboardButton:
    """⬅ Назад button."""
    return InlineKeyboardButton(text="⬅ Назад", callback_data=callback_data)


def btn_home() -> InlineKeyboardButton:
    """🏠 В меню button."""
    return InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")


def btn_confirm() -> InlineKeyboardButton:
    """✅ Подтвердить button."""
    return InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm")


def btn_cancel() -> InlineKeyboardButton:
    """❌ Отмена button."""
    return InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")


def kbd_nav(back_to: str = "menu:main", include_home: bool = True) -> List[List[InlineKeyboardButton]]:
    """Standard navigation row(s)."""
    if include_home:
        return [[btn_back(back_to), btn_home()]]
    else:
        return [[btn_back(back_to)]]


def kbd_confirm_cancel() -> List[List[InlineKeyboardButton]]:
    """Confirm/Cancel row."""
    return [[btn_confirm(), btn_cancel()]]
