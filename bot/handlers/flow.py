"""
Primary UX flow: categories -> models -> inputs -> confirmation -> generation.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.kie.builder import load_source_of_truth
from app.kie.validator import validate_input_type, ModelContractError
from app.payments.charges import get_charge_manager
from app.payments.integration import generate_with_payment
from app.payments.pricing import calculate_kie_cost, calculate_user_price, format_price_rub
from app.utils.validation import validate_url, validate_file_url, validate_text_input

logger = logging.getLogger(__name__)
router = Router(name="flow")


class FlowStates(StatesGroup):
    """States for flow handlers."""
    search_query = State()  # Waiting for model search query


CATEGORY_LABELS = {
    # Real categories from SOURCE_OF_TRUTH (v1.2.6)
    "image": "🎨 Картинки и дизайн",
    "video": "🎬 Видео",
    "audio": "🎵 Аудио",
    "music": "🎵 Музыка",
    "enhance": "✨ Улучшение качества",
    "avatar": "🧑‍🎤 Аватары",
    "other": "⭐ Другое",
    
    # Legacy format (backward compatibility)
    "text-to-image": "🎨 Создать картинку",
    "image-to-image": "✏️ Редактировать изображение",
    "text-to-video": "🎬 Создать видео",
    "image-to-video": "🎬 Оживить картинку",
    "video-to-video": "🎬 Редактировать видео",
    "text-to-speech": "🎵 Озвучка текста",
    "speech-to-text": "📝 Распознать речь",
    "audio-generation": "🎵 Создать музыку",
    "upscale": "✨ Улучшить качество",
    "ocr": "📝 Распознать текст",
    "lip-sync": "🎬 Lip Sync",
    "background-removal": "✂️ Убрать фон",
    "watermark-removal": "✂️ Убрать водяной знак",
    "music-generation": "🎵 Создать музыку",
    "sound-effects": "🔊 Звуковые эффекты",
    "general": "⭐ Разное",
    
    # Alternative names
    "creative": "🎨 Креатив",
    "voice": "🎙️ Голос и озвучка",
    "t2i": "🎨 Создать картинку",
    "i2i": "✏️ Редактировать изображение",
    "t2v": "🎬 Создать видео",
    "i2v": "🎬 Оживить картинку",
    "v2v": "🎬 Редактировать видео",
    "lip_sync": "🎬 Lip Sync",
    "music_old": "🎵 Музыка",
    "sfx": "🔊 Звуковые эффекты",
    "tts": "🎵 Озвучка",
    "stt": "📝 Распознать речь",
    "audio_isolation": "🎵 Очистить аудио",
    "bg_remove": "✂️ Убрать фон",
    "watermark_remove": "✂️ Убрать водяной знак",
}

WELCOME_BALANCE_RUB = float(os.getenv("WELCOME_BALANCE_RUB", "200"))


def _source_of_truth() -> Dict[str, Any]:
    return load_source_of_truth()


def _get_models_list() -> List[Dict[str, Any]]:
    """
    Получить список моделей из SOURCE_OF_TRUTH.
    Поддерживает оба формата: dict и list.
    """
    sot = _source_of_truth()
    models = sot.get("models", {})
    
    # Если dict - конвертируем в list
    if isinstance(models, dict):
        return list(models.values())
    # Если уже list - возвращаем как есть
    elif isinstance(models, list):
        return models
    else:
        return []


def _is_valid_model(model: Dict[str, Any]) -> bool:
    """Filter out technical/invalid models from registry."""
    model_id = model.get("model_id", "")
    if not model_id:
        return False
    
    # Check enabled flag
    if not model.get("enabled", True):
        return False
    
    # Check pricing exists
    pricing = model.get("pricing")
    if not pricing or not isinstance(pricing, dict):
        return False
    
    # Skip models with zero price AND no explicit free flag
    # (processors/technical entries have all zeros)
    rub_price = pricing.get("rub_per_use", 0)
    usd_price = pricing.get("usd_per_use", 0)
    
    if rub_price == 0 and usd_price == 0:
        # Allow if it's a known cheap model (will be free)
        # But skip if it's a technical entry
        if model_id.isupper() or "_processor" in model_id.lower():
            return False
    
    # Valid model must have either:
    # - vendor/name format (google/veo, flux/dev, etc.) OR
    # - simple name without uppercase/processor (z-image, grok-imagine, etc.)
    return True


def _models_by_category() -> Dict[str, List[Dict[str, Any]]]:
    models = [model for model in _get_models_list() if _is_valid_model(model)]
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for model in models:
        category = model.get("category", "other") or "other"
        grouped.setdefault(category, []).append(model)
    # Sort by price (cheapest first), then by name
    for model_list in grouped.values():
        model_list.sort(key=lambda item: (
            item.get("pricing", {}).get("rub_per_gen", 999999),
            (item.get("name") or item.get("model_id") or "").lower()
        ))
    return grouped


def _category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, category.replace("_", " ").title())


def _categories_from_registry() -> List[Tuple[str, str]]:
    grouped = _models_by_category()
    categories = sorted(grouped.keys(), key=lambda value: _category_label(value).lower())
    return [(category, _category_label(category)) for category in categories]


def _category_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"cat:{category}")]
        for category, label in _categories_from_registry()
    ]
    rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Main menu keyboard - task-oriented categories (production v3.0).
    
    ARCHITECTURE:
    - Shows 4 main categories: creative, music, voice, video
    - Dynamic: only shows categories with available models
    - Sorted by priority (creative → music → voice → video)
    - MASTER PROMPT: Includes "Best models" and "Search model" buttons
    """
    # Get actual categories from registry
    grouped = _models_by_category()
    
    # Build dynamic menu
    buttons = []
    
    # Priority mapping: category -> user-friendly label
    # Based on real categories from SOURCE_OF_TRUTH
    priority_map = [
        ('image', '🎨 Картинки и дизайн'),
        ('video', '🎬 Видео'),
        ('audio', '🎵 Аудио'),
        ('enhance', '✨ Улучшение качества'),
        ('avatar', '🧑‍🎤 Аватары'),
        ('music', '🎵 Музыка'),
    ]
    
    # Add buttons for existing categories
    for cat_id, label in priority_map:
        if cat_id in grouped and len(grouped[cat_id]) > 0:
            buttons.append([InlineKeyboardButton(text=label, callback_data=f"cat:{cat_id}")])
    
    # MASTER PROMPT: "Лучшие модели (curated)" + "Поиск модели"
    buttons.append([
        InlineKeyboardButton(text="⭐ Лучшие модели", callback_data="menu:best"),
        InlineKeyboardButton(text="🔍 Поиск модели", callback_data="menu:search"),
    ])
    
    # NEW: Quick actions row - Instagram, TikTok, YouTube
    buttons.append([
        InlineKeyboardButton(text="⚡ Быстрые действия", callback_data="quick:menu"),
    ])
    
    # NEW: Gallery row - Trending, Free
    buttons.append([
        InlineKeyboardButton(text="🔥 Trending", callback_data="gallery:trending"),
        InlineKeyboardButton(text="🆓 Free", callback_data="gallery:free"),
    ])
    
    # Browse all categories (if needed)
    if len(grouped) > 4:
        buttons.append([InlineKeyboardButton(text="📂 Все категории", callback_data="menu:categories")])
    
    # Bottom row: balance, history, help
    buttons.append([
        InlineKeyboardButton(text="💰 Баланс", callback_data="menu:balance"),
        InlineKeyboardButton(text="📜 История", callback_data="menu:history"),
    ])
    buttons.append([InlineKeyboardButton(text="❓ Помощь", callback_data="menu:help")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _help_menu_keyboard() -> InlineKeyboardMarkup:
    """Help menu with FAQ."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🆓 Как получить бесплатные генерации?", callback_data="help:free")],
            [InlineKeyboardButton(text="💳 Как пополнить баланс?", callback_data="help:topup")],
            [InlineKeyboardButton(text="📊 Как работает ценообразование?", callback_data="help:pricing")],
            [InlineKeyboardButton(text="🔧 Что делать при ошибке?", callback_data="help:errors")],
            [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
        ]
    )


def _main_menu_keyboard_OLD() -> InlineKeyboardMarkup:
    """
    Main menu keyboard with category shortcuts.
    
    ARCHITECTURE:
    - Quick access to most popular categories
    - All models accessible via category browser
    - Cheap/Free models highlighted
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            # Popular categories (auto-detect from registry)
            [InlineKeyboardButton(text="🎬 Видео (Reels/TikTok/Ads)", callback_data="cat:text-to-video")],
            [InlineKeyboardButton(text="🖼️ Картинка (баннер/пост/креатив)", callback_data="cat:text-to-image")],
            [InlineKeyboardButton(text="✨ Улучшить (апскейл/редакт)", callback_data="cat:upscale")],
            [InlineKeyboardButton(text="🎙️ Аудио (озвучка/музыка)", callback_data="cat:text-to-speech")],
            
            # Browse all
            [InlineKeyboardButton(text="🔎 Все модели (по категориям)", callback_data="menu:categories")],
            [InlineKeyboardButton(text="⭐ Дешёвые / Бесплатные", callback_data="menu:free")],
            
            # User actions
            [InlineKeyboardButton(text="🧾 История генераций", callback_data="menu:history")],
            [InlineKeyboardButton(text="💳 Баланс и пополнение", callback_data="menu:balance")],
        ]
    )


