"""
Navigation helpers - единые кнопки "Назад" и "Меню".

Гарантирует callback_data <= 64 bytes.
Поддержка navigation stack для умной кнопки "Назад".
"""
import logging
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

MAX_CALLBACK_LEN = 64


async def push_nav(state: FSMContext, callback_data: str) -> None:
    """
    Push current screen to navigation stack.
    
    Args:
        state: FSM context
        callback_data: current screen callback
    """
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    
    # Avoid duplicates
    if not nav_stack or nav_stack[-1] != callback_data:
        nav_stack.append(callback_data)
        
        # Limit stack size
        if len(nav_stack) > 10:
            nav_stack = nav_stack[-10:]
        
        await state.update_data(nav_stack=nav_stack)


async def pop_nav(state: FSMContext) -> Optional[str]:
    """
    Pop last screen from navigation stack.
    
    Args:
        state: FSM context
    
    Returns:
        Previous screen callback or None
    """
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    
    if len(nav_stack) > 1:
        # Remove current
        nav_stack.pop()
        previous = nav_stack[-1]
        await state.update_data(nav_stack=nav_stack)
        return previous
    
    return None


async def get_back_target(state: FSMContext, default: str = "main_menu") -> str:
    """
    Get smart back target from navigation stack.
    
    Args:
        state: FSM context
        default: default if stack empty
    
    Returns:
        Callback for back button
    """
    target = await pop_nav(state)
    return target or default


def validate_callback(callback_data: str) -> str:
    """
    Validate callback_data doesn't exceed limit.
    
    Args:
        callback_data: callback string
    
    Returns:
        Validated callback
    
    Raises:
        ValueError if exceeds 64 bytes (should use short keys instead)
    """
    byte_length = len(callback_data.encode('utf-8'))
    
    if byte_length > MAX_CALLBACK_LEN:
        logger.error(
            f"❌ Callback exceeds 64 bytes ({byte_length}): {callback_data[:40]}\n"
            f"Use app.ui.callback_registry.make_key() for long IDs!"
        )
        raise ValueError(f"Callback too long: {byte_length} bytes (max 64)")
    
    return callback_data


def back_button(callback_data: str, label: str = "◀️ Назад") -> InlineKeyboardButton:
    """Create back button."""
    return InlineKeyboardButton(
        text=label,
        callback_data=validate_callback(callback_data)
    )


def menu_button(callback_data: str = "main_menu", label: str = "🏠 Главное меню") -> InlineKeyboardButton:
    """Create main menu button."""
    return InlineKeyboardButton(
        text=label,
        callback_data=validate_callback(callback_data)
    )


def build_back_row(
    back_cb: str,
    home_cb: str = "main_menu"
) -> List[InlineKeyboardButton]:
    """
    Build standard navigation row: [Назад] [Меню].
    
    Args:
        back_cb: callback for back button
        home_cb: callback for home button (default: main_menu)
    
    Returns:
        Row of buttons
    """
    return [
        back_button(back_cb),
        menu_button(home_cb)
    ]


def add_navigation(
    buttons: List[List[InlineKeyboardButton]],
    back_cb: str,
    home_cb: str = "main_menu"
) -> List[List[InlineKeyboardButton]]:
    """
    Add navigation row to button list.
    
    Args:
        buttons: existing button rows
        back_cb: callback for back button
        home_cb: callback for home button
    
    Returns:
        buttons + navigation row
    """
    return buttons + [build_back_row(back_cb, home_cb)]


def build_model_button(
    model: Dict,
    compact: bool = False
) -> InlineKeyboardButton:
    """
    Build button for model in list.
    
    Args:
        model: model dict from catalog
        compact: if True, show only emoji + name (no price)
    
    Returns:
        Button with model name + price badge
    """
    model_id = model.get("model_id", "")
    display_name = model.get("display_name", "Model")
    pricing = model.get("pricing", {})
    is_free = pricing.get("is_free", False)
    
    # Price badge
    if compact:
        label = display_name
    else:
        if is_free:
            label = f"🎁 {display_name}"
        else:
            price = pricing.get("rub_per_gen", 0)
            if price > 0:
                label = f"{display_name} • {price:.0f}₽"
            else:
                label = display_name
    
    # Truncate if too long
    if len(label) > 40:
        label = label[:37] + "..."
    
    callback = validate_callback(f"model:{model_id}")
    
    return InlineKeyboardButton(text=label, callback_data=callback)


def build_category_button(
    category_key: str,
    category_info: Dict,
    count: Optional[int] = None
) -> InlineKeyboardButton:
    """
    Build button for category.
    
    Args:
        category_key: category key (e.g. "video")
        category_info: category info dict with emoji, title
        count: optional count to show
    
    Returns:
        Button for category
    """
    emoji = category_info.get("emoji", "")
    title = category_info.get("title", "Категория")
    
    if count is not None and count > 0:
        label = f"{emoji} {title} ({count})"
    else:
        label = f"{emoji} {title}"
    
    callback = validate_callback(f"cat:{category_key}")
    
    return InlineKeyboardButton(text=label, callback_data=callback)
