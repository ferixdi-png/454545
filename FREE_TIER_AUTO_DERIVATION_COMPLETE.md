# FREE TIER AUTO-DERIVATION - COMPLETE

## ✅ ЗАДАЧА РЕШЕНА

**Проблема:** Бот падал на старте с ошибкой FREE tier mismatch

**Причина:** Несинхронизированные is_free флаги в SOURCE_OF_TRUTH vs ожидаемый TOP-5 cheapest

**Решение:** Полностью автоматическая система FREE tier - никогда не упадет из-за рассинхрона

---

## 🔧 РЕАЛИЗОВАНО

### 1. ✅ app/pricing/free_tier.py - единый алгоритм

```python
compute_top5_cheapest(model_registry, pricing_map, count=5)
```

**Алгоритм:**
- Eligibility: `model.enabled == True AND model_id in pricing_map`
- Sorting: `(price_rub ASC, model_id ASC)` - детерминистический tie-breaking
- Returns: TOP-N model IDs

**Функции:**
- `compute_top5_cheapest()` - вычисление TOP-5
- `validate_free_tier_override()` - проверка ENV override
- `get_free_tier_models()` - получить FREE tier (auto или override)

### 2. ✅ Startup validation обновлен

**app/utils/startup_validation.py:**
- Expected вычисляется через `compute_top5_cheapest()`
- Actual берется из ENV `FREE_TIER_MODEL_IDS` (или auto)
- Если mismatch is_free флагов в файле → WARNING (не ERROR)
- Показывает четкую подсказку: "Run python scripts/sync_free_tier_from_truth.py"

### 3. ✅ scripts/sync_free_tier_from_truth.py

Синхронизирует is_free флаги с pricing truth:

```bash
python scripts/sync_free_tier_from_truth.py
```

**Действия:**
1. Читает pricing_source_truth.txt
2. Вычисляет TOP-5 cheapest
3. Обновляет is_free флаги в SOURCE_OF_TRUTH.json
4. Обновляет config.py default_free (информационно)

### 4. ✅ Тесты (18 passed)

**tests/test_free_tier_derivation.py:**
- `test_compute_top5_cheapest_basic` - базовая сортировка
- `test_compute_top5_cheapest_with_ties` - alphabetical tie-breaking
- `test_compute_top5_cheapest_skips_disabled` - пропуск disabled моделей
- `test_compute_top5_cheapest_skips_no_pricing` - пропуск моделей без цен
- `test_compute_top5_cheapest_insufficient_models` - ошибка если <5 моделей
- `test_validate_free_tier_override_*` - проверка ENV override
- `test_get_free_tier_models_*` - auto vs override modes
- `test_real_world_scenario` - реальные данные из логов

**tests/test_startup_validation_messages.py:**
- `test_invalid_override_error_message` - понятные ошибки
- `test_override_with_nonexistent_model_error` - несуществующая модель
- `test_override_with_disabled_model_error` - disabled модель в override
- `test_successful_validation_no_errors` - успешная валидация

### 5. ✅ verify_project.py обновлен

Теперь проверяет:
- FREE tier count == 5
- is_free флаги совпадают с `compute_top5_cheapest()`
- Все FREE модели имеют валидную цену

Показывает:
```
✅ FREE tier: TOP-5 cheapest = ['z-image', 'recraft/remove-background', ...]
```

### 6. ✅ README.md - правило

Добавлена секция:

> **⚙️ FREE Tier Auto-Derivation:**
> 
> FREE tier = **TOP-5 cheapest** моделей, вычисляется автоматически
> 
> - **Правило:** Не редактируйте is_free флаги руками
> - **Синхронизация:** `python scripts/sync_free_tier_from_truth.py`

---

## 🎯 ЖЕСТКИЕ ИНВАРИАНТЫ

✅ **Источник моделей:** models/KIE_SOURCE_OF_TRUTH.json  
✅ **Источник цен:** models/pricing_source_truth.txt  
✅ **FREE tier:** TOP-5 cheapest по RUB цене (после markup × FX rate)  
✅ **NO hardcoded lists:** Никаких захардкоженных списков в config.py  
✅ **ENV override:** `FREE_TIER_MODEL_IDS` валидируется (ровно 5, все существуют)  
✅ **Auto-derivation:** Если override не задан - вычисляем автоматически  

---

## ✅ ПРОВЕРКИ

