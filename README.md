# Kie.ai Telegram Bot - Production Ready

AI генератор для изображений, видео и аудио через Telegram с монетизацией.

**📚 Документация:**
- [🚀 Quick Start для разработчиков](./QUICK_START_DEV.md)
- [🤝 Contributing Guidelines](./CONTRIBUTING.md)
- [🌐 Deployment на Render](./DEPLOYMENT.md)

**📊 Статус:** Production Ready | 72 модели | PostgreSQL + SQLite

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

## ✅ Production Safety

### 🔐 Pricing Protection (P0)

- ✅ **72 модели** в SOURCE_OF_TRUTH
- ✅ **Pricing:** точные цены из Kie.ai
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