def _model_keyboard(models: List[Dict[str, Any]], back_cb: str, page: int = 0, per_page: int = 6) -> InlineKeyboardMarkup:
    """Create paginated model keyboard with prices."""
    rows: List[List[InlineKeyboardButton]] = []
    
    # Calculate pagination
    start = page * per_page
    end = start + per_page
    page_models = models[start:end]
    total_pages = (len(models) + per_page - 1) // per_page
    
    # Model buttons with PRICE indicators (MASTER PROMPT requirement)
    for model in page_models:
        model_id = model.get("model_id", "unknown")
        title = model.get("display_name") or model.get("name") or model_id
        price_rub = model.get("pricing", {}).get("rub_per_gen", 0)
        
        # Price tag
        if price_rub == 0:
            price_tag = "🆓"
        elif price_rub < 1.0:
            price_tag = f"{price_rub:.2f}₽"
        elif price_rub < 10.0:
            price_tag = f"{price_rub:.1f}₽"
        else:
            price_tag = f"{price_rub:.0f}₽"
        
        # Truncate long names
        max_name_len = 28
        if len(title) > max_name_len:
            title = title[:max_name_len-3] + "..."
        
        button_text = f"{title} • {price_tag}"
        rows.append([InlineKeyboardButton(text=button_text, callback_data=f"model:{model_id}")])
    
    # Pagination buttons
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Пред", callback_data=f"page:{back_cb}:{page-1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="След ▶️", callback_data=f"page:{back_cb}:{page+1}"))
        rows.append(nav_buttons)
    
    rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _model_detail_text(model: Dict[str, Any]) -> str:
    """
    Create human-friendly model card.
    
    PRODUCTION-READY:
    - Clear value proposition (what user gets)
    - Honest pricing (exact formula)
    - No technical jargon
    - Examples when available
    """
    name = model.get("display_name") or model.get("name") or model.get("model_id")
    model_id = model.get("model_id", "")
    vendor = model.get("vendor", "")
    
    # Description - human-friendly (v6.3.0 enrichment)
    description = model.get("description", "")
    if not description:
        # Enhanced fallback descriptions based on category
        category = model.get("category", "")
        fallback_descriptions = {
            "text-to-image": "Создаёт изображения по вашему описанию",
            "image": "Создаёт изображения по вашему описанию",
            "text-to-video": "Создаёт видео из текста",
            "video": "Создаёт и редактирует видео",
            "audio": "Работа с аудио: озвучка, музыка, обработка",
            "music": "Генерация музыки и звуковых эффектов",
            "upscale": "Улучшает качество изображений",
            "enhance": "Улучшает качество и редактирует медиа",
            "image-to-image": "Редактирует и улучшает изображения",
            "image-to-video": "Превращает картинку в видео",
            "avatar": "Создание анимированных аватаров и персонажей",
            "other": "AI генерация и обработка контента",
        }
        description = fallback_descriptions.get(category, "AI генерация контента")
    
    # Use-case from v6.3.0 enrichment
    use_case = model.get("use_case", "")
    
    # Example from v6.3.0 enrichment
    example = model.get("example", "")
    
    # Pricing - EXACT FORMULA
    from app.pricing.free_models import is_free_model
    
    if is_free_model(model_id):
        price_line = "💰 <b>Цена:</b> 🆓 БЕСПЛАТНО (FREE tier)"
    else:
        pricing = model.get("pricing", {})
        rub_per_use = pricing.get("rub_per_use")
        if rub_per_use:
            price_line = f"💰 <b>Цена:</b> {format_price_rub(rub_per_use)}"
        else:
            # Fallback calculation
            from app.payments.pricing import calculate_kie_cost, calculate_user_price
            kie_cost = calculate_kie_cost(model, {}, None)
            user_price = calculate_user_price(kie_cost)
            price_line = f"💰 <b>Цена:</b> {format_price_rub(user_price)}"
    
    # Parameters
    input_schema = model.get("input_schema", {})
    if 'properties' in input_schema:
        # Nested format
        required = input_schema.get("required", [])
        optional = input_schema.get("optional", [])
    else:
        # Flat format (source_of_truth.json)
        properties = input_schema
        required = [k for k, v in properties.items() if v.get('required', False)]
        optional = [k for k in properties.keys() if k not in required]
    
    params_total = len(required) + len(optional)
    if params_total == 0:
        params_line = "⚙️ <b>Параметры:</b> Не требуются"
    elif len(required) == 0:
        params_line = f"⚙️ <b>Параметры:</b> {params_total} опциональных"
    else:
        params_line = f"⚙️ <b>Параметры:</b> {len(required)} обязательных"
        if optional:
            params_line += f", {len(optional)} опциональных"
    
    # Vendor info
    if vendor:
        vendor_line = f"🏢 <b>Модель:</b> {vendor}"
    else:
        vendor_line = ""
    
    # Build card
    lines = [
        f"✨ <b>{name}</b>",
        "",
        f"📝 {description}",
    ]
    
    # Add use-case if available
    if use_case:
        lines.append("")
        lines.append(f"🎯 <b>Для чего:</b> {use_case[:200]}")  # Truncate to 200 chars
    
    lines.extend([
        "",
        price_line,
        params_line,
    ])
    
    if vendor_line:
        lines.append(vendor_line)
    
    # Add example from v6.3.0 enrichment
    if example:
        lines.append("")
        lines.append(f"💡 <b>Пример:</b> {example[:150]}")  # Truncate to 150 chars
    
    # Add tags if available
    tags = model.get("tags")
    if tags and isinstance(tags, list):
        lines.append("")
        tags_str = " • ".join(f"#{tag}" for tag in tags[:5])
        lines.append(f"🏷 {tags_str}")
    
    return "\n".join(lines)


