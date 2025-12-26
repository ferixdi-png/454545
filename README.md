# Kie.ai Telegram Bot - Production Ready (v23 stable)

AI генератор для изображений, видео и аудио через Telegram с монетизацией.

**📚 Документация:**
- [🚀 Quick Start для разработчиков](./QUICK_START_DEV.md)
- [🤝 Contributing Guidelines](./CONTRIBUTING.md)
- [🌐 Deployment на Render](./DEPLOYMENT.md)
- [✅ Production Ready Report v23](./PRODUCTION_READY_v23.md) ⭐ NEW
- [📝 Changelog v23](./CHANGELOG_v23.md) ⭐ NEW

**📊 Статус:** ✅ Production Ready v23 | 42 моделей | Docker 218MB | Webhook stable

**🎯 v23 Highlights:**
- ✅ Webhook retry + health check (`/healthz`)
- ✅ Docker optimized (218 MB, 2-3x faster deploy)
- ✅ Type-safe config (@dataclass)
- ✅ 57 tests passing (95/100 production score)

**🆕 System Improvements (Latest):**
- ✅ **Cleanup Tasks**: Auto-cleanup старых записей (7 дней - processed_updates, 30 дней - events)
- ✅ **Metrics API**: HTTP endpoint `/metrics` для мониторинга
- ✅ **Admin Dashboard**: Метрики системы в реальном времени (📈 в /admin)
- ✅ **Popular Models**: Быстрый доступ к топ-моделям (⭐ Популярные)
- ✅ **Request ID Search**: Поиск генераций по request_id в админке
- ✅ **Auto Model Sync**: Синхронизация с Kie API каждые 24ч

---

## 🚀 Quick Start: Deploy to Render

**[📖 Полная инструкция по деплою →](./DEPLOYMENT.md)**

### За 3 минуты:

1. **PostgreSQL база:** New → PostgreSQL → Free tier
2. **Web Service:** New → Web Service → Python 3
3. **ENV переменные:**
   ```bash
   TELEGRAM_BOT_TOKEN=7...     # от @BotFather
   KIE_API_KEY=kie_...         # от Kie.ai
   DATABASE_URL=postgresql://  # Internal URL
   ADMIN_ID=123456789          # ваш Telegram ID
   BOT_MODE=webhook            # ОБЯЗАТЕЛЬНО для Render
   WEBHOOK_BASE_URL=https://your-app.onrender.com
   ```
4. **Deploy!** → Бот работает

**Build Command:**
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
python main_render.py
```

---

## 🚀 Render Deployment Checklist

### Prerequisites
- [ ] GitHub repository with code
- [ ] Render.com account (free tier OK)
- [ ] Telegram bot token from @BotFather
- [ ] Kie.ai API key

### Step 1: PostgreSQL Database
1. Go to Render Dashboard → New → PostgreSQL
2. Name: `mybot-db` (or any name)
3. Plan: **Free** tier
4. Region: Choose closest to you
5. Click **Create Database**
6. Copy **Internal Database URL** (starts with `postgresql://`)

### Step 2: Web Service
1. Go to Render Dashboard → New → Web Service
2. Connect your GitHub repository
3. Name: `mybot-prod` (or any name)
4. Runtime: **Python 3**
5. Region: **Same as database**
6. Branch: `main`
7. Build Command: `pip install -r requirements.txt`
8. Start Command: `python main_render.py`
9. Plan: **Free** tier (or paid for better reliability)

### Step 3: Environment Variables