### Локальные тесты
```bash
# FREE tier derivation (13 tests)
pytest tests/test_free_tier_derivation.py -v
# ✅ 13 passed

# Startup validation messages (5 tests)
pytest tests/test_startup_validation_messages.py -v
# ✅ 5 passed

# Startup validation
python -m app.utils.startup_validation
# ✅ Startup validation PASSED - бот готов к запуску

# Project verification
PYTHONPATH=/workspaces/454545:$PYTHONPATH python scripts/verify_project.py
# ✅ All critical checks passed!

# Sync script
PYTHONPATH=/workspaces/454545:$PYTHONPATH python scripts/sync_free_tier_from_truth.py
# ✅ FREE tier sync complete
```

### Результаты

**Startup validation:**
```
Expected FREE tier (TOP-5 cheapest): ['z-image', 'recraft/remove-background', 'infinitalk/from-audio', 'google/imagen4', 'google/imagen4-fast']
✅ FREE tier: 5 models configured
✅ Startup validation PASSED - бот готов к запуску
```

**Sync script:**
```
Computed FREE tier (TOP-5 cheapest): ['z-image', 'recraft/remove-background', 'infinitalk/from-audio', 'google/imagen4', 'google/imagen4-fast']
Updated SOURCE_OF_TRUTH: 0 set to free, 0 cleared
config.py default_free already up to date
✅ FREE tier sync complete
```

**verify_project.py:**
```
✅ FREE tier: TOP-5 cheapest = ['z-image', 'recraft/remove-background', 'infinitalk/from-audio', 'google/imagen4', 'google/imagen4-fast']
✅ All critical checks passed!
```

---

## 📦 КОММИТ

```
commit db00f03
Fix free tier auto-derivation from pricing truth (no startup crash)
```

**Файлы:**
- ✅ app/pricing/free_tier.py (212 lines) - NEW
- ✅ app/utils/startup_validation.py - UPDATED
- ✅ scripts/sync_free_tier_from_truth.py (152 lines) - NEW
- ✅ tests/test_free_tier_derivation.py (338 lines) - NEW
- ✅ tests/test_startup_validation_messages.py (170 lines) - NEW
- ✅ README.md - UPDATED (FREE tier section)
- ✅ models/KIE_SOURCE_OF_TRUTH.json - UPDATED (newline)

**Stats:**
```
8 files changed, 1149 insertions(+), 28 deletions(-)
```

---

## 🚀 СЛЕДУЮЩИЙ ШАГ

### Для деплоя на Render:

```bash
# Manual Deploy
Render Dashboard → 454545 → Manual Deploy → "Clear build cache & deploy"
```

### Ожидаемый результат в Render logs:

```
INFO - Expected FREE tier (TOP-5 cheapest): ['z-image', 'recraft/remove-background', 'infinitalk/from-audio', 'google/imagen4', 'google/imagen4-fast']
INFO - FREE tier: auto-computed (TOP-5 cheapest)
INFO - ✅ FREE tier: 5 models configured
INFO - ✅ Startup validation PASSED - бот готов к запуску
```

### Если всё равно падает с ошибкой:

**Логи покажут понятную ошибку:**
```
FREE_TIER_MODEL_IDS override is invalid:
  - FREE_TIER_MODEL_IDS must have exactly 5 models, got 3
  - Model 'model-x' not in registry

Expected (TOP-5 cheapest): ['z-image', 'recraft/remove-background', 'infinitalk/from-audio', 'google/imagen4', 'google/imagen4-fast']
Got: ['model-a', 'model-b', 'model-c']
```

**Решение:**
1. Удалить ENV `FREE_TIER_MODEL_IDS` (если есть)
2. Перезапустить деплой

---

## 📈 ПРЕИМУЩЕСТВА РЕШЕНИЯ

✅ **Никогда не упадет** из-за рассинхрона is_free флагов  
✅ **Детерминистический** алгоритм (tie-breaking по алфавиту)  
✅ **Автоматический** - FREE tier = TOP-5 cheapest всегда  
✅ **Понятные ошибки** - показывает expected vs actual  
✅ **Проверяется тестами** - 18 тестов покрывают все сценарии  
✅ **Синхронизация** - скрипт sync_free_tier_from_truth.py  
✅ **Override support** - ENV FREE_TIER_MODEL_IDS с валидацией  

---

## 🎉 РЕЗЮМЕ

Система FREE tier теперь:
- ✅ Полностью автоматическая
- ✅ Детерминистическая (стабильная при tie-breaking)
- ✅ Валидируется на старте
- ✅ Показывает понятные ошибки
- ✅ Покрыта тестами (18 passed)
- ✅ Документирована (README)

**БОТ ГОТОВ К ДЕПЛОЮ НА RENDER!** 🚀
