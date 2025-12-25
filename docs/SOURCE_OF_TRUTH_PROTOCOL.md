# 🎯 SOURCE OF TRUTH PROTOCOL - KIE.AI MODELS

## ФИЛОСОФИЯ

**ЕДИНСТВЕННЫЙ ИСТОЧНИК ИСТИНЫ** для каждой модели - это её страница на **kie.ai/models/{model_id}**

### Почему это важно:

1. **Kie.ai - первоисточник** - они предоставляют API, они знают настройки
2. **"Copy page" button** - официальный способ получить рабочие примеры
3. **Парсинг ОДИН РАЗ** - фиксируем результат, больше не трогаем (если работает)
4. **Валидация реальными тестами** - убеждаемся что модель работает на практике

---

## ПРОЦЕСС ПАРСИНГА

### 1. Первичный парсинг (ОДИН РАЗ)

```bash
# Парсим все 77 моделей
python scripts/MASTER_PARSE_KIE_MODELS.py

# Тестовый режим (первые 3 модели)
python scripts/MASTER_PARSE_KIE_MODELS.py --test

# Лимит (например 10 моделей)
python scripts/MASTER_PARSE_KIE_MODELS.py --limit 10
```

**Что парсится:**

- ✅ `tech_model_id` - технический ID для API запросов
- ✅ `input_schema` - структура входных параметров (required/optional/properties)
- ✅ `output_type` - тип выхода (image/video/audio/text)
- ✅ `pricing` - стоимость в USD/credits
- ✅ HTML кэш страницы - для отладки

**Результат:**

- `models/kie_parsed_truth.json` - ЗАФИКСИРОВАННЫЙ источник истины
- `cache/kie_pages/*.html` - кэш HTML страниц для отладки

---

### 2. Валидация результатов

```bash
# Проверяем что парсинг корректный
python scripts/validate_all_models_schema.py

# Smoke test на TOP-5 cheapest (DRY RUN - без реальных запросов)
python scripts/smoke_test_api_real.py --dry-run

# REAL API TEST (⚠️ тратит ~6₽)
export KIE_API_KEY=your_key_here
python scripts/smoke_test_api_real.py --real
```

---

### 3. Merge в final_truth.json

Только ПОСЛЕ валидации:

```bash
# Объединяем parsed data с существующим registry
python scripts/merge_parsed_truth.py
```

Это обновит `models/kie_models_final_truth.json` с:
- ✅ Актуальными `input_schema` с реальных страниц
- ✅ Правильными `tech_model_id` для API
- ✅ Свежими ценами

---

## КОГДА ВОЗВРАЩАТЬСЯ К ПАРСИНГУ

**ТОЛЬКО** в следующих случаях:

### ❌ НЕ нужно парсить заново:

- Модель работает корректно
- Schema валидная
- Payload builder создает запросы
- Smoke test проходит

### ✅ НУЖНО парсить заново:

1. **Модель НЕ РАБОТАЕТ** в production
   - API возвращает ошибку 400/422 (invalid payload)
   - Timeout при создании задачи
   - Неправильный формат ответа

2. **Kie.ai обновил модель**
   - Изменились параметры
   - Добавились новые возможности
   - Изменилась цена

3. **Добавилась новая модель**
   - Парсим ТОЛЬКО новую модель
   - `python scripts/MASTER_PARSE_KIE_MODELS.py --model new-model-id`

---

## СТРУКТУРА ФАЙЛОВ

```
models/
├── kie_models_final_truth.json      # ✅ PRODUCTION SOURCE OF TRUTH
├── kie_parsed_truth.json            # 📝 Raw parsed data (before merge)
├── kie_models_source_of_truth.json  # 🗄️ Old/legacy (210 models, no schema)
└── kie_scraped_models.json          # 🗄️ Old scraper output

cache/
└── kie_pages/
    ├── flux_dev.html                # HTML кэш для отладки
    ├── wan_2-5-image-to-video.html
    └── ...

scripts/
├── MASTER_PARSE_KIE_MODELS.py       # 🎯 MASTER PARSER (используй этот!)
├── sync_kie_site_truth.py           # 🗄️ Old parser
├── scrape_all_kie_models.py         # 🗄️ Old scraper
└── merge_parsed_truth.py            # 🔄 Merge tool
```

---

## WORKFLOW ДЛЯ НОВОЙ МОДЕЛИ

### Пример: добавляем новую модель `sora/turbo-2`

