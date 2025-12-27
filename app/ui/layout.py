"""Unified screen layout renderer for consistent UX design.

PATTERN (enforced everywhere):
- Header (1 line, bold, max 1 emoji)
- Body (1-2 paragraphs max)
- Bullets (up to 4 max)
- Buttons (organized in rows)
- Footer hint (optional, subtle)

This ensures all screens follow same design discipline.
"""
from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.ui import tone


def render_screen(
    title: str,
    body_lines: Optional[List[str]] = None,
    buttons_rows: Optional[List[List[tuple[str, str]]]] = None,
    footer_hint: Optional[str] = None,
) -> tuple[str, Optional[InlineKeyboardMarkup]]:
    """Render screen with unified layout pattern.
    
    Args:
        title: Screen header (auto-formatted with bold)
        body_lines: List of paragraphs/bullets (max 2 paragraphs + 4 bullets)
        buttons_rows: List of rows, each row is list of (text, callback_data) tuples
        footer_hint: Optional footer hint (subtle, italics)
    
    Returns:
        (message_text, keyboard_markup)
    """
    parts = []
    
    # Header
    parts.append(tone.header(title))
    
    # Body
    if body_lines:
        # Separate paragraphs from bullets
        paragraphs = [line for line in body_lines if not line.strip().startswith("•")]
        bullets = [line for line in body_lines if line.strip().startswith("•")]
        
        # Add paragraphs
        if paragraphs:
            parts.append("\n\n".join(paragraphs[:2]))  # Max 2 paragraphs
        
        # Add bullets
        if bullets:
            parts.append("\n".join(bullets[:4]))  # Max 4 bullets
    
    # Footer hint
    if footer_hint:
        parts.append(f"\n_{footer_hint}_")
    
    message_text = "\n\n".join(parts)
    
    # Validate length
    if not tone.validate_message_length(message_text, max_paragraphs=3, max_bullets=4):
        # Truncate if needed
        pass  # Already limited above
    
    # Build keyboard
    keyboard = None
    if buttons_rows:
        buttons = []
        for row in buttons_rows:
            button_row = [
                InlineKeyboardButton(text=text, callback_data=callback)
                for text, callback in row
            ]
            buttons.append(button_row)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    return message_text, keyboard


def success_panel(
    result_type: str,
    actions: Optional[List[tuple[str, str]]] = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """Render post-result action panel (variants/improve/save).
    
    Args:
        result_type: Type of result ("изображение", "видео", "аудио", "текст")
        actions: Optional custom actions, defaults to standard retention actions
    
    Returns:
        (message_text, keyboard_markup)
    """
    message_text = f"✅ Готово! Твоё {result_type} выше ⬆️"
    
    # Default retention actions
    if actions is None:
        actions = [
            ("✨ Сделать 3 варианта", "action:variants"),
            ("🎯 Улучшить под цель", "action:improve"),
            ("📌 Сохранить в проект", "action:save_project"),
            (tone.CTA_RETRY, "action:retry"),
            (tone.CTA_HOME, "main_menu"),
        ]
    
    # Organize into rows (2 per row for primary, 1 for navigation)
    buttons = []
    
    # Primary actions (2 per row)
    primary = actions[:-2]  # All except last 2 (retry, home)
    for i in range(0, len(primary), 2):
        row = primary[i:i+2]
        buttons.append([InlineKeyboardButton(text=text, callback_data=cb) for text, cb in row])
    
    # Navigation actions (1 per row)
    for text, callback in actions[-2:]:
        buttons.append([InlineKeyboardButton(text=text, callback_data=callback)])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    return message_text, keyboard


def progress_message(
    task_type: str,
    elapsed_seconds: int = 0,
    can_cancel: bool = True,
) -> tuple[str, Optional[InlineKeyboardMarkup]]:
    """Render progress message with cancel option.
    
    Args:
        task_type: Type of task ("генерация", "улучшение", "озвучка")
        elapsed_seconds: Seconds elapsed (for animation)
        can_cancel: Whether to show cancel button
    
    Returns:
        (message_text, keyboard_markup)
    """
    # Animated dots based on elapsed time
    dots_count = (elapsed_seconds // 5) % 4  # 0-3 dots, changes every 5s
    dots = "." * dots_count
    
    message_text = f"⏳ {task_type.capitalize()}{dots} (обычно до 1–2 мин)"
    
    keyboard = None
    if can_cancel:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel:current")]
        ])
    
    return message_text, keyboard


def error_recovery(
    error_type: str = "timeout",
    context: Optional[str] = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """Render error recovery options (no panic, clear actions).
    
    Args:
        error_type: Type of error ("timeout", "failed", "cancelled")
        context: Optional context info
    
    Returns:
        (message_text, keyboard_markup)
    """
    messages = {
        "timeout": "⏳ Долго. Что делаем?",
        "failed": "😔 Не получилось. Что делаем?",
        "cancelled": "✅ Отменил",
    }
    
    message_text = messages.get(error_type, "Что делаем?")
    if context:
        message_text += f"\n\n_{context}_"
    
    if error_type == "cancelled":
        # Simple return to menu
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=tone.CTA_HOME, callback_data="main_menu")]
        ])
    else:
        # Recovery options
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Повторить", callback_data="action:retry")],
            [InlineKeyboardButton(text="⏰ Подождать ещё", callback_data="action:wait")],
            [InlineKeyboardButton(text=tone.CTA_HOME, callback_data="main_menu")],
        ])
    
    return message_text, keyboard


def upsell_nudge(
    from_tier: str = "free",
    benefit: Optional[str] = None,
) -> str:
    """Generate gentle upsell line (1 line, not annoying).
    
    Args:
        from_tier: Current tier ("free", "basic")
        benefit: Optional specific benefit to highlight
    
    Returns:
        Single-line upsell text
    """
    if from_tier == "free":
        if benefit:
            return f"💡 {benefit} — открой {tone.CTA_POPULAR}"
        return f"💡 Хочешь качество выше / больше форматов? Открой {tone.CTA_POPULAR}"
    
    return ""