def _model_detail_text_OLD(model: Dict[str, Any]) -> str:
    """Create human-friendly model card."""
    name = model.get("name") or model.get("model_id")
    model_id = model.get("model_id", "")
    
    # Check if price is preliminary (disabled_reason exists)
    price_warning = ""
    if model.get("disabled_reason"):
        price_warning = "\n\n⚠️ <i>Цена предварительная, актуализируется автоматически</i>"
    
    # Human-friendly description
    best_for = model.get("best_for") or model.get("description")
    if not best_for:
        # Generate description from model_id
        if "video" in model_id.lower():
            best_for = "Создание видео из текста или изображений"
        elif "image" in model_id.lower() or "flux" in model_id.lower():
            best_for = "Генерация изображений по описанию"
        elif "upscale" in model_id.lower():
            best_for = "Улучшение качества и разрешения изображений"
        elif "audio" in model_id.lower() or "tts" in model_id.lower():
            best_for = "Генерация голоса и озвучка текста"
        else:
            best_for = "Обработка и генерация контента"
    
    # Price formatting - CORRECT FORMULA: price_usd × 78 (USD→RUB) × 2 (markup)
    price_raw = model.get("price")
    if price_raw:
        try:
            price_usd = float(price_raw)
            if price_usd == 0:
                price_str = "Бесплатно"
            else:
                # Step 1: Convert USD to RUB (using calculate_kie_cost)
                kie_cost_rub = calculate_kie_cost(model, {}, None)
                # Step 2: Apply 2x markup for user price
                user_price_rub = calculate_user_price(kie_cost_rub)
                price_str = format_price_rub(user_price_rub)
        except (TypeError, ValueError):
            price_str = str(price_raw)
    else:
        price_str = "Уточняется"
    
    # ETA
    eta = model.get("eta")
    if eta:
        eta_str = f"~{eta} сек"
    else:
        # Estimate by category
        category = model.get("category", "")
        if "video" in category or "v2v" in category:
            eta_str = "~30-60 сек"
        elif "upscale" in category:
            eta_str = "~15-30 сек"
        else:
            eta_str = "~10-20 сек"
    
    # Example result
    input_schema = model.get("input_schema", {})
    required_fields = input_schema.get("required", [])
    if not required_fields:
        example = "Результат придет автоматически"
    elif len(required_fields) == 1:
        example = "Нужен 1 параметр"
    else:
        example = f"Нужно {len(required_fields)} параметра"
    
    return (
        f"✨ <b>{name}</b>\n\n"
        f"<b>Для чего:</b> {best_for}\n\n"
        f"<b>Что получите:</b> {example}\n"
        f"<b>Цена:</b> {price_str}\n"
        f"<b>Время:</b> {eta_str}"
        f"{price_warning}"
    )


def _model_detail_keyboard(model_id: str, back_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Сгенерировать", callback_data=f"gen:{model_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=back_cb)],
        ]
    )


class InputFlow(StatesGroup):
    waiting_input = State()
    confirm = State()


@dataclass
class InputContext:
    model_id: str
    required_fields: List[str]
    optional_fields: List[str]  # MASTER PROMPT: "Ввод ВСЕХ параметров (без автоподстановок)"
    properties: Dict[str, Any]
    collected: Dict[str, Any]
    index: int = 0
    collecting_optional: bool = False  # Track if collecting optional params


def _field_prompt(field_name: str, field_spec: Dict[str, Any]) -> str:
    """Generate human-friendly prompt with examples."""
    field_type = field_spec.get("type", "string")
    enum = field_spec.get("enum")
    max_length = field_spec.get("max_length")
    
    if enum:
        return f"Выберите значение для <b>{field_name}</b>:"
    
    if field_type in {"file", "file_id", "file_url"}:
        return (
            f"📎 <b>Загрузите файл</b>\n\n"
            f"Отправьте изображение, видео или документ для параметра: {field_name}"
        )
    
    if field_type in {"url", "link", "source_url"}:
        return (
            f"🔗 <b>Отправьте ссылку</b>\n\n"
            f"Вставьте URL для параметра: {field_name}\n\n"
            f"<i>Пример: https://example.com/image.jpg</i>"
        )
    
    # Text/prompt fields - make them human-friendly
    if field_name in {"prompt", "text", "description", "input"}:
        return (
            f"✍️ <b>Опишите, что вы хотите создать</b>\n\n"
            f"<i>Пример:</i>\n"
            f"\"Неоновый баннер для Instagram, стиль киберпанк, тёмный фон\""
        )
    
    if max_length:
        return (
            f"✍️ <b>Введите {field_name}</b>\n\n"
            f"Максимум {max_length} символов"
        )
    
    return f"✍️ <b>Введите {field_name}</b>"


def _enum_keyboard(field_spec: Dict[str, Any]) -> Optional[InlineKeyboardMarkup]:
    enum = field_spec.get("enum")
    if not enum:
        return None
    rows = [[InlineKeyboardButton(text=str(val), callback_data=f"enum:{val}")] for val in enum]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _coerce_value(value: Any, field_spec: Dict[str, Any]) -> Any:
    field_type = field_spec.get("type", "string")
    if field_type in {"integer", "int"}:
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if field_type in {"number", "float"}:
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    if field_type in {"boolean", "bool"}:
        if isinstance(value, str):
            return value.lower() in {"true", "1", "yes", "on"}
        return bool(value)
    return value


def _validate_field_value(value: Any, field_spec: Dict[str, Any], field_name: str) -> None:
    field_type = field_spec.get("type", "string")
    validate_input_type(value, field_type, field_name)
    if "enum" in field_spec:
        enum_values = field_spec.get("enum", [])
        if value not in enum_values:
            raise ModelContractError(
                f"Поле '{field_name}' должно быть одним из {enum_values}"
            )
    if field_type in {"string", "text", "prompt", "input", "message"}:
        max_length = field_spec.get("max_length")
        if max_length and isinstance(value, str) and len(value) > max_length:
            raise ModelContractError(
                f"Поле '{field_name}' должно быть не длиннее {max_length} символов"
            )
    minimum = field_spec.get("minimum")
    maximum = field_spec.get("maximum")
    if minimum is not None or maximum is not None:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return
        if minimum is not None and numeric_value < minimum:
            raise ModelContractError(
                f"Поле '{field_name}' должно быть >= {minimum}"
            )
        if maximum is not None and numeric_value > maximum:
            raise ModelContractError(
                f"Поле '{field_name}' должно быть <= {maximum}"
            )


@router.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext) -> None:
    """Start command - personalized welcome with quick-start guide."""
    await state.clear()
    
    # Get user info for personalization
    first_name = message.from_user.first_name or "друг"
    
    # Count available models
    models_list = _get_models_list()
    total_models = len([m for m in models_list if _is_valid_model(m) and m.get("enabled", True)])
    
    # Welcome message with quick-start guide
    await message.answer(
        f"👋 Привет, <b>{first_name}</b>!\n\n"
        f"🤖 Я помогу создать контент с помощью <b>{total_models} AI моделей</b>\n\n"
        f"<b>Что умею:</b>\n"
        f"📸 Картинки и дизайн — <b>от 0₽ (есть бесплатные!)</b>\n"
        f"🎬 Видео для TikTok/Reels — от 7.90₽\n"
        f"✨ Улучшение качества — от 0.20₽\n"
        f"🎵 Аудио и озвучка — от 0.08₽\n\n"
        f"💡 <b>Как начать?</b>\n"
        f"1️⃣ Выберите категорию или модель\n"
        f"2️⃣ Введите параметры (текст, изображение...)\n"
        f"3️⃣ Подтвердите и получите результат!\n\n"
        f"🆓 <b>4 бесплатные модели</b> для старта\n"
        f"💰 Старт с {WELCOME_BALANCE_RUB:.0f}₽ на балансе\n\n"
        f"Выбирайте задачу 👇",
        reply_markup=_main_menu_keyboard(),
    )


