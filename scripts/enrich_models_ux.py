#!/usr/bin/env python3
"""
Enrich models with UX data: descriptions, use-cases, examples.

Исправляет ТОП-5 UX проблем:
1. Нормализация категорий (дубликаты)
2. Добавление use-case описаний
3. Улучшение display_name
4. Добавление примеров использования  
5. Добавление тегов для поиска
"""
import json
from pathlib import Path
from typing import Dict, List

# Category normalization mapping
CATEGORY_NORMALIZATION = {
    "text to video": "text-to-video",
    "image to image": "image-to-image",
    "video to video": "video-to-video",
    "image to video": "image-to-video",
    "text to image": "text-to-image",
}

# Use-case templates by category
USE_CASES = {
    "text-to-image": {
        "description": "Генерация изображений по текстовому описанию",
        "use_case": "Создание иллюстраций, баннеров, концепт-артов для соцсетей, презентаций, рекламы. Идеально для визуализации идей без навыков рисования.",
        "example": "космонавт на Марсе, фотореализм, закат, 4K",
        "tags": ["креатив", "дизайн", "иллюстрация", "визуализация"]
    },
    "image-to-image": {
        "description": "Трансформация и обработка изображений",
        "use_case": "Изменение стиля, редактирование, улучшение качества фото. Подходит для редизайна, стилизации, обработки продуктовых фото.",
        "example": "Загрузите фото → получите в стиле аниме/картины/3D",
        "tags": ["редактирование", "стилизация", "обработка", "улучшение"]
    },
    "text-to-video": {
        "description": "Генерация видео из текстового описания",
        "use_case": "Создание видеоконтента для Reels, Shorts, TikTok, рекламных роликов. Отлично для маркетинга, презентаций, образовательного контента.",
        "example": "кот играет с клубком шерсти, замедленная съемка, 1080p",
        "tags": ["видео", "reels", "shorts", "анимация", "маркетинг"]
    },
    "image-to-video": {
        "description": "Создание видео из статичного изображения",
        "use_case": "Анимация постеров, оживление иллюстраций, создание динамичных превью. Подходит для соцсетей, презентаций, рекламы.",
        "example": "Загрузите фото → получите 5-секундное видео с движением",
        "tags": ["анимация", "видео", "оживление", "динамика"]
    },
    "video-to-video": {
        "description": "Обработка и трансформация видео",
        "use_case": "Изменение стиля видео, улучшение качества, спецэффекты. Идеально для постпродакшна, креативной обработки.",
        "example": "Загрузите видео → примените стиль аниме/киберпанк",
        "tags": ["обработка", "эффекты", "стилизация", "улучшение"]
    },
    "video-generation": {
        "description": "Генерация видео с расширенными возможностями",
        "use_case": "Профессиональное создание видеоконтента с контролем над параметрами. Для креативных проектов, рекламы, контента.",
        "example": "Опишите сцену → получите видео с нужной длительностью и разрешением",
        "tags": ["видео", "генерация", "продвинутое", "профессионально"]
    },
    "upscale": {
        "description": "Увеличение разрешения изображений",
        "use_case": "Улучшение качества для печати, больших экранов, профессионального использования. Восстановление деталей старых фото.",
        "example": "Загрузите 720p → получите 4K",
        "tags": ["улучшение", "качество", "4K", "апскейл"]
    },
    "bg_remove": {
        "description": "Удаление фона с изображений",
        "use_case": "Быстрая подготовка фото для каталогов, маркетплейсов, презентаций. Создание прозрачных PNG.",
        "example": "Загрузите фото товара → получите без фона",
        "tags": ["обработка", "фон", "товары", "каталог"]
    },
    "tts": {
        "description": "Озвучка текста голосом",
        "use_case": "Создание аудио для видео, подкастов, аудиокниг, презентаций. Профессиональная озвучка без диктора.",
        "example": "Введите текст → получите MP3 с озвучкой",
        "tags": ["озвучка", "аудио", "голос", "TTS"]
    },
    "music": {
        "description": "Генерация музыки и аудио",
        "use_case": "Создание фоновой музыки для видео, подкастов, презентаций. Уникальные треки без авторских прав.",
        "example": "спокойная фоновая музыка, ambient, 2 минуты",
        "tags": ["музыка", "аудио", "фон", "саундтрек"]
    },
}

