# 🚀 QUICK START GUIDE

**Telegram Bot для Kie.ai - Полное руководство по запуску**

---

## 📋 Предварительные требования

- Python 3.10+
- PostgreSQL (опционально, можно использовать SQLite)
- Telegram Bot Token
- Kie.ai API Key

---

## ⚡ Быстрый старт (5 минут)

### 1. Клонировать репозиторий

```bash
git clone https://github.com/ferixdi-png/5656.git
cd 5656
```

### 2. Создать виртуальное окружение

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Настроить переменные окружения

```bash
cp .env.example .env
```

Заполнить `.env` файл:

```env
# ОБЯЗАТЕЛЬНО
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
KIE_API_KEY=your_kie_api_key_here

# ОПЦИОНАЛЬНО (есть дефолты)
DATABASE_URL=sqlite:///./bot.db
ADMIN_IDS=123456789
PRICING_MARKUP=2.0
```

### 5. Инициализировать базу данных

```bash
# Если используете PostgreSQL:
alembic upgrade head

# Если используете SQLite - БД создастся автоматически
```

### 6. Запустить бота

```bash
python main_render.py
```

✅ **Готово!** Бот запущен и работает!

---

## 🔑 Где взять API ключи

### Telegram Bot Token

1. Открыть [@BotFather](https://t.me/BotFather) в Telegram
2. Отправить `/newbot`
3. Следовать инструкциям
4. Скопировать токен

### Kie.ai API Key

1. Зарегистрироваться на [kie.ai](https://kie.ai)
2. Перейти в настройки аккаунта
3. Найти раздел API Keys
4. Создать новый ключ
5. Скопировать API Key

---

## 📊 SOURCE_OF_TRUTH (Готово!)

**✅ Все 72 модели уже спарсены и готовы к работе!**

Файл `models/KIE_SOURCE_OF_TRUTH.json` содержит:
- 72 модели (100% coverage)
- 7 категорий (image, video, audio, enhance, avatar, music, other)
- 4 FREE модели (0 RUB)
- Все цены в рублях
- Полные схемы параметров

**НЕ НУЖНО** запускать парсер повторно!

---

## 🎯 Основные компоненты

### 1. SOURCE_OF_TRUTH

**Файл:** `models/KIE_SOURCE_OF_TRUTH.json`

Единственный источник истины о моделях:
- `model_id` - идентификатор
- `provider` - провайдер (Bytedance, Qwen, etc)
- `category` - категория
- `display_name` - название для UI
- `pricing` - цены (rub_per_gen, usd_per_gen)
- `input_schema` - схема параметров
- `endpoint` - API endpoint

### 2. Builder

**Файл:** `app/kie/builder.py`

Строит payload для API:
```python
from app.kie.builder import build_payload

payload = build_payload(
    model_id="seedream",
    user_inputs={"text": "A beautiful sunset"}
)
```

### 3. Pricing

**Файл:** `app/payments/pricing.py`

Формула ценообразования:
```python
# user_price_rub = usd_per_gen × 78.0 × 2.0
USD_TO_RUB = 78.0
MARKUP_MULTIPLIER = 2.0
```

### 4. UI

**Файлы:**
- `app/ui/marketing_menu.py` - построение меню
- `bot/handlers/marketing.py` - обработчики
- `bot/handlers/flow.py` - flow генерации

### 5. API Client

**Файл:** `app/kie/client_v4.py`

С автоматическим retry:
- 3 попытки при ошибках сети
- Exponential backoff (2-10 сек)
- Логирование всех ошибок

---

## 🧪 Тестирование

### Smoke test (FREE модели, 0 кредитов)

```bash
python scripts/smoke_test_free.py
```

Результат:
```
✅ z-image: PASS
✅ qwen/text-to-image: PASS
✅ qwen/image-to-image: PASS
✅ qwen/image-edit: PASS

Cost: 0 RUB
```

### Dry-run test (все 72 модели, 0 кредитов)

```bash
python scripts/dry_run_all_models.py
```

---

## 📁 Структура проекта

```
5656/
├── models/
│   └── KIE_SOURCE_OF_TRUTH.json  # ⭐ Главный файл
├── app/
│   ├── kie/
│   │   ├── builder.py            # Построение payload
│   │   ├── client_v4.py          # API client с retry
│   │   ├── generator.py          # End-to-end генерация
│   │   └── validator.py          # Валидация
│   ├── ui/
│   │   └── marketing_menu.py     # UI меню
│   └── payments/
│       └── pricing.py            # Ценообразование
├── bot/
│   └── handlers/
│       ├── marketing.py          # UI handlers
│       └── flow.py               # Generation flow
├── scripts/
│   ├── master_kie_parser.py      # Парсер (уже выполнен)
│   ├── smoke_test_free.py        # Smoke тесты
│   └── dry_run_all_models.py     # Dry-run тесты
├── .env.example                  # Пример конфигурации
├── requirements.txt              # Python зависимости
└── main_render.py               # Точка входа
```

---

## ⚙️ Конфигурация

### Переменные окружения (.env)

#### Обязательные

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
KIE_API_KEY=your_kie_api_key_here
```

#### База данных

```env
# SQLite (дефолт, для разработки)
DATABASE_URL=sqlite:///./bot.db

# PostgreSQL (для production)
DATABASE_URL=postgresql://user:password@localhost:5432/botdb
```

#### Админы

```env
# Один админ
ADMIN_ID=123456789

# Несколько админов (через запятую)
ADMIN_IDS=123456789,987654321
```

#### Pricing

```env
# Курс USD → RUB (дефолт 78.0)
USD_TO_RUB=78.0

# Наценка (дефолт 2.0 = цена × 2)
PRICING_MARKUP=2.0
```

#### Режимы работы

```env
# Тестовый режим (stub API, без реальных запросов)
TEST_MODE=false
KIE_STUB=false

# Режим бота
BOT_MODE=polling  # или webhook
```

---

## 🚀 Deployment на Render

### 1. Создать Web Service

1. Зайти на [render.com](https://render.com)
2. New → Web Service
3. Connect GitHub repository

### 2. Настроить Build

```yaml
# Build Command
pip install -r requirements.txt

# Start Command
python main_render.py
```

### 3. Добавить Environment Variables

В Render Dashboard → Environment:
```
TELEGRAM_BOT_TOKEN = ...
KIE_API_KEY = ...
DATABASE_URL = (автоматически для Postgres)
ADMIN_IDS = ...
```

### 4. Deploy

Render автоматически задеплоит при push в main.

---

## 🔧 Troubleshooting

### Проблема: Бот не запускается

**Решение:**
1. Проверить `.env` файл создан
2. Проверить `TELEGRAM_BOT_TOKEN` и `KIE_API_KEY` заполнены
3. Проверить логи: `tail -f logs/bot.log`

### Проблема: "Model not found"

**Решение:**
1. Проверить `models/KIE_SOURCE_OF_TRUTH.json` существует
2. Проверить model_id корректен
3. Запустить: `python -c "from app.kie.builder import load_source_of_truth; print(len(load_source_of_truth()['models']))"`

### Проблема: API errors

**Решение:**
1. Проверить `KIE_API_KEY` валиден
2. Проверить баланс на Kie.ai
3. Проверить логи API client
4. Retry автоматически срабатывает (3 попытки)

### Проблема: Database errors

**Решение:**
```bash
# Если PostgreSQL
alembic downgrade base
alembic upgrade head

# Если SQLite
rm bot.db
# Запустить бота заново - БД создастся
```

---

## 📚 Дополнительная документация

- **Полный отчет о системе:** `SYSTEM_STATUS_REPORT.md`
- **Cycle отчеты:** `docs/CYCLE_*.md`
- **Deployment:** `DEPLOYMENT.md`
- **Render setup:** `RENDER_DEPLOY.md`

---

## ✅ Checklist перед запуском

- [ ] Python 3.10+ установлен
- [ ] Виртуальное окружение создано
- [ ] `requirements.txt` установлены
- [ ] `.env` файл создан
- [ ] `TELEGRAM_BOT_TOKEN` заполнен
- [ ] `KIE_API_KEY` заполнен
- [ ] `models/KIE_SOURCE_OF_TRUTH.json` существует (должен быть!)
- [ ] База данных настроена (SQLite автоматически)

---

## 🎉 Готово!

Запустить бота:
```bash
python main_render.py
```

Проверить работу:
1. Открыть бота в Telegram
2. Отправить `/start`
3. Выбрать категорию
4. Выбрать модель
5. Сгенерировать контент

**Всё работает! 🚀**

---

## 💡 Полезные команды

```bash
# Проверить SOURCE_OF_TRUTH
python -c "import json; print(json.load(open('models/KIE_SOURCE_OF_TRUTH.json'))['version'])"

# Запустить smoke tests
python scripts/smoke_test_free.py

# Проверить все модели (dry-run)
python scripts/dry_run_all_models.py

# Обновить dependencies
pip install -r requirements.txt --upgrade

# Проверить синтаксис
python -m compileall .

# Запустить в debug режиме
DEBUG=1 python main_render.py
```

---

**Контакты:**
- GitHub: [@ferixdi-png/5656](https://github.com/ferixdi-png/5656)
- Отчет: `SYSTEM_STATUS_REPORT.md`

---

**Статус проекта:** 🟢 100% READY TO USE