@router.callback_query(F.data == "main_menu")
async def main_menu_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    
    # Get user info
    first_name = callback.from_user.first_name or "друг"
    
    # Count models
    models_list = _get_models_list()
    total_models = len([m for m in models_list if _is_valid_model(m) and m.get("enabled", True)])
    
    await callback.message.edit_text(
        f"🎨 <b>Главное меню</b>\n\n"
        f"✨ {total_models} AI моделей для ваших задач\n\n"
        f"� <b>Категории:</b> Картинки, Видео, Аудио, Улучшение\n"
        f"⭐ <b>Лучшие:</b> Топ моделей по цене/качеству\n"
        f"🔍 <b>Поиск:</b> Найти нужную модель\n\n"
        f"🆓 4 бесплатные модели • Старт с {WELCOME_BALANCE_RUB:.0f}₽\n\n"
        f"Выберите действие 👇",
        reply_markup=_main_menu_keyboard(),
    )


@router.callback_query(F.data == "menu:help")
async def help_menu_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Show help menu."""
    await callback.answer()
    await callback.message.edit_text(
        "❓ Помощь и FAQ\n\nВыберите вопрос:",
        reply_markup=_help_menu_keyboard(),
    )


@router.callback_query(F.data == "help:free")
async def help_free_cb(callback: CallbackQuery) -> None:
    """Explain free tier."""
    await callback.answer()
    from app.pricing.free_models import get_free_models
    
    free_models = get_free_models()
    await callback.message.edit_text(
        f"🆓 **Бесплатные генерации**\n\n"
        f"У нас есть {len(free_models)} бесплатных моделей (TOP-{len(free_models)} самые дешёвые):\n\n"
        f"Эти модели доступны ВСЕМ пользователям без списания баланса.\n\n"
        f"📍 Найти их: Главное меню → Все категории → выбрать любую категорию\n"
        f"💡 Модели с ценой 0.16₽ - 0.39₽ - это FREE tier",
        reply_markup=_help_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "help:topup")
async def help_topup_cb(callback: CallbackQuery) -> None:
    """Explain how to top up balance."""
    await callback.answer()
    await callback.message.edit_text(
        "💳 **Пополнение баланса**\n\n"
        "1. Нажмите 'Баланс' в главном меню\n"
        "2. Выберите сумму пополнения\n"
        "3. Оплатите по реквизитам\n"
        "4. Отправьте скриншот оплаты боту\n"
        "5. Баланс пополнится автоматически (OCR проверка)\n\n"
        "⚡️ Обычно обработка занимает 1-2 минуты\n\n"
        "❗️ Если баланс не пополнился - напишите в поддержку",
        reply_markup=_help_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "help:pricing")
async def help_pricing_cb(callback: CallbackQuery) -> None:
    """Explain pricing model."""
    await callback.answer()
    await callback.message.edit_text(
        "📊 **Ценообразование**\n\n"
        "Цена каждой генерации зависит от модели:\n\n"
        "• 🆓 FREE: 0₽ (топ-5 самых дешёвых)\n"
        "• 💚 Cheap: 0.40₽ - 10₽\n"
        "• 💛 Mid: 10₽ - 50₽\n"
        "• 🔴 Expensive: 50₽+\n\n"
        "Цена показывается ПЕРЕД запуском генерации.\n"
        "Списание происходит только после подтверждения.\n\n"
        "Формула: price_usd × 78.59 (курс) × 2.0 (наценка)\n\n"
        "💡 Начните с бесплатных моделей!",
        reply_markup=_help_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "help:errors")
async def help_errors_cb(callback: CallbackQuery) -> None:
    """Explain error handling."""
    await callback.answer()
    await callback.message.edit_text(
        "🔧 **Что делать при ошибке?**\n\n"
        "**Ошибка генерации:**\n"
        "• Деньги вернутся автоматически (auto-refund)\n"
        "• Проверьте баланс через 'История'\n\n"
        "**Ошибка оплаты:**\n"
        "• Убедитесь что сумма совпадает\n"
        "• Скриншот чёткий и читаемый\n"
        "• Попробуйте ещё раз\n\n"
        "**Модель не работает:**\n"
        "• Попробуйте другую модель\n"
        "• Проверьте параметры (формат, размер)\n\n"
        "❗️ Если проблема не решилась - напишите /support",
        reply_markup=_help_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "menu:best")
async def best_models_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Show curated list of best models (MASTER PROMPT requirement).
    
    CRITERIA:
    - TOP cheapest models first (best value)
    - Quality: Most reliable models from registry
    - Use case coverage: Different types (image, video, audio, enhance)
    - Price: Mix of FREE and paid
    """
    await callback.answer()
    await state.clear()
    
    # Get all models sorted by price
    models = _get_models_list()
    valid_models = [m for m in models if _is_valid_model(m)]
    
    # Sort by price (cheapest first)
    valid_models.sort(key=lambda m: m.get("pricing", {}).get("rub_per_gen", 999999))
    
    # Take top 15 best value models
    best_models = valid_models[:15]
    
    # Build keyboard with price indicators
    buttons = []
    for model in best_models:
        model_id = model.get("model_id", "")
        name = model.get("display_name") or model.get("name") or model_id
        price_rub = model.get("pricing", {}).get("rub_per_gen", 0)
        category = model.get("category", "other")
        
        # Add price + category tags
        if price_rub == 0:
            price_tag = "🆓"
        elif price_rub < 1.0:
            price_tag = "💚"
        elif price_rub < 5.0:
            price_tag = "💛"
        else:
            price_tag = "💰"
        
        # Category emoji
        cat_emoji = {
            "image": "🎨",
            "video": "🎬",
            "audio": "🎵",
            "music": "🎵",
            "enhance": "✨",
            "avatar": "🧑‍🎤",
        }.get(category, "⭐")
        
        # Truncate long names
        if len(name) > 30:
            name = name[:27] + "..."
        
        button_text = f"{price_tag} {cat_emoji} {name}"
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"model:{model_id}"
        )])
    
    buttons.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    
    await callback.message.edit_text(
        "⭐ <b>Лучшие модели</b>\n\n"
        "Топ-15 моделей с лучшим соотношением цена/качество:\n\n"
        "🆓 Бесплатно (0₽)\n"
        "💚 Очень дёшево (<1₽)\n"
        "💛 Дёшево (<5₽)\n"
        "💰 Доступно (5₽+)\n\n"
        "Выберите модель:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data == "menu:search")
async def search_models_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Start model search flow (MASTER PROMPT requirement).
    
    FLOW:
    1. User enters search query
    2. Bot searches in: model_id, name, description, category
    3. Shows matching models (max 10)
    """
    await callback.answer()
    await state.set_state(FlowStates.search_query)
    
    await callback.message.edit_text(
        "🔍 **Поиск модели**\n\n"
        "Введите название модели или описание (например: 'видео', 'музыка', 'flux', 'kling'):\n\n"
        "Или нажмите 'Отмена' чтобы вернуться.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")]
        ]),
        parse_mode="Markdown"
    )


@router.message(FlowStates.search_query)
async def process_search_query(message: Message, state: FSMContext) -> None:
    """Process model search query."""
    query = message.text.strip().lower()
    
    if len(query) < 2:
        await message.answer("Введите минимум 2 символа для поиска.")
        return
    
    # Get registry
    from app.kie.registry import get_model_registry
    registry = get_model_registry()
    
    # Search in all fields
    matches = []
    for model_id, model in registry.items():
        searchable_text = " ".join([
            model_id,
            model.get("name", ""),
            model.get("description", ""),
            model.get("category", ""),
        ]).lower()
        
        if query in searchable_text:
            matches.append((model_id, model))
    
    # Limit results
    matches = matches[:10]
    
    if not matches:
        await message.answer(
            f"❌ По запросу '{query}' ничего не найдено.\n\n"
            f"Попробуйте другой запрос или вернитесь в меню.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
            ])
        )
        await state.clear()
        return
    
    # Build results keyboard
    buttons = []
    for model_id, model in matches:
        name = model.get("name", model_id)
        price = model.get("pricing", {}).get("rub_per_use", 0)
        
        # Add price tag
        if price < 0.5:
            price_tag = "🆓"
        elif price < 10:
            price_tag = "💚"
        elif price < 50:
            price_tag = "💛"
        else:
            price_tag = "🔴"
        
        button_text = f"{price_tag} {name}"
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"model:{model_id}"
        )])
    
    buttons.append([InlineKeyboardButton(text="🔍 Новый поиск", callback_data="menu:search")])
    buttons.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    
    await message.answer(
        f"🔍 Найдено моделей: {len(matches)}\n\n"
        f"По запросу: '{query}'\n\n"
        f"Выберите модель:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.clear()


@router.callback_query(F.data == "menu:generate")
async def generate_menu_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "🚀 Генерация\n\nВыберите категорию:",
        reply_markup=_category_keyboard(),
    )


@router.callback_query(F.data == "menu:all_categories")
async def all_categories_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Show all categories - DEPRECATED, use menu:categories instead."""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "📂 Все категории\n\nВыберите категорию:",
        reply_markup=_category_keyboard(),
    )