# Display name improvements
DISPLAY_NAME_IMPROVEMENTS = {
    # Wan models
    "wan/2-5-image-to-video": "Wan 2.5 Image-to-Video",
    "wan/2-5-text-to-video": "Wan 2.5 Text-to-Video",
    "wan/2-5-image-to-video:default-10.0s-720p-v2": "Wan 2.5 (720p 10s)",
    "wan/2-2-image-to-video": "Wan 2.2 Image-to-Video",
    "wan/2-2-image-to-video:5.0s-720p-v2": "Wan 2.2 (720p 5s)",
    "wan/2-2-image-to-video:5.0s-580p-v3": "Wan 2.2 (580p 5s)",
    "wan/2-2-text-to-video": "Wan 2.2 Text-to-Video",
    "wan/2-2-text-to-video:5.0s-480p-v2": "Wan 2.2 (480p 5s)",
    "wan/2-2-text-to-video:5.0s-720p-v3": "Wan 2.2 (720p 5s)",
    "wan-2-2-animate:1-0s-720p": "Wan 2.2 Animate (720p)",
    "wan-2-2-animate:1-0s-580p": "Wan 2.2 Animate (580p)",
    "wan-2-2-animate:1-0s-480p": "Wan 2.2 Animate (480p)",
    "wan/2-6-image-to-video": "Wan 2.6 Image-to-Video",
    "wan/2-6-image-to-video:without-audio-10.0s-v2": "Wan 2.6 (No Audio 10s)",
    "wan/2-6-video-to-video": "Wan 2.6 Video-to-Video",
    "wan/2-6-text-to-video": "Wan 2.6 Text-to-Video",
    "wan/2-6-text-to-video:without-audio-10.0s-v2": "Wan 2.6 (No Audio 10s)",
    
    # Veo
    "veo3.1/text-to-video-fast": "Google Veo 3.1 Fast",
    
    # Grok
    "grok-imagine/image-to-video": "Grok Imagine (Image→Video)",
    "grok-imagine/text-to-video": "Grok Imagine (Text→Video)",
    "grok-imagine/text-to-image": "Grok Imagine (Text→Image)",
    
    # Qwen
    "qwen/z-image": "Qwen Z-Image",
    
    # Kling
    "kling/2-1-text-to-video:standard-5.0s": "Kling 2.1 Text-to-Video (Standard 5s)",
    "kling/2-1-text-to-video:standard-10.0s": "Kling 2.1 Text-to-Video (Standard 10s)",
    "kling/2-1-image-to-video:standard-5.0s": "Kling 2.1 Image-to-Video (Standard 5s)",
    "kling/2-1-image-to-video:standard-10.0s": "Kling 2.1 Image-to-Video (Standard 10s)",
    "kling/2-1-text-to-video:pro-5.0s": "Kling 2.1 Text-to-Video (Pro 5s)",
    "kling/2-1-text-to-video:pro-10.0s": "Kling 2.1 Text-to-Video (Pro 10s)",
    "kling/2-1-text-to-video:master-5.0s": "Kling 2.1 Text-to-Video (Master 5s)",
    "kling/2-1-text-to-video:master-10.0s": "Kling 2.1 Text-to-Video (Master 10s)",
    "kling/2-6-image-to-video": "Kling 2.6 Image-to-Video",
    "kling/2-6-text-to-video": "Kling 2.6 Text-to-Video",
    
    # Google
    "google/imagen4": "Google Imagen 4",
    "google/imagen4:fast-v2": "Google Imagen 4 Fast",
    "google/imagen4:ultra-v3": "Google Imagen 4 Ultra",
    
    # Recraft
    "recraft/remove-background": "Recraft Remove Background",
    "recraft/upscale:crisp-v1": "Recraft Crisp Upscale",
    
    # Midjourney
    "midjourney": "Midjourney",
    "midjourney:relax": "Midjourney Relax",
    
    # Hailuo
    "hailuo-2.3": "Hailuo 2.3",
    "hailuo/2.3-image-to-video": "Hailuo 2.3 Image-to-Video",
    "hailuo-video-v2": "Hailuo Video V2",
    "hailuo/02-text-to-video": "Hailuo 0.2 Text-to-Video",
    "hailuo/02-image-to-video": "Hailuo 0.2 Image-to-Video",
    
    # Sora
    "sora-2-pro-storyboard": "Sora 2 Pro Storyboard",
    
    # Other
    "nano-banana-pro": "Nano Banana Pro",
    "suno-v4": "Suno V4",
    "ideogram/v3-remix": "Ideogram V3 Remix",
    "ideogram/v3-remix:quality-v2": "Ideogram V3 Remix Quality",
    "ideogram/v3-remix:turbo-v3": "Ideogram V3 Remix Turbo",
    "ideogram/v3-edit": "Ideogram V3 Edit",
    "ideogram/v3-edit:balanced-v2": "Ideogram V3 Edit Balanced",
    "ideogram/v3-edit:turbo-v3": "Ideogram V3 Edit Turbo",
    "ideogram/v3": "Ideogram V3",
    "ideogram/v3:turbo-v2": "Ideogram V3 Turbo",
    "ideogram/v3:balanced-v3": "Ideogram V3 Balanced",
    "hunyuan-imagine": "Hunyuan Imagine",
    "hunyuan-imagine-turbo": "Hunyuan Imagine Turbo",
    "flux/1.1-pro": "Flux 1.1 Pro",
    "flux/1.1-pro-ultra": "Flux 1.1 Pro Ultra",
    "flux/1.1-dev": "Flux 1.1 Dev",
    "stable-diffusion/ultra": "Stable Diffusion Ultra",
}