```bash
# 1. Добавляем модель в registry вручную (минимальные данные)
python -c "
import json
with open('models/kie_models_final_truth.json') as f:
    data = json.load(f)

data['models'].append({
    'model_id': 'sora/turbo-2',
    'display_name': 'Sora Turbo 2.0',
    'category': 'text-to-video',
    'enabled': false,  # Disabled пока не спарсим
    'pricing': {'usd_per_run': 0.5, 'rub_per_use': 39.29}
})

with open('models/kie_models_final_truth.json', 'w') as f:
    json.dump(data, f, indent=2)
"

# 2. Парсим ТОЛЬКО эту модель
python scripts/MASTER_PARSE_KIE_MODELS.py --model sora/turbo-2

# 3. Проверяем результат
cat models/kie_parsed_truth.json | jq '.models[] | select(.model_id == "sora/turbo-2")'

# 4. Merge в final_truth
python scripts/merge_parsed_truth.py --only sora/turbo-2

# 5. Валидация
python scripts/validate_all_models_schema.py

# 6. Real test
export KIE_API_KEY=xxx
python scripts/smoke_test_api_real.py --model sora/turbo-2

# 7. Если работает - enable
python -c "
import json
with open('models/kie_models_final_truth.json') as f:
    data = json.load(f)

for m in data['models']:
    if m['model_id'] == 'sora/turbo-2':
        m['enabled'] = true

with open('models/kie_models_final_truth.json', 'w') as f:
    json.dump(data, f, indent=2)
"
```

---

## КРИТИЧЕСКИЕ ПРАВИЛА

### ✅ DO:

1. **Парсить каждую модель со страницы kie.ai** - это SOURCE OF TRUTH
2. **Кэшировать HTML** - для отладки и re-parsing без запросов
3. **Валидировать реальными API тестами** - парсинг может ошибаться
4. **Фиксировать результат** - не парсить заново если работает
5. **Документировать изменения** - changelog в registry

### ❌ DON'T:

1. **НЕ создавать schema вручную** - только с kie.ai страниц
2. **НЕ угадывать параметры** - если не спарсилось, пропускаем
3. **НЕ парсить заново без причины** - только если не работает
4. **НЕ доверять старым данным** - kie.ai может обновить модель
5. **НЕ деплоить без валидации** - сначала smoke test

---

## TROUBLESHOOTING

### Проблема: Парсинг не нашел input_schema

**Решение:**

1. Проверь HTML кэш: `cache/kie_pages/{model_id}.html`
2. Открой страницу руками: `https://kie.ai/models/{model_id}`
3. Найди "Copy page" или API examples
4. Если нет примеров - модель может быть beta/deprecated
5. Добавь schema вручную ТОЛЬКО после проверки страницы
6. Документируй в `parse_notes` поле

### Проблема: Model ID не совпадает с tech_model_id

**Это нормально!**

- `model_id`: slug для URL (`flux/dev`)
- `tech_model_id`: для API запросов (`flux-dev-1.1-ultra`)

Парсер автоматически извлекает `tech_model_id` из примеров кода.

### Проблема: Парсинг timeout

**Решение:**

1. Увеличь timeout в parser: `timeout=60000`
2. Проверь интернет соединение
3. Kie.ai может быть недоступен - retry later
4. Используй кэш если есть

---

## MAINTENANCE

### Ежемесячная проверка (рекомендуется)

```bash
# 1. Re-parse всех моделей
python scripts/MASTER_PARSE_KIE_MODELS.py

# 2. Сравни с current registry
python scripts/compare_parsed_vs_current.py

# 3. Если есть изменения - создай report
# 4. Smoke test changed models
# 5. Deploy если всё ОК
```

### Перед production deploy

```bash
# ALWAYS:
1. Validate schema (100% pass required)
2. Quick health check (ALL PASS required)
3. Smoke test TOP-5 cheapest (REAL mode)
4. Check git diff для manual review
5. Commit + Push только после валидации
```

---

## CHANGELOG

### v1.0 - 2025-12-24

- ✅ Создан MASTER_PARSE_KIE_MODELS.py
- ✅ Зафиксирован SOURCE OF TRUTH протокол
- ✅ Парсинг с Playwright + BeautifulSoup
- ✅ HTML кэширование для отладки
- ✅ Автоматическое извлечение schema/pricing/tech_model_id

---

**ИТОГ:** 

Этот протокол гарантирует что:
1. Каждая модель спарсена с официального источника (kie.ai)
2. Данные зафиксированы и не меняются без причины
3. Все изменения валидируются реальными тестами
4. Production всегда стабилен и работает корректно

**Source of Truth = kie.ai pages → Parsed once → Fixed → Validated → Production**