@router.callback_query(F.data == "menu:categories")
async def categories_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Show all models grouped by category."""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "📂 Все модели по категориям\n\nВыберите категорию:",
        reply_markup=_category_keyboard(),
    )


@router.callback_query(F.data == "menu:free")
async def free_models_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Show TOP-5 cheapest (free) models."""
    await callback.answer()
    await state.clear()
    
    try:
        from app.pricing.free_models import get_free_models, get_model_price
        
        free_ids = get_free_models()
        
        if not free_ids:
            await callback.message.edit_text(
                "⚠️ Бесплатные модели временно недоступны",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
                ])
            )
            return
        
        # Get full model info
        all_models = _get_models_list()
        free_models = [m for m in all_models if m["model_id"] in free_ids]
        
        # Build message
        lines = ["⭐ **Дешёвые / Бесплатные модели**\n"]
        lines.append("Эти модели можно использовать бесплатно (TOP-5 самых дешёвых):\n")
        
        for i, model in enumerate(free_models, 1):
            display_name = model.get("display_name", model["model_id"])
            category = _category_label(model.get("category", "other"))
            lines.append(f"{i}. **{display_name}** ({category})")
        
        lines.append("\n💡 Выберите модель ниже для генерации:")
        
        # Build keyboard
        rows = []
        for model in free_models:
            display_name = model.get("display_name", model["model_id"])
            # Truncate long names
            if len(display_name) > 30:
                display_name = display_name[:27] + "..."
            rows.append([
                InlineKeyboardButton(
                    text=f"🆓 {display_name}",
                    callback_data=f"model:{model['model_id']}"
                )
            ])
        
        rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
        
        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            parse_mode="Markdown"
        )
    
    except Exception as e:
        logger.error(f"Failed to show free models: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ Ошибка при загрузке бесплатных моделей",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
            ])
        )


@router.callback_query(F.data == "menu:edit")
async def edit_menu_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    # Show editing categories
    edit_categories = ["i2i", "upscale", "bg_remove", "watermark_remove"]
    grouped = _models_by_category()
    rows = []
    for cat in edit_categories:
        if cat in grouped and grouped[cat]:
            label = _category_label(cat)
            rows.append([InlineKeyboardButton(text=label, callback_data=f"cat:{cat}")])
    rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    await callback.message.edit_text(
        "✏️ Редактирование\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data == "menu:audio")
async def audio_menu_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    # Show audio categories
    audio_categories = ["tts", "stt", "music", "sfx", "audio_isolation"]
    grouped = _models_by_category()
    rows = []
    for cat in audio_categories:
        if cat in grouped and grouped[cat]:
            label = _category_label(cat)
            rows.append([InlineKeyboardButton(text=label, callback_data=f"cat:{cat}")])
    if not rows:
        rows.append([InlineKeyboardButton(text="⚠️ Аудио модели скоро появятся", callback_data="noop")])
    rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    await callback.message.edit_text(
        "🎧 Аудио / Озвучка\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data == "menu:top")
async def top_menu_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    # Top models - based on popularity/price
    all_models = [m for m in _get_models_list() if _is_valid_model(m)]
    
    # Sort by: has price, then by category popularity
    popular_categories = ["t2i", "t2v", "i2i", "upscale"]
    top_models = []
    
    for cat in popular_categories:
        cat_models = [m for m in all_models if m.get("category") == cat]
        if cat_models:
            top_models.append(cat_models[0])  # First model from each popular category
    
    if not top_models:
        top_models = all_models[:5]  # Fallback to first 5
    
    await state.update_data(top_models=True)
    await callback.message.edit_text(
        "⭐ Лучшие модели\n\nПопулярные и проверенные нейросети:",
        reply_markup=_model_keyboard(top_models, "main_menu", page=0),
    )


class SearchFlow(StatesGroup):
    waiting_query = State()


@router.callback_query(F.data == "menu:search")
async def search_menu_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SearchFlow.waiting_query)
    await callback.message.edit_text(
        "🔎 Поиск модели\n\n"
        "Введите название модели или ключевые слова (например: flux, kling, video, upscale):",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]]
        ),
    )


@router.message(SearchFlow.waiting_query, F.text)
async def search_query_handler(message: Message, state: FSMContext) -> None:
    query = (message.text or "").lower().strip()
    if not query:
        await message.answer("⚠️ Введите поисковый запрос.")
        return
    
    await state.clear()
    
    # Search models
    all_models = [m for m in _get_models_list() if _is_valid_model(m)]
    matches = []
    for model in all_models:
        model_id = model.get("model_id", "").lower()
        name = (model.get("name") or "").lower()
        desc = (model.get("description") or "").lower()
        best_for = (model.get("best_for") or "").lower()
        
        if query in model_id or query in name or query in desc or query in best_for:
            matches.append(model)
    
    if not matches:
        await message.answer(
            f"❌ По запросу '{query}' ничего не найдено.\n\n"
            "Попробуйте другие ключевые слова.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔎 Новый поиск", callback_data="menu:search")],
                    [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
                ]
            ),
        )
        return
    
    # Show results
    await state.update_data(category_models=matches)
    await message.answer(
        f"🔎 Найдено моделей: {len(matches)}\n\nВыберите модель:",
        reply_markup=_model_keyboard(matches, "menu:search", page=0),
    )


@router.callback_query(F.data.in_({"support", "menu:support"}))
async def support_cb(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "ℹ️ <b>Поддержка</b>\n\n"
        "Если у вас возникли вопросы или проблемы:\n\n"
        "📧 Email: support@example.com\n"
        "💬 Telegram: @support_bot\n\n"
        "Мы отвечаем в течение 24 часов.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
            ]
        ),
    )


