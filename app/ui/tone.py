"""Single source of truth for AI Studio tone of voice and copy primitives.

VOICE: Calm premium, marketer-first, no tech slang.
AUDIENCE: Marketers, SMM managers, content creators.
STYLE: Professional but friendly, clear CTAs, no walls of text.

RULES:
- Title Case for buttons and section headers
- sentence case for body text and hints
- Max 2 emoji per message, 1 per line
- Messages: 1-2 paragraphs + up to 4 bullets max
- No mention of "kie.ai" or technical provider details
"""
from typing import List, Optional


# ============================================================================
# STANDARD CTA LABELS (use these exact strings everywhere)
# ============================================================================

CTA_START = "🚀 Запустить"
CTA_EXAMPLE = "✨ Пример"
CTA_PRESETS = "🧩 Пресеты"
CTA_FREE = "🔥 Бесплатные"
CTA_POPULAR = "⭐ Популярное"
CTA_FORMATS = "🎬 Форматы"
CTA_SEARCH = "🔍 Поиск"
CTA_REFERRAL = "🤝 Партнёрка"
CTA_BALANCE = "💳 Баланс"
CTA_SUPPORT = "🆘 Поддержка"
CTA_BACK = "◀️ Назад"
CTA_HOME = "🏠 Меню"
CTA_RETRY = "🔁 Повторить"
CTA_RECOMMENDED = "🎯 Рекомендованные модели"
CTA_HOW_IT_WORKS = "❓ Как это работает"
CTA_MINI_COURSE = "🧠 Мини-обучение"


# ============================================================================
# MICROCOPY HELPERS
# ============================================================================

def header(section: str) -> str:
    """Format section header (Title Case, 1 emoji max)."""
    return f"**{section}**"


def hint(text: str) -> str:
    """Format hint text (subtle, italics)."""
    return f"💡 _{text}_"


def bullets(items: List[str], emoji: str = "•") -> str:
    """Format bullet list (max 4 items recommended)."""
    if len(items) > 4:
        items = items[:4]
    return "\n".join(f"{emoji} {item}" for item in items)


def price_line(price_rub: float, is_free: bool = False) -> str:
    """Format price display line."""
    if is_free:
        return "🔥 **Бесплатно**"
    
    if price_rub == 0:
        return "✨ **0 ₽**"
    
    return f"💳 **{price_rub:.2f} ₽**"


def input_example(kind: str, example: str) -> str:
    """Format input example hint."""
    labels = {
        "prompt": "Пример запроса",
        "text": "Пример текста",
        "style": "Пример стиля",
        "negative": "Что НЕ включать",
        "brand": "Пример бренда",
        "colors": "Пример палитры",
        "voice": "Пример голоса",
        "image": "Какое фото лучше",
        "video": "Какое видео подойдёт",
        "audio": "Какой аудио файл",
    }
    
    label = labels.get(kind, "Пример")
    return f"💡 _{label}: {example}_"


# ============================================================================
# STANDARD MESSAGES (reusable across screens)
# ============================================================================

WELCOME_MESSAGE = """👋 **AI Studio** — твой инструмент для контента

Создавай изображения, видео, текст и аудио за секунды. Без регистрации, без подписок, без сложностей.

• Генерация картинок и видео
• Озвучка и голосовые клоны
• Улучшение качества (апскейл, удаление фона)
• Скрипты для Reels/TikTok/Stories"""


FIRST_TIME_HINT = """💡 _Новичок? Начни с бесплатных моделей или попробуй готовые пресеты._"""


HOW_IT_WORKS_MESSAGE = """❓ **Как это работает**

**Шаг 1:** Выбери формат
Текст→Изображение, Видео, Аудио и т.д.

**Шаг 2:** Выбери модель
Каждая модель — это отдельный AI-инструмент с уникальным стилем.

**Шаг 3:** Опиши что нужно
Заполни параметры (текст, изображение, стиль) — готово!

**С чего начать:**
• Попробуй бесплатные модели (без трат)
• Посмотри рекомендованные (популярные у маркетологов)
• Используй пресеты (готовые сценарии)"""


