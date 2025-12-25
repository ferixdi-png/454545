# 🚀 Quick Start для разработчиков

Быстрый старт для локальной разработки и тестирования.

---

## 1️⃣ Клонирование и установка

```bash
git clone https://github.com/ferixdi-png/5656.git
cd 5656
pip install -r requirements.txt
```

---

## 2️⃣ Настройка окружения

Создайте `.env` файл:

```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_from_BotFather
ADMIN_ID=your_telegram_id

# Kie.ai API
KIE_API_KEY=kie_your_api_key_from_kie_ai

# Database (для локальной разработки используется SQLite)
# DATABASE_URL не нужен - автоматически создастся bot_local.db

# Bot Mode
BOT_MODE=polling  # для локальной разработки
```

**Как получить токены:**
- TELEGRAM_BOT_TOKEN: [@BotFather](https://t.me/BotFather) → /newbot
- KIE_API_KEY: [kie.ai](https://kie.ai/) → Settings → API Keys
- ADMIN_ID: [@userinfobot](https://t.me/userinfobot) → отправьте /start

---

## 3️⃣ Запуск бота локально

```bash
# Обычный запуск
python main_render.py

# С отладкой
python main_render.py --debug
```

Бот стартует в polling режиме и работает с локальной SQLite БД.

---

## 4️⃣ Проверка работоспособности

### Автоматические проверки:

```bash
# Все проверки сразу
python scripts/check_all.py

# Или по отдельности:
python scripts/verify_project.py              # Структура проекта
python scripts/validate_source_of_truth.py    # SOURCE_OF_TRUTH валидация
python scripts/dry_run_validate_payloads.py   # Payload building
```

### Тесты:

```bash
# Быстрые unit-тесты (без API)
pytest tests/test_pricing.py -v
pytest tests/test_cheapest_models.py -v

# Полный набор (включая интеграционные)
pytest -v

# Только зелёные тесты
pytest -k "not real" -v
```

---

## 5️⃣ Структура проекта

```
5656/
├── app/                    # Основной код бота
│   ├── kie/               # Генерация через Kie.ai
│   ├── payments/          # Баланс и pricing
│   ├── database/          # PostgreSQL/SQLite
│   └── ui/                # Telegram handlers
├── bot/                   # Aiogram bot logic
├── models/                # SOURCE_OF_TRUTH
├── scripts/               # Утилиты и проверки
├── tests/                 # Pytest тесты
└── main_render.py         # Entry point
```

---

## 6️⃣ Полезные команды

### Компиляция и проверка:

```bash
python -m compileall .     # Проверка синтаксиса
pytest -q                  # Быстрый прогон тестов
python scripts/check_all.py  # Все проверки
```

### База данных:

```bash
# Локально используется SQLite: bot_local.db
# Для production PostgreSQL - см. DEPLOYMENT.md
```

### Деплой на Render:

```bash
git push origin main  # Auto-deploy при push в main
```

---

## 7️⃣ Troubleshooting

### Бот не стартует:

1. Проверьте `.env` файл - все переменные заполнены?
2. `BOT_MODE=polling` для локальной разработки
3. Проверьте логи: `python main_render.py` покажет ошибки

### API ошибки (422/500):

- Проблема: пустые `input_schema` для моделей
- Решение: пока используйте только модели с валидными схемами
- TODO: обновить схемы из актуальной документации Kie.ai

### TelegramConflictError:

- Бот запущен в двух местах одновременно
- Остановите локальную версию ИЛИ Render instance

### База данных:

- Локально: удалите `bot_local.db` для сброса
- Production: используйте alembic migrations

---

## 8️⃣ Contributing

1. Создайте feature branch: `git checkout -b feature/my-feature`
2. Сделайте изменения
3. Прогоните проверки: `python scripts/check_all.py`
4. Commit: `git commit -m "feat: my feature"`
5. Push: `git push origin feature/my-feature`
6. Создайте Pull Request

**Требования:**
- ✅ `python -m compileall .` - без ошибок
- ✅ `python scripts/check_all.py` - все проверки зелёные
- ✅ Новый код покрыт тестами

---

## 9️⃣ Архитектура

### SOURCE_OF_TRUTH

**Файл:** `models/KIE_SOURCE_OF_TRUTH.json`

Единый источник истины для всех моделей:

```json
{
  "version": "1.2.10-FINAL",
  "models": {
    "model-id": {
      "endpoint": "/api/v1/jobs/createTask",
      "input_schema": { "properties": {...} },
      "pricing": {
        "usd_per_gen": 0.1,
        "rub_per_gen": 7.8
      },
      "tags": ["image", "fast"],
      "ui_example_prompts": ["Create a cat..."]
    }
  }
}
```

### API Clients

- **V4 API:** `app/kie/client_v4.py` - новый category-based API
- **V3 API:** `app/kie/client.py` - legacy universal endpoint
- **Router:** `app/kie/router.py` - автоматический выбор V3/V4

### Pricing System

- **FX rates:** Автообновление курса USD/RUB из ЦБР
- **Markup:** 2x от стоимости Kie.ai
- **Free tier:** 5 самых дешёвых моделей для новых пользователей

---

## 🔟 Полезные ссылки

- [Deployment Guide](./DEPLOYMENT.md) - полный гайд по деплою на Render
- [Kie.ai Docs](https://docs.kie.ai/) - официальная документация API
- [Aiogram Docs](https://docs.aiogram.dev/) - Telegram Bot framework
- [Render Docs](https://render.com/docs) - платформа для деплоя

---

## 📊 Статус проекта

- ✅ 72 модели в SOURCE_OF_TRUTH
- ✅ Бот работает на Render стабильно
- ✅ PostgreSQL + SQLite support
- ✅ FX auto-update
- ✅ Free tier для новых пользователей
- ⚠️ Input schemas требуют обновления (72/72 пустые)
- ⚠️ 15 pytest failures (интеграционные тесты)

---

**Версия:** 1.2.10-FINAL  
**Дата:** 2025-12-25  
**Статус:** Production Ready (с ограничениями по схемам)
