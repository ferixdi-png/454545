"""Единый Tone of Voice и терминология для всего бота."""

# === КНОПКИ / CTA ===
BTN_START = "🚀 Начать"
BTN_GENERATE = "🚀 Запустить"
BTN_BACK = "◀️ Назад"
BTN_HOME = "🏠 Меню"
BTN_CANCEL = "❌ Отменить"
BTN_SKIP = "⏭ Пропустить"
BTN_RETRY = "🔄 Повторить"
BTN_EXAMPLES = "📋 Примеры"

# === ГЛАВНОЕ МЕНЮ ===
MENU_POPULAR = "🔥 Популярные"
MENU_FORMATS = "🧩 Форматы"
MENU_FREE = "🆓 Бесплатные (5)"
MENU_VIDEO = "🎬 Видео"
MENU_IMAGES = "🖼 Изображения"
MENU_AUDIO = "🎙 Аудио/Озвучка"
MENU_HISTORY = "📂 История"
MENU_BALANCE = "💰 Баланс"
MENU_PRICING = "💎 Тарифы"
MENU_SUPPORT = "🆘 Поддержка"

# === ФОРМАТЫ (подменю) ===
FORMAT_TEXT_TO_IMAGE = "✍️ Текст → Изображение"
FORMAT_IMAGE_TO_IMAGE = "🖼 Изображение → Изображение"
FORMAT_TEXT_TO_VIDEO = "✍️ Текст → Видео"
FORMAT_IMAGE_TO_VIDEO = "🖼 Изображение → Видео"
FORMAT_TEXT_TO_AUDIO = "✍️ Текст → Аудио (TTS/SFX)"
FORMAT_AUDIO_PROCESSING = "🎚 Обработка аудио"
FORMAT_IMAGE_UPSCALE = "⬆️ Увеличение изображений"
FORMAT_BACKGROUND_REMOVE = "🪄 Удаление фона"

# === СООБЩЕНИЯ ===
MSG_WELCOME = (
    "👋 <b>Добро пожаловать в AI Studio!</b>\n\n"
    "🚀 <b>42+ премиальных нейросетей</b> для креативных задач\n\n"
    "<b>Выберите направление:</b>\n"
    "1. Выберите формат или популярную модель 📂\n"
    "2. Укажите параметры 📝\n"
    "3. Получите результат ⚡\n\n"
    "🆓 <b>5 бесплатных</b> моделей\n\n"
    "Выберите задачу 👇"
)

MSG_MODEL_CARD_TEMPLATE = (
    "🎨 <b>{display_name}</b>\n\n"
    "{description}\n\n"
    "📂 <b>Формат:</b> {format}\n"
    "💰 <b>Цена:</b> {price}\n"
    "🔥 <b>Популярность:</b> {popularity}\n\n"
    "<b>Что нужно:</b>\n"
    "{required_inputs}\n"
)

MSG_GENERATION_START = "🚀 Запускаю генерацию..."
MSG_GENERATION_SUCCESS = "✅ <b>Готово!</b>\n\n🎨 Модель: {model_name}\n\n"
MSG_GENERATION_FAILED = (
    "❌ <b>Ошибка генерации</b>\n\n"
    "{error_message}\n\n"
    "Попробуйте:\n"
    "• Изменить параметры\n"
    "• Выбрать другую модель\n"
    "• Написать в поддержку /support"
)

MSG_INSUFFICIENT_BALANCE = (
    "⚠️ <b>Недостаточно средств</b>\n\n"
    "Требуется: {required}₽\n"
    "Баланс: {balance}₽\n\n"
    "💳 Пополните баланс для продолжения"
)

MSG_BUTTON_OUTDATED = (
    "⚠️ <b>Экран устарел</b>\n\n"
    "Открываю главное меню..."
)

MSG_FILE_ACCEPTED = "✅ <b>Файл принят!</b>\n\n📎 {field_name}"
MSG_URL_ACCEPTED = "✅ <b>Ссылка принята!</b>\n\n🔗 {field_name}"

MSG_INVALID_FILE_TYPE = (
    "❌ <b>Неверный формат</b>\n\n"
    "Ожидается: файл ИЛИ ссылка\n\n"
    "📎 Загрузите файл или отправьте http(s) URL"
)

