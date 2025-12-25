"""
Enhanced model gallery with examples - Syntx-like experience
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.fsm.context import FSMContext
import json
from pathlib import Path

router = Router(name="gallery")

# Load recommendations
RECOMMENDATIONS_PATH = Path("artifacts/model_recommendations.json")

def load_recommendations():
    """Load model recommendations"""
    if not RECOMMENDATIONS_PATH.exists():
        return {}
    with open(RECOMMENDATIONS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

# Example prompts gallery for popular models
EXAMPLE_GALLERY = {
    "flux-2/flex-text-to-image": {
        "name": "Flux-2 Text to Image",
        "examples": [
            {
                "prompt": "Неоновый баннер для Instagram, стиль киберпанк, тёмный фон",
                "use_case": "Instagram post",
                "description": "Идеально для соцсетей"
            },
            {
                "prompt": "Логотип для стартапа в сфере AI, минимализм, векторный стиль",
                "use_case": "Logo design",
                "description": "Для бизнеса"
            },
            {
                "prompt": "Обложка для YouTube видео про путешествия, яркие цвета",
                "use_case": "YouTube thumbnail",
                "description": "Для YouTube"
            }
        ]
    },
    "sora-2-text-to-video": {
        "name": "Sora2 Text to Video",
        "examples": [
            {
                "prompt": "Таймлапс восхода солнца над океаном, 5 секунд",
                "use_case": "Reels/TikTok",
                "description": "Для коротких видео"
            },
            {
                "prompt": "Анимация логотипа с эффектом появления, 3 секунды",
                "use_case": "Intro/Outro",
                "description": "Для видео-интро"
            }
        ]
    },
    "z-image": {
        "name": "Z-Image (FREE)",
        "examples": [
            {
                "prompt": "Красивый закат на пляже",
                "use_case": "General",
                "description": "Бесплатно!"
            }
        ]
    }
}


@router.callback_query(F.data == "gallery:trending")
async def show_trending_gallery(callback: CallbackQuery, state: FSMContext):
    """Show trending models with example gallery"""
    await callback.answer()
    
    recs = load_recommendations()
    trending = recs.get('quick_actions', {}).get('trending', [])
    
    if not trending:
        await callback.message.edit_text(
            "🔥 <b>Trending модели</b>\\n\\n"
            "Скоро появятся популярные модели!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
            ])
        )
        return
    
    # Build gallery buttons
    buttons = []
    for model_id in trending[:5]:  # Top 5 trending
        model_name = model_id.split('/')[-1].replace('-', ' ').title()
        buttons.append([
            InlineKeyboardButton(
                text=f"🔥 {model_name}",
                callback_data=f"gallery:show:{model_id}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    
    await callback.message.edit_text(
        "🔥 <b>Trending сейчас</b>\\n\\n"
        "Самые популярные модели с примерами использования:\\n\\n"
        "👆 Выберите модель чтобы посмотреть примеры",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("gallery:show:"))
async def show_model_gallery(callback: CallbackQuery, state: FSMContext):
    """Show example gallery for specific model"""
    await callback.answer()
    
    model_id = callback.data.split(":", 2)[2]
    gallery = EXAMPLE_GALLERY.get(model_id, {})
    
    if not gallery:
        await callback.message.edit_text(
            f"📸 <b>Примеры для {model_id}</b>\\n\\n"
            "Скоро добавим примеры использования!\\n\\n"
            "А пока можете попробовать создать что-то своё 🎨",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✨ Попробовать", callback_data=f"model:{model_id}")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="gallery:trending")]
            ])
        )
        return
    
    examples = gallery.get('examples', [])
    name = gallery.get('name', model_id)
    
    # Build examples text
    examples_text = f"📸 <b>{name}</b>\\n\\n<b>Примеры использования:</b>\\n\\n"
    
    for idx, ex in enumerate(examples, 1):
        examples_text += (
            f"{idx}. <b>{ex['use_case']}</b>\\n"
            f"   <i>{ex['description']}</i>\\n"
            f"   Prompt: \"{ex['prompt']}\"\\n\\n"
        )
    
    examples_text += "💡 Выберите пример или создайте свой!"
    
    # Build buttons - examples + try button
    buttons = []
    for idx, ex in enumerate(examples):
        buttons.append([
            InlineKeyboardButton(
                text=f"✨ {ex['use_case']}",
                callback_data=f"example:use:{model_id}:{idx}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(text="🎨 Свой промпт", callback_data=f"model:{model_id}")
    ])
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="gallery:trending")
    ])
    
    await callback.message.edit_text(
        examples_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("example:use:"))
async def use_example(callback: CallbackQuery, state: FSMContext):
    """Use example prompt directly"""
    await callback.answer("Используем пример!")
    
    parts = callback.data.split(":")
    model_id = parts[2]
    example_idx = int(parts[3])
    
    gallery = EXAMPLE_GALLERY.get(model_id, {})
    examples = gallery.get('examples', [])
    
    if example_idx >= len(examples):
        await callback.message.answer("⚠️ Пример не найден")
        return
    
    example = examples[example_idx]
    prompt = example['prompt']
    
    # Pre-fill prompt and redirect to generation
    await state.update_data(
        model_id=model_id,
        prompt=prompt,
        from_example=True
    )
    
    # Show confirmation with pre-filled prompt
    await callback.message.edit_text(
        f"✨ <b>Создаём с примером!</b>\\n\\n"
        f"<b>Модель:</b> {gallery.get('name', model_id)}\\n"
        f"<b>Промпт:</b> {prompt}\\n\\n"
        f"Начинаем генерацию?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, создать!", callback_data=f"gen:{model_id}")],
            [InlineKeyboardButton(text="✏️ Изменить промпт", callback_data=f"model:{model_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"gallery:show:{model_id}")]
        ])
    )


@router.callback_query(F.data == "gallery:free")
async def show_free_models(callback: CallbackQuery, state: FSMContext):
    """Show FREE models with quick start"""
    await callback.answer()
    
    recs = load_recommendations()
    free_models = recs.get('quick_actions', {}).get('free', [])
    
    buttons = []
    for model_id in free_models:
        model_name = model_id.split('/')[-1].replace('-', ' ').title()
        buttons.append([
            InlineKeyboardButton(
                text=f"🆓 {model_name}",
                callback_data=f"model:{model_id}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    
    await callback.message.edit_text(
        "🆓 <b>Бесплатные модели</b>\\n\\n"
        "Попробуйте без списания баланса!\\n\\n"
        "✨ Полностью бесплатно\\n"
        "🚀 Без лимитов\\n"
        "💯 Высокое качество\\n\\n"
        "Выберите модель:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
