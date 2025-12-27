"""Retention panel: variants, improve, save after successful generation."""
import logging
from typing import Dict, Optional, List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.ui import tone

log = logging.getLogger(__name__)


async def get_variants_prompt(
    original_prompt: str,
    variant_number: int,
    format_type: str,
) -> str:
    """Generate prompt for variant (adds seed variation locally).
    
    Args:
        original_prompt: Original user prompt
        variant_number: Variant number (1, 2, 3)
        format_type: Format type
    
    Returns:
        Modified prompt for variant
    """
    # Simple variation: add variant marker
    # Different models may interpret this differently for diversity
    
    variation_hints = {
        1: "вариант 1, немного другой ракурс",
        2: "вариант 2, другая композиция",
        3: "вариант 3, альтернативный стиль",
    }
    
    hint = variation_hints.get(variant_number, f"вариант {variant_number}")
    
    return f"{original_prompt}, {hint}"


async def get_improvement_goals() -> List[tuple[str, str, str]]:
    """Get improvement goal options.
    
    Returns:
        List of (goal_id, title, description) tuples
    """
    return [
        ("ctr", "📈 Больше кликов (CTR)", "Оптимизация под клики и внимание"),
        ("conversion", "💰 Больше продаж", "Фокус на конверсию и оффер"),
        ("premium", "✨ Премиум-вид", "Люксовый стиль, высокое качество"),
        ("viral", "🔥 Виральность", "Цепляющий контент для шеринга"),
        ("cheap", "💸 Бюджетно", "Снизить стоимость без потери качества"),
    ]


async def apply_improvement_goal(
    original_prompt: str,
    goal_id: str,
    format_type: str,
) -> str:
    """Apply improvement goal to prompt (template-based).
    
    Args:
        original_prompt: Original prompt
        goal_id: Goal ID from get_improvement_goals()
        format_type: Format type
    
    Returns:
        Enhanced prompt
    """
    improvements = {
        "ctr": "яркие контрастные цвета, крупный текст, эмоциональные лица, динамика",
        "conversion": "чёткий оффер, призыв к действию, социальные доказательства, срочность",
        "premium": "минимализм, дорогие материалы, мягкое освещение, элегантная типографика",
        "viral": "неожиданный ракурс, юмор, провокация, мем-эстетика, высокая контрастность",
        "cheap": "простая композиция, меньше деталей, stock-friendly",
    }
    
    improvement_text = improvements.get(goal_id, "")
    
    if improvement_text:
        return f"{original_prompt}, оптимизация: {improvement_text}"
    
    return original_prompt


def build_retention_panel(
    result_type: str,
    task_id: Optional[str] = None,
    show_variants: bool = True,
    show_improve: bool = True,
    show_save: bool = True,
) -> InlineKeyboardMarkup:
    """Build post-result action panel.
    
    Args:
        result_type: Type of result ("image", "video", "audio", "text")
        task_id: Optional task ID for context
        show_variants: Show variants button
        show_improve: Show improve button
        show_save: Show save to project button
    
    Returns:
        Keyboard markup
    """
    buttons = []
    
    # Primary retention actions
    row1 = []
    if show_variants:
        row1.append(InlineKeyboardButton(
            text="✨ Сделать 3 варианта",
            callback_data=f"retention:variants:{task_id or 'current'}"
        ))
    
    if show_improve:
        row1.append(InlineKeyboardButton(
            text="🎯 Улучшить под цель",
            callback_data=f"retention:improve:{task_id or 'current'}"
        ))
    
    if row1:
        buttons.append(row1)
    
    # Secondary actions
    row2 = []
    if show_save:
        row2.append(InlineKeyboardButton(
            text="📌 Сохранить в проект",
            callback_data=f"retention:save:{task_id or 'current'}"
        ))
    
    row2.append(InlineKeyboardButton(
        text=tone.CTA_RETRY,
        callback_data=f"retention:retry:{task_id or 'current'}"
    ))
    
    buttons.append(row2)
    
    # Navigation
    buttons.append([InlineKeyboardButton(text=tone.CTA_HOME, callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_improvement_goals_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for improvement goal selection.
    
    Returns:
        Keyboard markup
    """
    import asyncio
    
    # Get goals synchronously for keyboard builder
    goals = [
        ("ctr", "📈 Больше кликов (CTR)"),
        ("conversion", "💰 Больше продаж"),
        ("premium", "✨ Премиум-вид"),
        ("viral", "🔥 Виральность"),
        ("cheap", "💸 Бюджетно"),
    ]
    
    buttons = []
    
    # 2 per row
    for i in range(0, len(goals), 2):
        row = []
        for goal_id, title in goals[i:i+2]:
            row.append(InlineKeyboardButton(
                text=title,
                callback_data=f"improve_goal:{goal_id}"
            ))
        buttons.append(row)
    
    # Back button
    buttons.append([InlineKeyboardButton(text=tone.CTA_BACK, callback_data="cancel_improve")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_project_list_keyboard(
    projects: List[Dict],
    allow_new: bool = True,
) -> InlineKeyboardMarkup:
    """Build keyboard for project selection.
    
    Args:
        projects: List of project dicts
        allow_new: Show "create new project" option
    
    Returns:
        Keyboard markup
    """
    buttons = []
    
    # Existing projects (max 8 to show)
    for project in projects[:8]:
        project_id = project.get("project_id")
        project_name = project.get("name", "Без названия")
        gen_count = project.get("generation_count", 0)
        
        buttons.append([InlineKeyboardButton(
            text=f"📁 {project_name} ({gen_count})",
            callback_data=f"select_project:{project_id}"
        )])
    
    # New project option
    if allow_new:
        buttons.append([InlineKeyboardButton(
            text="➕ Создать новый проект",
            callback_data="create_new_project"
        )])
    
    # Back
    buttons.append([InlineKeyboardButton(text=tone.CTA_BACK, callback_data="cancel_save")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def format_result_type(format_id: str) -> str:
    """Get display name for result type.
    
    Args:
        format_id: Format ID
    
    Returns:
        Display name in nominative case
    """
    mapping = {
        "text-to-image": "изображение",
        "image-to-image": "изображение",
        "text-to-video": "видео",
        "image-to-video": "видео",
        "text-to-audio": "аудио",
        "audio-to-audio": "аудио",
        "image-upscale": "улучшенное изображение",
        "background-remove": "изображение без фона",
    }
    
    return mapping.get(format_id, "результат")
