"""Premium onboarding flow: first success in 30 seconds.

GOAL: Get user to first result FAST via goal-based flow.
NO model selection initially — just "what do you want to make?"
"""
import logging
from typing import Optional, Dict, List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.ui import tone
from app.ui.layout import render_screen

log = logging.getLogger(__name__)

# In-memory first-run tracking (DB fallback handled in caller)
_first_run_users: set[int] = set()


def mark_onboarding_complete(user_id: int):
    """Mark user as having completed onboarding."""
    _first_run_users.add(user_id)  # Add to set (= has completed)


def is_first_run(user_id: int, from_db: Optional[bool] = None) -> bool:
    """Check if user is first-time.
    
    Args:
        user_id: User ID
        from_db: DB result if available (None = check memory)
    
    Returns:
        True if first run
    """
    if from_db is not None:
        return from_db
    
    # Memory fallback: if NOT in set, it's first run
    return user_id not in _first_run_users


def get_onboarding_goals() -> List[tuple[str, str, str]]:
    """Get onboarding goal options.
    
    Returns:
        List of (goal_id, button_text, description) tuples
    """
    return [
        ("ads", "📈 Реклама (клики/лиды)", "Баннеры, креативы, посадочные страницы"),
        ("reels", "🎬 Reels/TikTok (сценарий/видео)", "Короткие вирусные видео для соцсетей"),
        ("design", "🖼️ Дизайн (обложки/баннеры)", "Обложки, посты, визуал для блога"),
        ("ecommerce", "🛒 Товар (карточки/магазин)", "Продуктовые фото, карточки товаров"),
        ("audio", "🎧 Голос (озвучка/звук)", "Озвучка текста, голосовые клоны, музыка"),
        ("quick_free", "⚡ Быстро попробовать (FREE)", "Бесплатные модели, мгновенный старт"),
    ]


def build_onboarding_screen() -> tuple[str, InlineKeyboardMarkup]:
    """Build onboarding screen 1: goal selection.
    
    Returns:
        (message_text, keyboard)
    """
    goals = get_onboarding_goals()
    
    body_lines = [
        "Создавай изображения, видео, аудио за минуту. Выбери цель:",
    ]
    
    # Build buttons (1 per row for clarity)
    button_rows = []
    for goal_id, button_text, _ in goals:
        button_rows.append([(button_text, f"onboarding_goal:{goal_id}")])
    
    # Skip option
    button_rows.append([(f"⏭️ Пропустить обучение", "skip_onboarding")])
    
    return render_screen(
        title="👋 Что ты хочешь сделать?",
        body_lines=body_lines,
        buttons_rows=button_rows,
        footer_hint="Первый результат — за ~1 минуту",
    )


async def get_recommended_presets_for_goal(
    goal_id: str,
    all_presets: List[Dict],
) -> List[Dict]:
    """Get 3 recommended presets for goal.
    
    Args:
        goal_id: Goal ID from onboarding
        all_presets: All available presets
    
    Returns:
        List of 3 preset dicts
    """
    # Map goals to preset categories
    goal_to_category = {
        "ads": "ads",
        "reels": "reels",
        "design": "branding",
        "ecommerce": "ecommerce",
        "audio": "audio",
        "quick_free": None,  # Show free models instead
    }
    
    category = goal_to_category.get(goal_id)
    
    if category:
        # Filter by category
        matching = [p for p in all_presets if p.get("category") == category]
        return matching[:3]
    
    # For quick_free, return first 3 presets
    return all_presets[:3]


def build_goal_presets_screen(
    goal_id: str,
    presets: List[Dict],
) -> tuple[str, InlineKeyboardMarkup]:
    """Build screen showing recommended presets for goal.
    
    Args:
        goal_id: Goal ID
        presets: List of recommended presets
    
    Returns:
        (message_text, keyboard)
    """
    goal_names = {
        "ads": "реклама",
        "reels": "Reels/TikTok",
        "design": "дизайн",
        "ecommerce": "товары",
        "audio": "аудио",
        "quick_free": "быстрый старт",
    }
    
    goal_name = goal_names.get(goal_id, "твоя цель")
    
    body_lines = [
        f"Лучшие варианты для: **{goal_name}**",
        "Выбери готовый сценарий или создай свой:",
    ]
    
    # Buttons: 3 presets + "Все пресеты"
    button_rows = []
    
    for preset in presets[:3]:
        preset_id = preset.get("id")
        preset_title = preset.get("title", "Пресет")
        button_rows.append([(f"🧩 {preset_title}", f"use_preset:{preset_id}")])
    
    # All presets option
    button_rows.append([("📋 Все пресеты", "show_all_presets")])
    
    # Skip to free models (quick start)
    if goal_id != "quick_free":
        button_rows.append([("⚡ Быстро попробовать FREE", "show_free_models")])
    
    # Back
    button_rows.append([(tone.CTA_BACK, "restart_onboarding")])
    
    return render_screen(
        title="🎯 Рекомендуем для тебя",
        body_lines=body_lines,
        buttons_rows=button_rows,
        footer_hint="Первый запуск бесплатный для пробы",
    )


def build_skip_confirmation() -> tuple[str, InlineKeyboardMarkup]:
    """Build skip onboarding confirmation.
    
    Returns:
        (message_text, keyboard)
    """
    body_lines = [
        "Окей, перейдём сразу к делу!",
        "В главном меню найдёшь:",
        "• 🧩 Пресеты — готовые сценарии",
        "• 🔥 Бесплатные — модели без оплаты",
        "• ⭐ Популярное — лучшие модели",
    ]
    
    button_rows = [
        [(tone.CTA_HOME, "main_menu")],
    ]
    
    return render_screen(
        title="✅ Поехали",
        body_lines=body_lines,
        buttons_rows=button_rows,
    )


async def track_onboarding_completion(
    user_id: int,
    goal_selected: str,
    preset_used: Optional[str] = None,
    pool=None,
):
    """Track onboarding completion (analytics).
    
    Args:
        user_id: User ID
        goal_selected: Goal ID selected
        preset_used: Preset ID if used
        pool: DB pool (optional)
    """
    try:
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO onboarding_stats (user_id, goal_selected, preset_used, completed_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (user_id) DO UPDATE
                    SET goal_selected = $2, preset_used = $3, completed_at = NOW()
                    """,
                    user_id,
                    goal_selected,
                    preset_used,
                )
    except Exception as e:
        log.warning(f"Failed to track onboarding: {e}")
    
    # Mark complete in memory
    mark_onboarding_complete(user_id)
