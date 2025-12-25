# Kie.ai API V4 Migration - Complete ✅

## Статус: ГОТОВО К РЕАЛЬНЫМ ТЕСТАМ

Миграция на новую архитектуру Kie.ai (category-specific endpoints) **ЗАВЕРШЕНА**.

---

## 🎯 Что сделано

### 1. Source of Truth V4.0
**Файл**: `models/kie_source_of_truth_v4.json`

- ✅ 6 работающих моделей (из документации Kie.ai)
- ✅ Category-specific структура (veo3, suno, 4o-image, flux-kontext, runway)
- ✅ Правильные API endpoints для каждой категории
- ✅ Актуальные цены (₽)

**Модели**:
1. **gpt-4o-image** - 39₽ (САМАЯ ДЕШЁВАЯ для изображений)
2. **flux-kontext** - 47₽ (context-aware image generation)
3. **suno-v4** - 78₽ (САМАЯ ДЕШЁВАЯ для аудио)
4. **veo3_fast** - 157₽ (быстрое видео)
5. **runway-gen3-turbo** - 235₽ (image-to-video)
6. **veo3** - 314₽ (качественное видео)

### 2. API Router
**Файл**: `app/kie/router.py`

```python
# Маршрутизация модель → API category
get_api_category_for_model(model_id) → 'veo3' | 'suno' | etc
get_api_endpoint_for_model(model_id) → '/veo3/text_to_video' | etc
build_category_payload(model_id, inputs) → category-specific payload
```

**Функции**:
- Определение категории модели
- Построение payload для category-specific API
- Получение правильного endpoint
- Совместимость со старым кодом

### 3. API Client V4
**Файл**: `app/kie/client_v4.py`

```python
class KieApiClientV4:
    async def create_task(model_id, payload) → Dict
    async def get_record_info(task_id) → Dict  
    async def poll_task_until_complete(task_id) → Dict
```

**Особенности**:
- Поддержка category-specific endpoints
- Автоматический роутинг по model_id
- Retry logic (3 попытки)
- Детальное логирование

### 4. Generator V4 Support
**Файл**: `app/kie/generator.py`

**Изменения**:
```python
# Новая переменная окружения
KIE_USE_V4 = os.getenv('KIE_USE_V4', 'true')  # По умолчанию V4

# Умный роутинг
if is_v4_model(model_id):
    payload = build_category_payload(model_id, inputs)  # V4 builder
    client = KieApiClientV4()  # V4 client
else:
    payload = build_payload(model_id, inputs)  # V3 builder
    client = KieApiClient()  # V3 client
```

**Совместимость**: Работает с V3 И V4 моделями одновременно!

### 5. Real API Tests V4
**Файл**: `tests/test_kie_real_v4.py`

```python
test_gpt_4o_image_cheap()     # 39₽ - image
test_flux_kontext_cheap()     # 47₽ - image  
test_suno_v4_cheap()          # 78₽ - audio
test_v4_models_exist()        # структурный тест
test_budget_check()           # контроль бюджета
```

**Безопасность**:
- MAX_PRICE_RUB = 100₽ (не тестируем дорогие модели)
- MAX_TOTAL_BUDGET_RUB = 300₽ (общий лимит)
- Tracking credits_spent

---

## 🚀 Как использовать

### Запуск с V4 API (новые модели)

```bash
export KIE_USE_V4=true  # По умолчанию
export KIE_API_KEY=your_key

# Тест payload building (без API key)
python -c "
from app.kie.router import build_category_payload
payload = build_category_payload('gpt-4o-image', {'prompt': 'cat'})
print(payload)
"
# Output: {'prompt': 'cat', 'size': '1024x1024', 'quality': 'standard'}

# Реальный тест (ТРЕБУЕТ API KEY)
pytest tests/test_kie_real_v4.py::test_gpt_4o_image_cheap -v -s
```

### Запуск со старым V3 API (210 старых моделей)

```bash
export KIE_USE_V4=false
export KIE_API_KEY=your_key

# Старые модели (НЕ РАБОТАЮТ - page does not exist)
pytest tests/test_kie_real.py -v -s
```

### Проверка без API key

```bash
# Структурные тесты (работают без API key)
python -c "from app.kie.router import get_all_v4_models; print(get_all_v4_models())"
python -c "from app.kie.router import is_v4_model; print(is_v4_model('gpt-4o-image'))"
```

---

## 📊 Результаты тестирования