MSG_UPLOAD_NOT_AVAILABLE = (
    "⚠️ <b>Загрузка файлов недоступна</b>\n\n"
    "Пришлите прямую ссылку на {field_name}:"
)

MSG_VALIDATION_ERROR = (
    "❌ <b>Ошибка валидации:</b>\n"
    "{error}\n\n"
    "Попробуйте снова:"
)

MSG_EMPTY_INPUT = "❌ Пустой ввод. Попробуйте снова."

# === ПОДСКАЗКИ ПО ИНПУТАМ ===
HINT_TEXT = "✍️ Опишите что хотите получить"
HINT_IMAGE_FILE = "📎 Загрузите файл из галереи или отправьте ссылку"
HINT_VIDEO_FILE = "📎 Загрузите видео или отправьте ссылку"
HINT_AUDIO_FILE = "📎 Загрузите аудио или отправьте ссылку"
HINT_NUMBER = "🔢 Введите число"
HINT_ENUM = "📋 Выберите из вариантов"

# === ЭМОДЖИ ПО ТИПАМ ИНПУТОВ ===
EMOJI_TEXT = "✍️"
EMOJI_IMAGE = "🖼"
EMOJI_VIDEO = "🎬"
EMOJI_AUDIO = "🎙"
EMOJI_NUMBER = "🔢"
EMOJI_ENUM = "📋"
EMOJI_BOOLEAN = "✅"

# === ЦЕНЫ (форматирование) ===
PRICE_FREE = "🆓 Бесплатно"
PRICE_TEMPLATE = "₽{amount}"

# === ПОПУЛЯРНОСТЬ ===
POPULARITY_HIGH = "🔥🔥🔥 Очень популярная"
POPULARITY_MEDIUM = "🔥🔥 Популярная"
POPULARITY_LOW = "🔥 Новая"
POPULARITY_UNKNOWN = "—"

# === ОШИБКИ (понятные для пользователя) ===
ERROR_MODEL_NOT_FOUND = "❌ Модель не найдена"
ERROR_INVALID_INPUT = "❌ Неверные параметры"
ERROR_TIMEOUT = "⏱ Время ожидания истекло. Попробуйте снова."
ERROR_NETWORK = "🌐 Проблема с сетью. Повторите попытку."
ERROR_UNKNOWN = "❌ Произошла ошибка. Обратитесь в поддержку."

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def format_price(price_rub: float) -> str:
    """Форматирование цены."""
    if price_rub == 0:
        return PRICE_FREE
    return PRICE_TEMPLATE.format(amount=f"{price_rub:.2f}")


def format_popularity(rank: int) -> str:
    """Форматирование популярности."""
    if rank <= 5:
        return POPULARITY_HIGH
    elif rank <= 15:
        return POPULARITY_MEDIUM
    elif rank <= 30:
        return POPULARITY_LOW
    return POPULARITY_UNKNOWN


def get_emoji_for_input_type(input_type: str) -> str:
    """Получить эмоджи для типа инпута."""
    mapping = {
        "TEXT": EMOJI_TEXT,
        "IMAGE_URL": EMOJI_IMAGE,
        "IMAGE_FILE": EMOJI_IMAGE,
        "VIDEO_URL": EMOJI_VIDEO,
        "VIDEO_FILE": EMOJI_VIDEO,
        "AUDIO_URL": EMOJI_AUDIO,
        "AUDIO_FILE": EMOJI_AUDIO,
        "NUMBER": EMOJI_NUMBER,
        "ENUM": EMOJI_ENUM,
        "BOOLEAN": EMOJI_BOOLEAN,
    }
    return mapping.get(input_type, "📝")


def get_hint_for_input_type(input_type: str) -> str:
    """Получить подсказку для типа инпута."""
    mapping = {
        "TEXT": HINT_TEXT,
        "IMAGE_URL": HINT_IMAGE_FILE,
        "IMAGE_FILE": HINT_IMAGE_FILE,
        "VIDEO_URL": HINT_VIDEO_FILE,
        "VIDEO_FILE": HINT_VIDEO_FILE,
        "AUDIO_URL": HINT_AUDIO_FILE,
        "AUDIO_FILE": HINT_AUDIO_FILE,
        "NUMBER": HINT_NUMBER,
        "ENUM": HINT_ENUM,
    }
    return mapping.get(input_type, "")