@router.callback_query(F.data.in_({"balance", "menu:balance"}))
async def balance_cb(callback: CallbackQuery) -> None:
    await callback.answer()
    balance = get_charge_manager().get_user_balance(callback.from_user.id)
    await callback.message.edit_text(
        f"💰 Баланс: {format_price_rub(balance)}\n\n"
        "Пополнение временно доступно через поддержку.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="ℹ️ Поддержка", callback_data="menu:support")],
                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
            ]
        ),
    )


@router.callback_query(F.data == "menu:history")
async def history_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    history = get_charge_manager().get_user_history(callback.from_user.id, limit=10)
    
    if not history:
        await callback.message.edit_text(
            "🕘 История генераций пуста.\n\n"
            "Создайте свою первую генерацию!",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]]
            ),
        )
        return
    
    # Show history
    text_lines = ["🕘 <b>Последние генерации:</b>\n"]
    rows = []
    for idx, record in enumerate(history[:5]):
        model_id = record.get('model_id', 'unknown')
        success = record.get('success', False)
        timestamp = record.get('timestamp', '')[:16]  # YYYY-MM-DDTHH:MM
        status_icon = "✅" if success else "❌"
        text_lines.append(f"{status_icon} {model_id} - {timestamp}")
        # Add repeat button
        if success and idx < 3:  # Only first 3
            rows.append([InlineKeyboardButton(text=f"🔁 {model_id}", callback_data=f"repeat:{idx}")])
    
    text_lines.append("\nНажмите 🔁 чтобы повторить генерацию.")
    rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("repeat:"))
async def repeat_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    idx_str = callback.data.split(":", 1)[1]
    try:
        idx = int(idx_str)
    except ValueError:
        await callback.message.edit_text("⚠️ Ошибка.")
        return
    
    history = get_charge_manager().get_user_history(callback.from_user.id, limit=10)
    if idx >= len(history):
        await callback.message.edit_text("⚠️ Генерация не найдена.")
        return
    
    record = history[idx]
    model_id = record.get('model_id')
    inputs = record.get('inputs', {})
    
    # Re-run generation with same inputs
    model = next((m for m in _get_models_list() if m.get("model_id") == model_id), None)
    if not model:
        await callback.message.edit_text("⚠️ Модель не найдена.")
        return
    
    price_raw = model.get("price") or 0
    try:
        amount = float(price_raw)
    except (TypeError, ValueError):
        amount = 0.0
    
    charge_manager = get_charge_manager()
    balance = charge_manager.get_user_balance(callback.from_user.id)
    if amount > 0 and balance < amount:
        await callback.message.edit_text(
            "❌ Недостаточно средств для повтора.\n\n"
            f"Стоимость: {format_price_rub(amount)}\n"
            f"Баланс: {format_price_rub(balance)}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Пополнить", callback_data="menu:balance")],
                    [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
                ]
            ),
        )
        return
    
    await callback.message.edit_text("⏳ Повторная генерация запущена...")
    
    def heartbeat(text: str) -> None:
        asyncio.create_task(callback.message.answer(text))
    
    charge_task_id = f"repeat_{callback.from_user.id}_{callback.message.message_id}"
    result = await generate_with_payment(
        model_id=model_id,
        user_inputs=inputs,
        user_id=callback.from_user.id,
        amount=amount,
        progress_callback=heartbeat,
        task_id=charge_task_id,
        reserve_balance=True,
    )
    
    if result.get("success"):
        urls = result.get("result_urls") or []
        if urls:
            await callback.message.answer("\n".join(urls))
        else:
            await callback.message.answer("✅ Готово!")
        await callback.message.answer(
            "Что дальше?",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔁 Ещё раз", callback_data=f"repeat:{idx}")],
                    [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")],
                ]
            ),
        )
    else:
        await callback.message.answer(result.get("message", "❌ Ошибка"))
        await callback.message.answer(
            "Попробовать ещё?",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔁 Повторить", callback_data=f"repeat:{idx}")],
                    [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")],
                ]
            ),
        )


@router.callback_query(F.data.startswith("cat:"))
async def category_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    category = callback.data.split(":", 1)[1]
    grouped = _models_by_category()
    models = grouped.get(category, [])

    if not models:
        category_label = _category_label(category)
        await callback.message.edit_text(
            f"⚠️ {category_label}\n\n"
            f"В этой категории пока нет доступных моделей.\n"
            f"Попробуйте другую категорию или вернитесь в меню.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📂 Все категории", callback_data="menu:categories")],
                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
            ])
        )
        return

    await state.update_data(category=category, category_models=models)
    await callback.message.edit_text(
        f"Категория: {_category_label(category)}\n\nВыберите модель:",
        reply_markup=_model_keyboard(models, f"cat:{category}", page=0),
    )


@router.callback_query(F.data.startswith("page:"))
async def page_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle pagination callbacks."""
    await callback.answer()
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        return
    
    back_cb = parts[1]
    try:
        page = int(parts[2])
    except ValueError:
        return
    
    data = await state.get_data()
    
    # Get models from state
    models = data.get("category_models")
    if not models:
        # Fallback: try to get from category
        if back_cb.startswith("cat:"):
            category = back_cb.split(":", 1)[1]
            grouped = _models_by_category()
            models = grouped.get(category, [])
    
    if not models:
        await callback.answer("⚠️ Модели не найдены", show_alert=True)
        return
    
    await callback.message.edit_reply_markup(
        reply_markup=_model_keyboard(models, back_cb, page=page)
    )


@router.callback_query(F.data == "noop")
async def noop_cb(callback: CallbackQuery) -> None:
    """No-op callback for pagination display."""
    await callback.answer()


@router.callback_query(F.data.startswith("model:"))
async def model_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    model_id = callback.data.split(":", 1)[1]
    model = next((m for m in _get_models_list() if m.get("model_id") == model_id), None)
    if not model:
        await callback.message.edit_text("⚠️ Модель не найдена.", reply_markup=_category_keyboard())
        return

    data = await state.get_data()
    back_cb = "menu:generate"
    category = data.get("category")
    if category:
        back_cb = f"cat:{category}"

    await state.update_data(model_id=model_id)
    await callback.message.edit_text(
        _model_detail_text(model),
        reply_markup=_model_detail_keyboard(model_id, back_cb),
    )


@router.callback_query(F.data.startswith("gen:"))
async def generate_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    model_id = callback.data.split(":", 1)[1]
    model = next((m for m in _get_models_list() if m.get("model_id") == model_id), None)
    if not model:
        await callback.message.edit_text("⚠️ Модель не найдена.", reply_markup=_category_keyboard())
        return

    input_schema = model.get("input_schema", {})
    
    # Support BOTH flat and nested formats (like builder.py)
    if 'properties' in input_schema:
        # Nested format
        required_fields = input_schema.get("required", [])
        optional_fields = input_schema.get("optional", [])
        properties = input_schema.get("properties", {})
    else:
        # Flat format (source_of_truth.json) - convert
        properties = input_schema
        required_fields = [k for k, v in properties.items() if v.get('required', False)]
        optional_fields = [k for k in properties.keys() if k not in required_fields]
    
    ctx = InputContext(
        model_id=model_id,
        required_fields=required_fields,
        optional_fields=optional_fields,
        properties=properties,
        collected={},
        collecting_optional=False
    )
    await state.update_data(flow_ctx=ctx.__dict__)

    if not required_fields:
        await _show_confirmation(callback.message, state, model)
        return

    field_name = required_fields[0]
    field_spec = properties.get(field_name, {})
    await state.set_state(InputFlow.waiting_input)
    await callback.message.answer(
        _field_prompt(field_name, field_spec),
        reply_markup=_enum_keyboard(field_spec),
    )


@router.callback_query(F.data.startswith("enum:"), InputFlow.waiting_input)
async def enum_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    value = callback.data.split(":", 1)[1]
    await _save_input_and_continue(callback.message, state, value)


@router.callback_query(F.data == "opt_skip_all")
async def opt_skip_all_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Skip all optional parameters and proceed to confirmation (MASTER PROMPT)."""
    await callback.answer("Используем значения по умолчанию")
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    model = next((m for m in _get_models_list() if m.get("model_id") == flow_ctx.model_id), None)
    await _show_confirmation(callback.message, state, model)


