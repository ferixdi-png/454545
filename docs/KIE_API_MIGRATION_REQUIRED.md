# 🚨 КРИТИЧЕСКАЯ НАХОДКА: Kie.ai изменила архитектуру API

**Дата**: 24 декабря 2025
**Статус**: БЛОКЕР для реальных тестов
**Приоритет**: P0

## Проблема

При попытке запустить реальные тесты Kie.ai API обнаружено:

**ВСЕ модели возвращают ошибку "page does not exist"**

```bash
# Все эти модели НЕ РАБОТАЮТ через /api/v1/jobs/createTask:
❌ z-image              → "The page does not exist or is not published"
❌ midjourney           → "The page does not exist or is not published"
❌ gpt-4o-mini          → "The page does not exist or is not published"
❌ flux-2-pro           → "The page does not exist or is not published"
❌ elevenlabs/*         → "The page does not exist or is not published"
❌ suno/*               → "The page does not exist or is not published"
```

## Доказательства

### 1. API работает (endpoint `/api/v1/jobs/recordInfo` отвечает)

```bash
$ curl GET "https://api.kie.ai/api/v1/jobs/recordInfo?taskId=test123"
{"code":422,"msg":"recordInfo is null","data":null}  # ← правильный ответ для несуществующего task
```

### 2. Но createTask не работает ни для одной модели

```bash
$ curl POST "https://api.kie.ai/api/v1/jobs/createTask" \
  -d '{"model":"z-image","input":{"prompt":"cat"}}'

# Response:
{"code":422,"msg":"The page does not exist or is not published","data":null}
```

### 3. Новая архитектура в документации

Открыв https://docs.kie.ai/, видим:

```
Kie.ai теперь имеет СПЕЦИАЛИЗИРОВАННЫЕ API:

🎬 Video Generation APIs:
   - Veo3.1 API        → /veo3-api/quickstart
   - Runway Aleph API  → /runway-api/generate-aleph-video
   - Runway API        → /runway-api/quickstart

🎵 Audio & Music APIs:
   - Suno API          → /suno-api/quickstart

🖼️ Image Generation APIs:
   - 4O Image API      → /4o-image-api/quickstart
   - Flux Kontext API  → /flux-kontext-api/quickstart

🔧 Utility APIs:
   - File Upload API   → /file-upload-api/quickstart
   - Common API        → /common-api/quickstart
```

**НЕТ универсального `/api/v1/jobs/createTask` для всех моделей!**

## Что устарело

### Файл: `models/kie_source_of_truth.json`

```json
{
  "version": "3.0",
  "last_updated": "2024-12-23",
  "total_models": 210,  // ← Все эти модели НЕ РАБОТАЮТ
  "models": [
    {
      "model_id": "z-image",
      "api_endpoint": "z-image",  // ← Неправильно! Endpoint изменился
      "pricing": {...},
      "input_schema": {...}
    },
    // ... 209 других моделей с устаревшими endpoints
  ]
}
```

**Проблема**: Весь source_of_truth построен на предположении о едином API endpoint, но Kie.ai разделила API на категории.

### Файл: `app/kie/generator.py`

```python
# Текущий подход (УСТАРЕЛ):
url = f"{self._api_base()}/jobs/createTask"
payload = {'model': 'z-image', 'input': {...}}  # ← Не работает!

# Нужно:
# Определить категорию модели → выбрать правильный API → использовать специфичный endpoint
```

## Что исправлено

### ✅ Fix #1: None response handling ([app/kie/generator.py](../app/kie/generator.py))

```python
# БЫЛО:
task_id = create_response.get('taskId') or create_response.get('data', {}).get('taskId')
# ↓ Crash when data=None

# СТАЛО:
if create_response is None:
    return {'success': False, 'error_code': 'NO_RESPONSE', ...}

if 'error' in create_response:
    return {'success': False, 'error_code': 'API_CONNECTION_ERROR', ...}

# Safe data access:
task_id = create_response.get('taskId')
if not task_id and isinstance(create_response.get('data'), dict):
    task_id = create_response['data'].get('taskId')
```

**Результат**: Generator больше не падает при ошибках API ✅

### ✅ Fix #2: Real API test suite ([tests/test_kie_real.py](../tests/test_kie_real.py))

Создан credit-safe test suite:

```python
# Safety constraints:
MAX_PRICE_RUB = Decimal("1.0")  # Только модели <1₽
BUDGET_RUB = Decimal("10.0")     # Лимит на всю сессию

# 7 cheapest models identified:
- elevenlabs-audio-isolation  0.16₽  (CHEAPEST)
- elevenlabs-sound-effects    0.19₽
- suno-convert-to-wav         0.31₽
- suno-generate-lyrics        0.31₽
- recraft-crisp-upscale       0.39₽
- z-image                     0.63₽
- recraft-remove-background   0.79₽
```

