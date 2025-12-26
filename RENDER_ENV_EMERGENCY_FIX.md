## ЭКСТРЕННЫЙ ФИКС: FREE_TIER_MODEL_IDS не применяется

### Проблема:
Render логи показывают старое значение `FREE_TIER_MODEL_IDS` несмотря на обновление в UI.

### Решение (пошагово):

#### Вариант 1: Проверить сохранение (САМОЕ ВАЖНОЕ)
1. **Render Dashboard** → **454545** → **Environment**
2. Найти `FREE_TIER_MODEL_IDS`
3. Убедиться, что значение:
   ```
   z-image,recraft/remove-background,infinitalk/from-audio,grok-imagine/text-to-image,google/nano-banana
   ```
4. **ОБЯЗАТЕЛЬНО** нажать **"Save Changes"** (зеленая кнопка внизу страницы)
5. Подождать автоматический редеплой (2-3 минуты)

#### Вариант 2: Manual Deploy (если Save не помог)
1. **Render Dashboard** → **454545** → **Manual Deploy**
2. Выбрать **"Clear build cache & deploy"**
3. Нажать **Deploy**
4. Ждать 3-5 минут

#### Вариант 3: Удалить и создать заново
Если Save не работает (баг Render):
1. **Удалить** переменную `FREE_TIER_MODEL_IDS` целиком
2. **Сохранить** (Save Changes)
3. **Добавить** новую переменную:
   - KEY: `FREE_TIER_MODEL_IDS`
   - VALUE: `z-image,recraft/remove-background,infinitalk/from-audio,grok-imagine/text-to-image,google/nano-banana`
4. **Сохранить** (Save Changes)
5. Ждать редеплой

### Проверка успеха:
После деплоя в логах должно появиться:
```
✅ FREE tier matches TOP-5 cheapest
```

Вместо:
```
❌ Startup validation failed: FREE tier не совпадает с TOP-5 cheapest
```

### Временное решение (если не работает):
Можно **удалить** переменную `FREE_TIER_MODEL_IDS` полностью - тогда код будет использовать значение по умолчанию из `app/utils/config.py`, которое уже обновлено.

---

**Дата**: 2025-12-26  
**Статус**: Ожидание действий пользователя на Render Dashboard