@router.callback_query(F.data.startswith("opt_start:"))
async def opt_start_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Start collecting a specific optional parameter (MASTER PROMPT compliance)."""
    await callback.answer()
    field_name = callback.data.split(":", 1)[1]
    
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    
    # Find index of this optional field
    try:
        opt_index = flow_ctx.optional_fields.index(field_name)
    except ValueError:
        await callback.message.answer("⚠️ Параметр не найден.")
        return
    
    # Switch to collecting optional params
    flow_ctx.collecting_optional = True
    flow_ctx.index = opt_index
    await state.update_data(flow_ctx=flow_ctx.__dict__)
    
    # Show input prompt
    field_spec = flow_ctx.properties.get(field_name, {})
    await state.set_state(InputFlow.waiting_input)
    await callback.message.answer(
        _field_prompt(field_name, field_spec),
        reply_markup=_enum_keyboard(field_spec),
    )


@router.message(InputFlow.waiting_input)
async def input_message(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    
    # Determine which field we're collecting
    if flow_ctx.collecting_optional:
        current_fields = flow_ctx.optional_fields
    else:
        current_fields = flow_ctx.required_fields
    
    field_name = current_fields[flow_ctx.index]
    field_spec = flow_ctx.properties.get(field_name, {})
    field_type = field_spec.get("type", "string")

    if field_type in {"file", "file_id", "file_url"}:
        file_id = None
        if message.photo:
            file_id = message.photo[-1].file_id
        elif message.document:
            file_id = message.document.file_id
        elif message.video:
            file_id = message.video.file_id
        elif message.audio:
            file_id = message.audio.file_id
        if not file_id and message.text and message.text.startswith(("http://", "https://")):
            # Validate URL before accepting
            is_valid, error = validate_url(message.text)
            if not is_valid:
                await message.answer(f"⚠️ Некорректная ссылка: {error}\n\nПопробуйте снова.")
                return
            
            # Additional validation for file URLs
            is_valid, error = validate_file_url(message.text, file_type="image")
            if not is_valid:
                await message.answer(f"⚠️ {error}\n\nПопробуйте снова.")
                return
            
            await _save_input_and_continue(message, state, message.text)
            return
        if not file_id:
            await message.answer("⚠️ Нужен файл. Отправьте фото/документ/видео/аудио.")
            return
        await _save_input_and_continue(message, state, file_id)
        return

    if field_type in {"url", "link", "source_url"}:
        if not message.text:
            await message.answer("⚠️ Ожидается ссылка (http/https).")
            return
        
        # Validate URL
        is_valid, error = validate_url(message.text)
        if not is_valid:
            await message.answer(f"⚠️ Некорректная ссылка: {error}\n\nПопробуйте снова.")
            return
        
        await _save_input_and_continue(message, state, message.text)
        return

    value = message.text
    if value is None:
        await message.answer("⚠️ Ожидается текстовое значение.")
        return
    
    # Validate text input length
    is_valid, error = validate_text_input(value, max_length=10000)
    if not is_valid:
        await message.answer(f"⚠️ {error}\n\nПопробуйте снова.")
        return
    
    await _save_input_and_continue(message, state, value)


async def _ask_optional_params(message: Message, state: FSMContext, flow_ctx: InputContext) -> None:
    """Ask user if they want to configure optional parameters (MASTER PROMPT compliance)."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    # Build keyboard with all optional params (mark configured ones with ✓)
    buttons = []
    for opt_field in flow_ctx.optional_fields:
        field_spec = flow_ctx.properties.get(opt_field, {})
        default = field_spec.get("default")
        
        # Check if already configured
        is_configured = opt_field in flow_ctx.collected
        
        if is_configured:
            button_text = f"✓ {opt_field}: {flow_ctx.collected[opt_field]}"
        else:
            button_text = f"○ {opt_field}"
            if default is not None:
                button_text += f" (default: {default})"
        
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"opt_start:{opt_field}")])
    
    # Add "Finish" or "Skip all" button
    any_configured = any(opt in flow_ctx.collected for opt in flow_ctx.optional_fields)
    if any_configured:
        buttons.append([InlineKeyboardButton(text="✅ Готово, перейти к подтверждению", callback_data="opt_skip_all")])
    else:
        buttons.append([InlineKeyboardButton(text="⏭ Пропустить все (использовать defaults)", callback_data="opt_skip_all")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Show status of parameters
    configured_count = sum(1 for opt in flow_ctx.optional_fields if opt in flow_ctx.collected)
    total_count = len(flow_ctx.optional_fields)
    
    await message.answer(
        f"🎛 <b>Дополнительные параметры</b> ({configured_count}/{total_count} настроено)\n\n"
        f"✓ = настроено\n"
        f"○ = default значение\n\n"
        f"Выберите параметр для настройки:",
        reply_markup=keyboard
    )


async def _save_input_and_continue(message: Message, state: FSMContext, value: Any) -> None:
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    
    # Determine which field list we're working on
    if flow_ctx.collecting_optional:
        current_fields = flow_ctx.optional_fields
    else:
        current_fields = flow_ctx.required_fields
    
    field_name = current_fields[flow_ctx.index]
    field_spec = flow_ctx.properties.get(field_name, {})
    value = _coerce_value(value, field_spec)

    try:
        _validate_field_value(value, field_spec, field_name)
    except ModelContractError as e:
        await message.answer(f"⚠️ {e}")
        return

    flow_ctx.collected[field_name] = value
    
    # CRITICAL UX FIX: If collecting optional, RETURN to optional menu after each param
    # This allows flexible configuration of ANY optional params
    if flow_ctx.collecting_optional:
        # Reset to allow selecting another optional param
        flow_ctx.index = 0
        flow_ctx.collecting_optional = False
        await state.update_data(flow_ctx=flow_ctx.__dict__)
        await _ask_optional_params(message, state, flow_ctx)
        return
    
    # For required fields, continue sequentially
    flow_ctx.index += 1
    await state.update_data(flow_ctx=flow_ctx.__dict__)

    # Check if we finished required fields
    if flow_ctx.index >= len(current_fields):
        # If we finished required and have optional fields, offer to configure them
        if flow_ctx.optional_fields:
            await _ask_optional_params(message, state, flow_ctx)
            return
        
        # Otherwise, show confirmation
        model = next((m for m in _get_models_list() if m.get("model_id") == flow_ctx.model_id), None)
        await _show_confirmation(message, state, model)
        return

    # Continue to next required field
    next_field = current_fields[flow_ctx.index]
    next_spec = flow_ctx.properties.get(next_field, {})
    await message.answer(
        _field_prompt(next_field, next_spec),
        reply_markup=_enum_keyboard(next_spec),
    )


async def _show_confirmation(message: Message, state: FSMContext, model: Optional[Dict[str, Any]]) -> None:
    """Show canonical confirmation screen."""
    if not model:
        await message.answer("⚠️ Модель не найдена.")
        return
    
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    
    model_name = model.get("name") or model.get("model_id")
    
    # Price formatting - CORRECT FORMULA: price_usd × 78 (USD→RUB) × 2 (markup)
    price_usd = model.get("price") or 0
    try:
        if price_usd == 0:
            price_str = "Бесплатно"
        else:
            # Step 1: Convert USD to RUB (using calculate_kie_cost)
            kie_cost_rub = calculate_kie_cost(model, {}, None)
            # Step 2: Apply 2x markup for user price
            user_price_rub = calculate_user_price(kie_cost_rub)
            price_str = format_price_rub(user_price_rub)
    except (TypeError, ValueError):
        price_str = "Цена не определена"
    
    # ETA
    eta = model.get("eta")
    if eta:
        eta_str = f"~{eta} сек"
    else:
        category = model.get("category", "")
        if "video" in category:
            eta_str = "~30-60 сек"
        elif "upscale" in category:
            eta_str = "~15-30 сек"
        else:
            eta_str = "~10-20 сек"
    
    # What user will get
    output_type = model.get("output_type", "url")
    if output_type == "url":
        result_desc = "Ссылка на результат"
    elif "video" in str(model.get("category", "")):
        result_desc = "Видеофайл"
    elif "image" in str(model.get("category", "")):
        result_desc = "Изображение"
    else:
        result_desc = "Файл результата"
    
    # Format parameters - show ALL (required + optional) with defaults for missing optional
    # MASTER PROMPT: "Ввод ВСЕХ параметров (без автоподстановок)"
    params_lines = []
    
    # Show collected parameters
    for k, v in flow_ctx.collected.items():
        # Truncate long values
        v_str = str(v)
        if len(v_str) > 60:
            v_str = v_str[:57] + "..."
        params_lines.append(f"✓ {k}: {v_str}")
    
    # Show optional parameters that weren't collected (with defaults)
    for opt_field in flow_ctx.optional_fields:
        if opt_field not in flow_ctx.collected:
            field_spec = flow_ctx.properties.get(opt_field, {})
            default = field_spec.get("default", "auto")
            params_lines.append(f"○ {opt_field}: {default} (default)")
    
    if params_lines:
        params_str = "\n".join(params_lines)
    else:
        params_str = "Параметры по умолчанию"
    
    balance = get_charge_manager().get_user_balance(message.from_user.id)
    
    await state.set_state(InputFlow.confirm)
    await message.answer(
        f"🔍 <b>Проверьте заказ</b>\n\n"
        f"<b>Модель:</b> {model_name}\n"
        f"<b>Задача:</b>\n{params_str}\n\n"
        f"💰 <b>Стоимость генерации:</b> {price_str}\n"
        f"📌 <b>Цена сформирована на основе тарифа модели</b>\n"
        f"⏱ <b>Ожидание:</b> {eta_str}\n"
        f"📦 <b>Получите:</b> {result_desc}\n\n"
        f"💳 <b>Ваш баланс:</b> {format_price_rub(balance)}\n\n"
        f"ℹ️ <i>Деньги спишутся ТОЛЬКО при успешной генерации</i>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Запустить", callback_data="confirm")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
            ]
        ),
    )