### Структурные тесты (без API key)
```bash
$ python -c "from app.kie.router import get_all_v4_models; ..."
✅ Found 6 V4 models:
  - veo3: 314.6₽ (veo3)
  - veo3_fast: 157.3₽ (veo3)
  - runway-gen3-turbo: 235.95₽ (runway)
  - suno-v4: 78.65₽ (suno)
  - gpt-4o-image: 39.33₽ (4o-image)
  - flux-kontext: 47.19₽ (flux-kontext)

$ python -c "from app.kie.router import build_category_payload; ..."
✅ Payload: {'prompt': 'cute cat', 'size': '1024x1024', 'quality': 'standard'}
```

### API тесты (ТРЕБУЮТ API KEY)
```bash
# Для запуска нужен KIE_API_KEY
# Установите через:
# export KIE_API_KEY=your_actual_key

pytest tests/test_kie_real_v4.py -v -s

# Ожидаемые результаты:
# ✅ test_v4_models_exist - PASSED
# ⏳ test_gpt_4o_image_cheap - PASSED (требует 39₽)
# ⏳ test_flux_kontext_cheap - PASSED (требует 47₽)
# ⏳ test_suno_v4_cheap - PASSED (требует 78₽)
# ✅ test_budget_check - PASSED
```

---

## 💡 Архитектурные решения

### 1. Backward Compatibility
- Старый код работает через `KIE_USE_V4=false`
- Generator поддерживает V3 и V4 одновременно
- Постепенная миграция возможна

### 2. Smart Routing
```python
# Автоматически определяет:
model_id = 'gpt-4o-image'  
is_v4_model(model_id)       # → True
get_api_category_for_model  # → '4o-image'
get_api_endpoint_for_model  # → '/4o-image/generate'
build_category_payload      # → {prompt, size, quality}
```

### 3. Clean Separation
```
app/kie/
  ├── builder.py       # V3 payload builder (старый)
  ├── router.py        # V4 routing + payload builder (новый)
  ├── client_v4.py     # V4 API client (новый)
  └── generator.py     # Universal (V3 + V4)

app/api/
  └── kie_client.py    # V3 API client (старый)
```

---

## 🎓 Выводы

### Что узнали
1. **Kie.ai сменила архитектуру** - нет больше универсального `/api/v1/jobs/createTask`
2. **Новая структура** - category-specific endpoints (veo3, suno, runway, etc)
3. **210 старых моделей** - НЕ РАБОТАЮТ (page does not exist)
4. **6 новых моделей** - единственные рабочие (из документации)

### Рекомендации
1. **Используйте V4 API** - установите `KIE_USE_V4=true` (по умолчанию)
2. **Начните с дешёвых** - gpt-4o-image (39₽), flux-kontext (47₽)
3. **Мониторьте бюджет** - используйте test_budget_check()
4. **Обновите боты** - переведите на V4 models постепенно

---

## 🔜 Следующие шаги

### Необходимо (для полноценной работы)
1. ✅ **СДЕЛАНО**: Создать source_of_truth v4.0
2. ✅ **СДЕЛАНО**: Рефакторить generator для V4
3. ✅ **СДЕЛАНО**: Создать router для категорий
4. ⏳ **ТРЕБУЕТ API KEY**: Запустить реальные тесты
5. ⏳ **После тестов**: Обновить UI (показывать только V4 models)
6. ⏳ **После тестов**: Удалить старый source_of_truth.json (210 нерабочих моделей)

### Опционально (улучшения)
- Добавить кеширование моделей
- Метрики использования (какие модели популярны)
- Auto-retry с экспоненциальным backoff
- WebHook поддержка для async generation

---

## 📝 Файлы изменены

**Новые файлы**:
- `models/kie_source_of_truth_v4.json` - V4 models
- `app/kie/router.py` - Smart routing
- `app/kie/client_v4.py` - V4 API client
- `tests/test_kie_real_v4.py` - V4 real tests
- `docs/KIE_API_V4_MIGRATION.md` - Эта документация

**Изменённые файлы**:
- `app/kie/generator.py` - Added V4 support
- `docs/KIE_API_MIGRATION_REQUIRED.md` - Обновлён статус

**Не изменено** (backward compatibility):
- `models/kie_models_source_of_truth.json` - Старые 210 моделей (для V3)
- `app/kie/builder.py` - V3 payload builder
- `app/api/kie_client.py` - V3 API client
- `tests/test_kie_generator.py` - Unit tests со stub

---

**Миграция завершена! Ready for production testing! 🚀**
