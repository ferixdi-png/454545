# 🚀 Деплой на Render за 3 минуты

## Требования
- Аккаунт на [render.com](https://render.com)
- Telegram бот (получить токен у [@BotFather](https://t.me/botfather))
- PostgreSQL база (бесплатная на Render)
- API ключ от [Kie.ai](https://kie.ai)

---

## 📋 Шаг 1: Создать PostgreSQL базу

1. В Render Dashboard: **New → PostgreSQL**
2. Name: `kie-bot-db` (любое имя)
3. Database: `kie_bot`
4. User: `kie_user`
5. Region: выбрать ближайший к целевой аудитории
6. Plan: **Free** (для тестов) или **Starter** (для продакшена)
7. **Create Database**

✅ Скопировать **Internal Database URL** (начинается с `postgresql://`)

---

## 📋 Шаг 2: Создать Web Service

1. В Render Dashboard: **New → Web Service**
2. Подключить GitHub репозиторий
3. Name: `kie-bot-production` (любое имя)
4. Branch: `main`
5. Region: тот же, что и база
6. Runtime: **Python 3**
7. Build Command: `pip install -r requirements.txt`
8. Start Command: `python main_render.py`
9. Plan: **Free** (1 инстанс) или **Starter** (для auto-scaling)

---

## 🔐 Шаг 3: Настроить Environment Variables

В разделе **Environment** добавить:

| Переменная | Значение | Описание |
|------------|----------|----------|
| `TELEGRAM_BOT_TOKEN` | `7123456789:AAHd...` | Токен от @BotFather |
| `KIE_API_KEY` | `kie_...` | API ключ Kie.ai |
| `DATABASE_URL` | `postgresql://...` | Internal URL из Шага 1 |
| `ADMIN_ID` | `123456789` | Ваш Telegram ID (получить у @userinfobot) |
| `BOT_MODE` | `webhook` | **ОБЯЗАТЕЛЬНО** для Render |
| `INSTANCE_NAME` | `prod-bot-1` | Имя инстанса (для мониторинга) |
| `LOG_LEVEL` | `INFO` | `DEBUG` для разработки, `INFO` для продакшена |
| `RENDER_EXTERNAL_URL` | *(авто)* | Render автоматически устанавливает |

### ⚠️ КРИТИЧНО: BOT_MODE

```bash
BOT_MODE=webhook  # ✅ ПРАВИЛЬНО для Render
BOT_MODE=polling  # ❌ НЕПРАВИЛЬНО - будет конфликт
```

**Почему webhook:**
- Render использует blue-green deployment (2 инстанса одновременно)
- Polling вызовет конфликт (Telegram не даст 2 инстансам одновременно получать updates)
- Webhook работает через HTTP, совместим с балансировщиком Render

---

## 🔄 Шаг 4: Deploy

1. Нажать **Create Web Service**
2. Render автоматически:
   - Клонирует репозиторий
   - Установит зависимости
   - Запустит `main_render.py`
3. Дождаться статуса **Live** (2-3 минуты)

---

## ✅ Проверка работоспособности

### 1. Healthcheck endpoint

```bash
curl https://kie-bot-production.onrender.com/health
```

Ожидаемый ответ:
```json
{
  "status": "ok",
  "mode": "webhook",
  "lock_status": "acquired",
  "instance_name": "prod-bot-1"
}
```

### 2. Telegram бот

Отправить `/start` в Telegram:
```
👋 Привет! Я AI генератор.

💰 Баланс: 0.00 ₽
🎨 Выберите категорию:

[Изображения] [Видео] [Аудио]
```

### 3. Логи

В Render Dashboard → вашем сервисе → **Logs**:
```
✅ Singleton lock acquired by prod-bot-1
🤖 Bot polling disabled (webhook mode)
✅ Webhook set to https://kie-bot-production.onrender.com/webhook/...
📡 Bot is running in webhook mode
```

---

## 🔧 Multi-tenant: деплой нескольких ботов

Для запуска нескольких независимых ботов из одного репозитория:

### Вариант A: Разные Render Services

1. Создать еще один Web Service: `kie-bot-europe`
2. Использовать те же файлы (тот же GitHub repo)
3. Указать **разные ENV**:

**Service 1 (RU):**
```bash
TELEGRAM_BOT_TOKEN=7123456789:AAHd...  # Бот для РФ
ADMIN_ID=111111111
INSTANCE_NAME=prod-bot-ru
DATABASE_URL=postgresql://...ru-db
```

**Service 2 (EU):**
```bash
TELEGRAM_BOT_TOKEN=7987654321:AABb...  # Бот для EU
ADMIN_ID=222222222
INSTANCE_NAME=prod-bot-eu
DATABASE_URL=postgresql://...eu-db
```

### Вариант B: Несколько админов для одного бота

```bash
ADMIN_ID=111111111,222222222,333333333  # CSV список
```

---

## 🛡️ Production Safety Checklist

### ✅ Singleton Lock

- [x] База PostgreSQL доступна
- [x] Lock TTL = 60 секунд
- [x] Heartbeat каждые 20 секунд
- [x] Автоматическая очистка stale locks

**Проверка:**
```sql
SELECT * FROM singleton_heartbeat;
```

Должна быть **одна запись** с `last_heartbeat < 60 секунд назад`.

### ✅ Pricing Safety

- [x] НЕТ fallback/default цен
- [x] Только модели с `is_pricing_known=true` доступны в UI
- [x] 66 моделей **отключены** (нет подтвержденных цен)
- [x] 23 модели **доступны** (цены из Kie.ai API)

**Проверка:**
```bash
python scripts/kie_truth_audit.py
```

### ✅ Graceful Shutdown

Render отправляет `SIGTERM` при deployment:

```python
# main_render.py
signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)
```

**Что происходит:**
1. Render запускает новый инстанс (green)
2. Старый инстанс получает SIGTERM
3. Старый инстанс:
   - Завершает текущие запросы
   - Освобождает singleton lock
   - Закрывает соединения
4. Новый инстанс забирает lock
5. Старый инстанс выключается

**Проверка логов:**
```
⚠️  Received SIGTERM, shutting down gracefully...
✅ Singleton lock released by prod-bot-1
🛑 Bot stopped
```

---

## 🐛 Troubleshooting

### Проблема: "Singleton lock NOT acquired"

**Причина:** Другой инстанс уже работает или stale lock.

**Решение:**
1. Проверить другие Render services (не запущены ли дубликаты)
2. Проверить heartbeat:
   ```sql
   SELECT * FROM singleton_heartbeat WHERE lock_id = 12345;
   ```
3. Если `last_heartbeat` > 60 секунд назад:
   ```sql
   DELETE FROM singleton_heartbeat WHERE lock_id = 12345;
   ```
4. Restart сервиса в Render

### Проблема: Бот не отвечает

**Проверка:**
1. Логи Render: есть ли ошибки?
2. Healthcheck: `curl https://...onrender.com/health`
3. Webhook статус:
   ```bash
   curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
   ```

**Частые причины:**
- `BOT_MODE != webhook` (должен быть `webhook`)
- `TELEGRAM_BOT_TOKEN` неверный
- Webhook не установлен (проверить логи при старте)

### Проблема: "Модель временно недоступна"

**Причина:** Нет подтвержденной цены от Kie.ai.

**Решение:**
1. Проверить registry:
   ```bash
   grep -A5 '"model_id": "flux/schnell"' models/kie_models_source_of_truth.json
   ```
2. Если `"is_pricing_known": false`, обновить данные:
   ```bash
   python scripts/enrich_registry.py
   ```
3. Если модель все еще без цены - связаться с Kie.ai support

---

## 📊 Мониторинг

### Метрики

1. **Healthcheck** (каждые 5 минут):
   ```bash
   */5 * * * * curl https://kie-bot-production.onrender.com/health
   ```

2. **Database connections**:
   ```sql
   SELECT count(*) FROM pg_stat_activity WHERE datname = 'kie_bot';
   ```

3. **Lock status**:
   ```sql
   SELECT instance_name, last_heartbeat,
          NOW() - last_heartbeat AS age
   FROM singleton_heartbeat;
   ```

### Логирование

- Render автоматически сохраняет логи (7 дней на Free tier)
- Для долгосрочного хранения: интегрировать Sentry/DataDog

---

## 🔐 Безопасность

### ❌ НЕ КОММИТИТЬ В GIT:

- `TELEGRAM_BOT_TOKEN`
- `KIE_API_KEY`
- `DATABASE_URL`
- Любые пароли/секреты

### ✅ Использовать Environment Variables

- Render хранит секреты безопасно
- Логи автоматически маскируют секреты (см. `app/utils/config.py`)

---

## 💰 Стоимость

### Free Tier (для тестов)

- **PostgreSQL:** 1 GB storage, засыпает после 90 дней неактивности
- **Web Service:** 750 часов/месяц, засыпает после 15 минут без трафика

### Starter Plan (для продакшена)

- **PostgreSQL:** $7/месяц, 10 GB storage, всегда активна
- **Web Service:** $7/месяц, 0.1 CPU, 512 MB RAM, всегда активен

---

## ✅ Production-Ready Checklist

- [ ] PostgreSQL база создана (Starter plan для продакшена)
- [ ] ENV переменные настроены (не забыть `BOT_MODE=webhook`)
- [ ] Healthcheck endpoint работает
- [ ] Бот отвечает на `/start`
- [ ] Singleton lock работает (проверить heartbeat)
- [ ] Pricing audit пройден (`python scripts/kie_truth_audit.py`)
- [ ] Graceful shutdown настроен (проверить логи при deployment)
- [ ] Мониторинг настроен (healthcheck + логи)
- [ ] Backup базы (Render делает автоматически на Starter+)

---

**Готово!** 🚀 Бот работает в production на Render.

Для обновлений: просто `git push main` - Render автоматически задеплоит новую версию.