@router.callback_query(F.data == "cancel", InputFlow.confirm)
async def cancel_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "❌ Отменено. Возврат в меню.",
        reply_markup=_main_menu_keyboard()
    )


@router.callback_query(F.data == "confirm", InputFlow.confirm)
async def confirm_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    model = next((m for m in _get_models_list() if m.get("model_id") == flow_ctx.model_id), None)
    if not model:
        await callback.message.edit_text("⚠️ Модель не найдена.")
        await state.clear()
        return

    price_raw = model.get("price") or 0
    try:
        amount = float(price_raw)
    except (TypeError, ValueError):
        amount = 0.0

    charge_manager = get_charge_manager()
    balance = charge_manager.get_user_balance(callback.from_user.id)
    if amount > 0 and balance < amount:
        await callback.message.edit_text(
            "❌ Недостаточно средств для запуска.\n\n"
            f"Цена: {amount:.2f}\n"
            f"Баланс: {balance:.2f}\n\n"
            "Пополните баланс и попробуйте снова.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Баланс / Оплата", callback_data="menu:balance")],
                    [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
                ]
            ),
        )
        await state.clear()
        return

    # Send initial progress message
    # MASTER PROMPT: "7. Прогресс / ETA" - TRANSPARENCY: show model and prompt
    # SECURITY: Escape user input to prevent XSS (MASTER PROMPT: no vulnerabilities)
    from app.utils.html import escape_html
    
    # Initial progress message with model and inputs info
    model_name = _get_models_list()
    model_display = "Unknown"
    for m in model_name:
        if m.get("model_id") == flow_ctx.model_id:
            model_display = m.get("name") or flow_ctx.model_id
            break

    # Format inputs for display - ESCAPE USER INPUT
    inputs_preview = ""
    if "prompt" in flow_ctx.collected:
        prompt_text = flow_ctx.collected["prompt"]
        if len(prompt_text) > 50:
            prompt_text = prompt_text[:50] + "..."
        # CRITICAL: Escape HTML to prevent XSS
        prompt_text_safe = escape_html(prompt_text)
        inputs_preview = f"Промпт: {prompt_text_safe}\n"

    progress_msg = await callback.message.edit_text(
        f"⏳ <b>Генерация запущена</b>\n\n"
        f"Модель: {escape_html(model_display)}\n"
        f"{inputs_preview}"
        f"Инициализация...",
        parse_mode="HTML"
    )

    # MASTER PROMPT: "7. Прогресс / ETA"
    # Update SAME message instead of creating new ones
    def heartbeat(text: str) -> None:
        asyncio.create_task(progress_msg.edit_text(text, parse_mode="HTML"))

    charge_task_id = f"charge_{callback.from_user.id}_{callback.message.message_id}"
    result = await generate_with_payment(
        model_id=flow_ctx.model_id,
        user_inputs=flow_ctx.collected,
        user_id=callback.from_user.id,
        amount=amount,
        progress_callback=heartbeat,
        task_id=charge_task_id,
        reserve_balance=True,
    )

    await state.clear()

    if result.get("success"):
        urls = result.get("result_urls") or []
        if urls:
            await callback.message.answer("\n".join(urls))
        else:
            await callback.message.answer("✅ Готово!")
        await callback.message.answer(
            "Что дальше?",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔁 Повторить", callback_data=f"gen:{flow_ctx.model_id}")],
                    [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")],
                ]
            ),
        )
    else:
        # MASTER PROMPT: "10. Возможный refund при ошибке"
        # Show error + refund notification
        error_msg = result.get("message", "❌ Ошибка")
        payment_status = result.get("payment_status", "")
        
        # Check if refund happened
        if payment_status == "released" or "refund" in payment_status.lower():
            refund_notice = "\n\n💰 <b>Средства возвращены на ваш баланс</b>"
        else:
            refund_notice = ""
        
        await callback.message.answer(f"{error_msg}{refund_notice}")
        await callback.message.answer(
            "Попробовать ещё раз?",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔁 Повторить", callback_data=f"gen:{flow_ctx.model_id}")],
                    [InlineKeyboardButton(text="💳 Баланс", callback_data="balance:main")],
                    [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")],
                ]
            ),
        )


@router.callback_query()
async def fallback_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer("⚠️ Кнопка устарела. Нажмите /start.")