MINI_COURSE_MESSAGE = """🧠 **Мини-обучение: промпты для рекламы**

**5 правил хорошего промпта:**
1. **Цель** — что создаём (пост, обложка, видео)
2. **Аудитория** — для кого (ЦА, возраст, интересы)
3. **Оффер** — что предлагаем (акция, продукт)
4. **Стиль** — как должно выглядеть (минимализм, яркие цвета)
5. **CTA** — призыв к действию (купи, подпишись, читай)

**Примеры:**

✅ **Хороший промпт (реклама кофе):**
"Рекламный пост для Instagram: кофе для занятых предпринимателей 25-35 лет. Акция 2+1 до конца недели. Стиль — минимализм, тёплые тона, утренний свет. CTA: Закажи сейчас."

✅ **Хороший промпт (скрипт Reels):**
"Сценарий Reels 15 сек: запуск нового курса по SMM для новичков. Интро с проблемой (нет подписчиков), решение (наш курс за 7 дней), финал с CTA (ссылка в шапке). Формат: говорящая голова + текст."

💡 _Чем точнее промпт — тем лучше результат!_"""


INSUFFICIENT_BALANCE_MESSAGE = """⚠️ **Недостаточно средств**

Для запуска этой модели нужно {amount:.2f} ₽.
На балансе: {current:.2f} ₽.

**Что делать:**
• Пополни баланс ({CTA_BALANCE})
• Выбери бесплатную модель ({CTA_FREE})
• Пригласи друга и получи бонус ({CTA_REFERRAL})"""


GENERATION_SUCCESS_MESSAGE = """✅ **Готово!**

{result_description}

**Что дальше:**
• {CTA_RETRY} — запустить с теми же настройками
• {CTA_HOME} — вернуться в меню
• {CTA_REFERRAL} — получить бонусы за друзей"""


GENERATION_FAILED_MESSAGE = """❌ **Не получилось**

Причина: {error_message}

**Попробуй:**
• {CTA_RETRY} — повторить с другими настройками
• {CTA_SUPPORT} — написать в поддержку
• {CTA_FREE} — попробовать бесплатную модель"""


# ============================================================================
# FORMAT DISPLAY NAMES (consistent across all screens)
# ============================================================================

FORMAT_NAMES = {
    "text-to-image": "Текст → Изображение",
    "image-to-image": "Изображение → Изображение",
    "image-to-video": "Изображение → Видео",
    "text-to-video": "Текст → Видео",
    "text-to-audio": "Текст → Аудио",
    "audio-to-audio": "Аудио → Аудио",
    "audio-to-text": "Аудио → Текст",
    "image-upscale": "Улучшение качества",
    "background-remove": "Удаление фона",
    "video-editing": "Редактирование видео",
    "audio-editing": "Редактирование аудио",
}


def format_display_name(format_id: str) -> str:
    """Get consistent display name for format."""
    return FORMAT_NAMES.get(format_id, format_id)


# ============================================================================
# VALIDATION HELPERS
# ============================================================================

def validate_message_length(text: str, max_paragraphs: int = 2, max_bullets: int = 4) -> bool:
    """Validate message follows tone guidelines."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    bullets = [line for line in text.split("\n") if line.strip().startswith(("•", "-", "✓"))]
    
    if len(paragraphs) > max_paragraphs:
        return False
    
    if len(bullets) > max_bullets:
        return False
    
    return True


def count_emoji(text: str) -> int:
    """Count emoji in text (basic check)."""
    import re
    # Simple emoji pattern (not perfect but catches most)
    emoji_pattern = re.compile(
        "["
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F700-\U0001F77F"  # alchemical
        "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
        "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027B0"  # Dingbats
        "]+",
        flags=re.UNICODE
    )
    return len(emoji_pattern.findall(text))