def normalize_category(category: str) -> str:
    """Normalize category name."""
    return CATEGORY_NORMALIZATION.get(category, category)


def get_ux_data(category: str) -> Dict:
    """Get UX data for category."""
    # Try normalized category first
    norm_cat = normalize_category(category)
    
    # Try exact match
    if norm_cat in USE_CASES:
        return USE_CASES[norm_cat]
    
    # Try fuzzy match
    for key in USE_CASES:
        if key in norm_cat or norm_cat in key:
            return USE_CASES[key]
    
    # Default fallback
    return {
        "description": "AI генерация контента",
        "use_case": "Универсальная модель для создания контента с помощью искусственного интеллекта.",
        "example": "Введите параметры → получите результат",
        "tags": ["ai", "генерация", "контент"]
    }


def improve_display_name(model_id: str, current_name: str) -> str:
    """Improve display name."""
    # Check manual mapping first
    if model_id in DISPLAY_NAME_IMPROVEMENTS:
        return DISPLAY_NAME_IMPROVEMENTS[model_id]
    
    # If current name is technical (contains /), try to improve
    if '/' in current_name:
        # Extract vendor and model parts
        parts = model_id.split('/')
        if len(parts) == 2:
            vendor, model = parts
            
            # Capitalize vendor
            vendor_nice = vendor.capitalize()
            
            # Improve model name
            model_nice = model.replace('-', ' ').replace('_', ' ').title()
            
            return f"{vendor_nice} {model_nice}"
    
    return current_name


def enrich_models():
    """Enrich all models with UX data."""
    print("🔧 ENRICHING MODELS WITH UX DATA")
    print("=" * 80)
    
    # Load registry
    registry_path = Path("models/kie_models_final_truth.json")
    with open(registry_path, 'r') as f:
        data = json.load(f)
    
    models = data.get('models', [])
    total = len(models)
    
    print(f"\n📦 Loaded {total} models from registry v{data.get('version')}")
    
    # Stats
    categories_normalized = 0
    display_names_improved = 0
    descriptions_added = 0
    use_cases_added = 0
    examples_added = 0
    tags_added = 0
    
    for model in models:
        model_id = model.get('model_id', '')
        
        # 1. Normalize category
        old_cat = model.get('category', '')
        new_cat = normalize_category(old_cat)
        if old_cat != new_cat:
            model['category'] = new_cat
            categories_normalized += 1
        
        # 2. Improve display_name
        old_name = model.get('display_name', model_id)
        new_name = improve_display_name(model_id, old_name)
        
        # Update if new name is better (not technical)
        is_technical_old = '/' in old_name or (old_name and old_name[0].islower())
        is_technical_new = '/' in new_name or (new_name and new_name[0].islower())
        
        if old_name != new_name and (is_technical_old or not is_technical_new):
            model['display_name'] = new_name
            display_names_improved += 1
        
        # 3. Add UX data
        ux_data = get_ux_data(new_cat)
        
        if not model.get('description'):
            model['description'] = ux_data['description']
            descriptions_added += 1
        
        if not model.get('use_case'):
            model['use_case'] = ux_data['use_case']
            use_cases_added += 1
        
        if not model.get('example'):
            model['example'] = ux_data['example']
            examples_added += 1
        
        if not model.get('tags'):
            model['tags'] = ux_data['tags']
            tags_added += 1
    
    # Save enriched registry
    data['models'] = models
    
    # Update version
    old_version = data.get('version', '6.2.0')
    new_version = "6.3.0"  # UX enrichment version
    data['version'] = new_version
    data['enrichment'] = {
        "categories_normalized": categories_normalized,
        "display_names_improved": display_names_improved,
        "descriptions_added": descriptions_added,
        "use_cases_added": use_cases_added,
        "examples_added": examples_added,
        "tags_added": tags_added
    }
    
    with open(registry_path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ ENRICHMENT COMPLETE:")
    print(f"   Categories normalized: {categories_normalized}")
    print(f"   Display names improved: {display_names_improved}")
    print(f"   Descriptions added: {descriptions_added}")
    print(f"   Use-cases added: {use_cases_added}")
    print(f"   Examples added: {examples_added}")
    print(f"   Tags added: {tags_added}")
    print(f"\n💾 Saved to: {registry_path}")
    print(f"   Version: {old_version} → {new_version}")
    print("=" * 80)


if __name__ == "__main__":
    enrich_models()