**Required (CRITICAL - bot won't start without these):**

| Variable | Value | Where to get |
|----------|-------|--------------|
| `TELEGRAM_BOT_TOKEN` | `7123456789:AAH...` | @BotFather → /newbot |
| `KIE_API_KEY` | `kie_...` | https://kie.ai/api-keys |
| `DATABASE_URL` | `postgresql://...` | Render PostgreSQL → Internal URL |
| `ADMIN_ID` | `123456789` | Your Telegram user ID (@userinfobot) |
| `BOT_MODE` | `webhook` | **Must be webhook for Render** |
| `WEBHOOK_BASE_URL` | `https://mybot-prod.onrender.com` | Your Render service URL |

**Optional (recommended for production):**

| Variable | Default | Purpose |
|----------|---------|---------|
| `TELEGRAM_WEBHOOK_SECRET_TOKEN` | auto-generated | Webhook security (recommended) |
| `TELEGRAM_WEBHOOK_PATH` | `/webhook` | Webhook endpoint path |
| `PORT` | `10000` | Render sets this automatically |
| `LOG_LEVEL` | `INFO` | `DEBUG` for troubleshooting |
| `INSTANCE_NAME` | auto | For multi-instance deployments |
| `PRICING_MARKUP` | `2.0` | Price multiplier (profit margin) |

**Payment Settings (for topup functionality):**

| Variable | Example | Purpose |
|----------|---------|---------|
| `PAYMENT_BANK` | `Тинькофф` | Bank name for payment instructions |
| `PAYMENT_CARD` | `5536 9137 **** ****` | Masked card number |
| `PAYMENT_CARD_HOLDER` | `IVAN IVANOV` | Cardholder name |
| `PAYMENT_PHONE` | `+7 900 123-45-67` | Phone for SBP payments |

### Step 4: Health Checks

Render automatically checks these endpoints:

- **Liveness probe:** `GET /healthz` → Returns 200 if service is alive
- **Readiness probe:** `GET /readyz` → Returns 200 if bot is ready (DB initialized, webhook registered)

**What Render checks:**
- Every 30 seconds: `GET /healthz`
- If 3 consecutive failures → restarts service
- During deploy: waits for `/readyz` to return 200

**Troubleshooting:**
```bash
# Check health manually
curl https://mybot-prod.onrender.com/healthz
# Should return: {"status":"ok"}

curl https://mybot-prod.onrender.com/readyz
# Should return: {"mode":"active","ready":true,...}
```

### Step 5: Webhook Registration

After deploy, verify webhook is registered:

1. Open Render Logs
2. Look for: `✅ Webhook registered successfully: https://...`
3. If you see: `⚠️ WEBHOOK_BASE_URL NOT SET` → add `WEBHOOK_BASE_URL` env var

**Check webhook status:**
```bash
curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo
```

Should show:
```json
{
  "ok": true,
  "result": {
    "url": "https://mybot-prod.onrender.com/webhook",
    "has_custom_certificate": false,
    "pending_update_count": 0,
    "max_connections": 40
  }
}
```

### Step 6: Verify Deployment

**Check logs:**
```
✅ Startup selfcheck OK: 42 models locked
✅ Database initialized with schema
✅ Webhook server started on 0.0.0.0:10000
✅ Webhook registered successfully
✅ Bot is READY (webhook mode)
```

**Test bot:**
1. Open Telegram
2. Find your bot
3. Send `/start`
4. Should receive welcome message

**Common issues:**

| Issue | Solution |
|-------|----------|
| "WEBHOOK_BASE_URL not set" | Add `WEBHOOK_BASE_URL` env var with your Render URL |
| "Lock not acquired" | Old instance still running → wait 60s or restart service |
| "Database connection failed" | Check `DATABASE_URL` is correct (Internal URL) |
| "/healthz returns 503" | Service still starting → wait 1-2 minutes |
| "/readyz returns 503" | Database not initialized → check logs for errors |

### Step 7: Post-Deployment

**Monitor:**
- Render Dashboard → Logs (real-time)
- Health checks: Green = healthy
- Metrics: CPU/Memory usage

**Update code:**
1. Push to GitHub `main` branch
2. Render auto-deploys (if enabled)
3. Watch logs for: `✅ Bot is READY`

**Scale (paid plans):**
- Horizontal: Run multiple instances (requires `INSTANCE_NAME` uniqueness)
- Vertical: Upgrade Render plan for more RAM/CPU

---

## 🔒 Security Best Practices

### Webhook Security
- ✅ Set `TELEGRAM_WEBHOOK_SECRET_TOKEN` (auto-generated if not provided)
- ✅ Webhook validates `X-Telegram-Bot-Api-Secret-Token` header
- ✅ Only `/webhook` endpoint accepts Telegram updates
- ✅ All other endpoints (`/healthz`, `/readyz`) public for health checks

### Secrets Management
- ✅ Never commit env vars to git
- ✅ Use Render environment variables UI
- ✅ Rotate `KIE_API_KEY` and `TELEGRAM_BOT_TOKEN` periodically
- ✅ User IDs masked in logs (last 4 digits only)

### Rate Limiting
- ✅ Per-user rate limit: 20 actions/min (burst 30)
- ✅ Callback deduplication: 2s window
- ✅ Admins exempt from rate limits

### Database
- ✅ PostgreSQL advisory locks prevent duplicate instances
- ✅ Database credentials in `DATABASE_URL` only (not hardcoded)
- ✅ Migrations applied automatically on startup

---

## ✅ Production Safety

### 🔐 Pricing Protection (P0)

- ✅ **42 модели** в SOURCE_OF_TRUTH (locked to allowlist)
- ✅ **Pricing:** точные цены из Kie.ai с fallback CBR API
- ✅ **Формула:** `USER_PRICE_RUB = KIE_PRICE_USD × FX_RATE × 2.0`
- ✅ **FX auto-update** из ЦБР (78.43 RUB/USD актуальный)
- ⚠️ **Input schemas:** требуют обновления (см. QUICK_START_DEV.md)

### 🔒 Singleton Lock

- ✅ PostgreSQL advisory lock
- ✅ TTL = 60 секунд
- ✅ Heartbeat каждые 20 секунд
- ✅ Автоочистка stale locks
- ✅ Graceful shutdown (SIGTERM/SIGINT)

### 🌐 Multi-Tenant

- ✅ Один репозиторий → много Render services
- ✅ ENV-based конфигурация
- ✅ `ADMIN_ID` CSV поддержка: `111,222,333`
- ✅ `INSTANCE_NAME` для мониторинга

---

## 📋 Environment Variables Reference

| Переменная | Обязательно | Описание | Пример |
|------------|-------------|----------|--------|
| `TELEGRAM_BOT_TOKEN` | ✅ | Токен от @BotFather | `7123456789:AAHd...` |
| `KIE_API_KEY` | ✅ | API ключ Kie.ai | `kie_...` |
| `DATABASE_URL` | ✅ | PostgreSQL URL | `postgresql://user:pass@host/db` |
| `ADMIN_ID` | ✅ | Telegram ID админов (CSV) | `123456789` или `111,222,333` |
| `BOT_MODE` | ✅ | `webhook` или `polling` | `webhook` (для Render) |
| `INSTANCE_NAME` | ❌ | Имя инстанса | `prod-bot-1` |
| `LOG_LEVEL` | ❌ | `DEBUG`/`INFO`/`WARNING` | `INFO` |
| `RENDER_EXTERNAL_URL` | ❌ | Автоматически (Render) | - |
| **`ADMIN_IDS`** | ❌ | **Альтернатива ADMIN_ID (CSV)** | `111,222,333` |
| **`CURRENCY`** | ❌ | **Валюта отображения** | `RUB` (default) |
| **`KIE_STUB`** | ❌ | **Stub режим для тестов** | `true` или `false` |
| **`PAYMENT_BANK`** | ❌ | **Банк для оплаты** | `Тинькофф` |
| **`PAYMENT_CARD`** | ❌ | **Номер карты** | `5536 9137 XXXX YYYY` |
| **`PAYMENT_CARD_HOLDER`** | ❌ | **Владелец карты** | `IVAN IVANOV` |
| **`PAYMENT_PHONE`** | ❌ | **Телефон для оплаты** | `+7 900 123-45-67` |
| **`PRICING_MARKUP`** | ❌ | **Множитель цены (default: 2.0)** | `2.0` |
| **`STORAGE_MODE`** | ❌ | **Режим хранения** | `local` или `s3` |
| **`SUPPORT_TELEGRAM`** | ❌ | **Telegram поддержки** | `@support_bot` |
| **`SUPPORT_TEXT`** | ❌ | **Текст поддержки** | `Напишите нам` |
| **`TEST_DATABASE_URL`** | ❌ | **БД для тестов** | `postgresql://...` |
| **`TEST_MODE`** | ❌ | **Тестовый режим** | `true` или `false` |
| **`WELCOME_BALANCE_RUB`** | ❌ | **Стартовый баланс новых пользователей** | `100` (₽) |

### Pricing Formula (MASTER PROMPT compliance):
```python
price_rub = price_usd * 78.0 * PRICING_MARKUP
```
- **USD_TO_RUB rate:** 78.0 ₽/USD (фиксированный)
- **MARKUP:** 2.0 (можно переопределить через `PRICING_MARKUP`)
- **Формула:** строго соблюдается во всех модулях

**⚙️ FREE Tier Auto-Derivation:**

FREE tier = **TOP-5 cheapest** моделей, вычисляется автоматически из `models/pricing_source_truth.txt`

- **Правило:** Не редактируйте is_free флаги руками. Измените pricing_source_truth.txt → FREE tier пересчитается автоматически
- **Синхронизация:** `python scripts/sync_free_tier_from_truth.py`
- **Алгоритм:** sort by (price_rub ASC, model_id ASC) - детерминистический tie-breaking
- **Override:** ENV `FREE_TIER_MODEL_IDS` (только для экстренных случаев, должен содержать ровно 5 моделей)

```bash
# Проверить FREE tier
python -m app.utils.startup_validation

# Синхронизировать после изменения pricing_source_truth.txt
python scripts/sync_free_tier_from_truth.py
```

---

## 🧪 Testing

```bash
# Все тесты
python -m pytest tests/ -v

# Pricing safety
python scripts/kie_truth_audit.py

# Registry enrichment
python scripts/enrich_registry.py
```

**59 тестов проходят** ✅

---

## 📦 Возможности

- ✅ **AI генерация:** изображения (Flux, DALL-E), видео (Kling, Luma), аудио
- ✅ **Платежи:** предоплата через Telegram Stars, автоматические возвраты
- ✅ **Pricing safety:** NO fallback prices, только проверенные цены
- ✅ **Singleton lock:** предотвращение дубликатов при blue-green deployment
- ✅ **Graceful shutdown:** корректная остановка при deployment
- ✅ **Multi-tenant:** несколько ботов из одного кода
- `PORT=10000` (healthcheck listener)
- `DRY_RUN=0`

### Конфигурация (опционально)

Создайте `config.json` на основе `config.json.example`:

```json
{
  "base_url": "https://api.kie.ai/api/v1",
  "market_url": "https://kie.ai/ru/market",
  "max_models": 50,
  "request_delay": 0.3,
  "timeout": 15
}
```

Или используйте переменные окружения:
- `KIE_BASE_URL` - базовый URL API
- `KIE_MARKET_URL` - URL маркета
- `MAX_MODELS` - максимальное количество моделей
- `REQUEST_DELAY` - задержка между запросами
- `REQUEST_TIMEOUT` - таймаут запросов

## 🎯 Использование

### ⚠️ Важно: Одноразовый парсинг

Парсинг выполняется **один раз локально**. Результаты сохраняются в `kie_full_api.json` и используются на Render без повторного парсинга.

```bash
# Запуск парсинга (один раз)
python kie_api_scraper.py

# Принудительный перезапуск (если данные уже есть)
python kie_api_scraper.py --force
```

Скрипт автоматически:
1. Сканирует страницу маркета
2. Парсит документацию каждой модели (параллельно)
3. Валидирует структуру всех моделей
4. Сохраняет результаты в `kie_full_api.json`
5. Сохраняет статистику в `kie_scraper_stats.json`

**После парсинга:**
- Закоммитьте `kie_full_api.json` в Git
- На Render парсинг **НЕ запускается** автоматически
- Используются уже спарсенные данные

### Дополнительные опции (как библиотека):

```python
from kie_api_scraper import KieApiScraper

# Настройка количества потоков и кэширования
scraper = KieApiScraper(max_workers=10, enable_cache=True)

# Запуск парсинга
models = scraper.run_full_scrape()

# Фильтрация моделей
video_models = scraper.filter_models(category='video', has_endpoint=True)

# Экспорт по категориям
scraper.export_models_by_category('exports')
```

### Переменные окружения:

- `EXPORT_BY_CATEGORY=true` - включить экспорт по категориям

## 📋 Структура данных

Каждая модель содержит:
- `name` - название модели
- `endpoint` - API endpoint (проверен и валидирован)
- `method` - HTTP метод (обычно POST)
- `base_url` - базовый URL API
- `params` - параметры модели (duration, width, height, steps, temperature, max_length)
- `input_schema` - схема входных данных с обязательными полями
- `example` - пример использования (JSON строка)
- `example_request` - структурированный пример запроса (объект)
- `price` - цена (если доступна)
- `category` - категория модели (video, image, text, audio, other)

## ✅ Валидация

Скрипт автоматически проверяет:
- Наличие всех обязательных полей
- Правильность типов данных
- Соответствие base_url
- Структуру параметров

## 📁 Файлы

- `kie_api_scraper.py` - основной скрипт
- `requirements.txt` - зависимости Python
- `runtime.txt` - версия Python для Render
- `render.yaml` - конфигурация для деплоя на Render
- `.renderignore` - игнорируемые файлы
- `kie_full_api.json` - ⭐ **ГЛАВНЫЙ ФАЙЛ** - результат парсинга (создается после локального запуска)
- `kie_scraper_stats.json` - статистика и метрики (создается после запуска)
- `kie_scraper.log` - лог файл с детальной информацией
- `config.json` - конфигурация (опционально, см. config.json.example)
- `exports/` - экспорт по категориям (если включен)

**Важно:** Файл `kie_full_api.json` должен быть закоммичен в Git и использоваться на Render без повторного парсинга.

## 🔧 Требования

- Python 3.7+
- requests>=2.31.0
- beautifulsoup4>=4.12.0
- lxml>=4.9.0
- urllib3>=2.0.0

## ⚡ Производительность

- **Параллельная обработка**: до 5-10 потоков (настраивается)
- **Кэширование**: избежание повторных запросов
- **Retry механизм**: автоматические повторы при ошибках
- **Оптимизированный парсинг**: множественные стратегии поиска

## 📊 Метрики

После выполнения создается файл `kie_scraper_stats.json` с:
- Временем выполнения
- Количеством запросов (всего, кэшированных, ошибок)
- Статистикой по категориям
- Результатами валидации

## 📝 Лицензия

MIT