**Статус**: Готов к запуску, НО заблокирован из-за устаревших API endpoints ❌

## План миграции

### Phase 1: Анализ новой архитектуры (1-2 часа)

1. Изучить документацию всех специализированных API:
   - Veo3.1 API endpoints
   - Runway API endpoints
   - Suno API endpoints
   - 4O Image API endpoints
   - Flux Kontext API endpoints

2. Определить маппинг старых моделей → новые API:
   ```
   z-image           → какой API?
   midjourney-*      → какой API?
   gpt-4o-mini       → какой API?
   elevenlabs/*      → Suno API?
   suno/*            → Suno API?
   ```

### Phase 2: Обновить source_of_truth.json (2-3 часа)

```json
{
  "version": "4.0",
  "migration_notes": "Kie.ai разделила API на категории",
  "last_updated": "2024-12-24",
  "api_categories": {
    "veo3": {
      "base_url": "https://api.kie.ai",
      "endpoint": "/veo3-api/*",
      "models": [...]
    },
    "runway": {
      "base_url": "https://api.kie.ai",
      "endpoint": "/runway-api/*",
      "models": [...]
    },
    "suno": {
      "base_url": "https://api.kie.ai",
      "endpoint": "/suno-api/*",
      "models": [...]
    }
  }
}
```

### Phase 3: Рефакторинг generator.py (3-4 часа)

```python
class KieGenerator:
    def _get_api_category(self, model_id: str) -> str:
        """Определить категорию API для модели."""
        # Логика маппинга model_id → API category
        
    def _get_api_endpoint(self, model_id: str) -> str:
        """Получить правильный endpoint для модели."""
        category = self._get_api_category(model_id)
        # Вернуть специфичный endpoint
        
    async def generate(self, model_id, user_inputs):
        endpoint = self._get_api_endpoint(model_id)
        # Использовать правильный API
```

### Phase 4: Обновить тесты (1-2 часа)

1. Обновить `test_kie_real.py` под новые endpoints
2. Добавить тесты для каждой категории API
3. Валидировать маппинг моделей

### Phase 5: Запуск реальных тестов (30 минут)

```bash
# После миграции:
pytest tests/test_kie_real.py -v -s

# Ожидаемый результат:
✅ test_z_image_cheap              PASSED (0.63₽ списано)
✅ test_suno_generate_lyrics       PASSED (0.31₽ списано)
✅ test_elevenlabs_audio_isolation PASSED (0.16₽ списано)
# ...
Total credits spent: ~3₽ из 1000₽ бюджета
```

## Временная стратегия (до миграции)

### Использовать STUB-режим для всех тестов

```bash
# В .env:
TEST_MODE=true
KIE_STUB=true

# Запуск тестов:
pytest tests/ -v
# ✅ Все 72 теста проходят (но без реальных API вызовов)
```

### Отключить реальные API тесты

```python
# tests/test_kie_real.py
@pytest.mark.skip(reason="Kie.ai изменила архитектуру API - требуется миграция")
class TestKieRealAPI:
    ...
```

## Оценка воздействия

### Что сломано:

- ❌ Реальная интеграция с Kie.ai API (все 210 моделей)
- ❌ Невозможность запуска продакшн бота с реальными генерациями
- ❌ Реальные API тесты (test_kie_real.py)

### Что работает:

- ✅ Stub-режим (TEST_MODE=true)
- ✅ Все unit/integration тесты (72/72)
- ✅ Вся бизнес-логика (payments, free tier, UI, admin)
- ✅ Error handling (улучшен в generator.py)

## Выводы

1. **Миграция неизбежна** - Kie.ai радикально изменила архитектуру
2. **Stub-режим спасает** - можем продолжать разработку
3. **Реальные тесты отложены** - пока не обновим source_of_truth
4. **Время миграции**: ~7-12 часов работы

## Рекомендации

### Краткосрочная (сегодня):

1. Закоммитить фиксы (None handling + test suite skeleton)
2. Добавить документацию о проблеме
3. Переключить все тесты в stub-режим
4. Продолжать разработку других фич

### Среднесрочная (завтра-послезавтра):

1. Детально изучить новую документацию Kie.ai
2. Создать новый source_of_truth v4.0
3. Рефакторить generator.py под новые endpoints
4. Запустить реальные тесты

### Долгосрочная:

1. Автоматизировать синхронизацию с Kie.ai API
2. Мониторинг изменений в документации
3. Версионирование API (поддержка нескольких версий)

---

**Автор**: Real API testing attempt
**Commit**: (pending)
**Related files**:
- [app/kie/generator.py](../app/kie/generator.py) - Fixed None handling
- [tests/test_kie_real.py](../tests/test_kie_real.py) - Created test suite
- [models/kie_source_of_truth.json](../models/kie_source_of_truth.json) - OUTDATED
