# Contributing Guidelines

Спасибо за интерес к проекту! Этот документ описывает процесс контрибуции.

---

## 🎯 Как начать

1. **Fork** репозитория
2. **Clone** вашего fork
3. **Create branch** для ваших изменений
4. **Make changes** следуя guidelines ниже
5. **Test** ваши изменения
6. **Submit PR** с описанием изменений

---

## 📋 Перед отправкой PR

### ✅ Обязательные проверки:

```bash
# 1. Компиляция без ошибок
python -m compileall .

# 2. Все verification scripts зелёные
python scripts/check_all.py

# 3. Pytest (хотя бы unit-тесты)
pytest tests/test_pricing.py -v
pytest tests/test_cheapest_models.py -v

# 4. Code style (если есть)
# black . --check
# flake8 .
```

### 📝 Commit messages:

Используйте [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new feature
fix: fix bug in payment system
docs: update README
refactor: restructure pricing module
test: add tests for generator
chore: update dependencies
```

---

## 🏗️ Структура кода

### Основные модули:

- `app/kie/` - интеграция с Kie.ai API
- `app/payments/` - pricing, balance, transactions
- `app/database/` - PostgreSQL/SQLite
- `app/ui/` - Telegram UI handlers
- `bot/handlers/` - Aiogram handlers
- `models/` - SOURCE_OF_TRUTH и схемы
- `scripts/` - утилиты и проверки

### Важные файлы:

- `models/KIE_SOURCE_OF_TRUTH.json` - **НЕ редактируйте вручную!** Генерируется скриптами
- `main_render.py` - entry point
- `requirements.txt` - зависимости

---

## 🧪 Тестирование

### Unit тесты:

```bash
# Pricing logic
pytest tests/test_pricing.py -v

# Cheapest models
pytest tests/test_cheapest_models.py -v

# Generator (без API)
pytest tests/test_kie_generator.py -v -k "not real"
```

### Integration тесты:

```bash
# С реальным API (осторожно - тратит кредиты!)
pytest tests/test_kie_real.py -v

# V4 API тесты
pytest tests/test_kie_real_v4.py -v
```

### Покрытие:

```bash
pytest --cov=app --cov-report=html
# Откройте htmlcov/index.html
```

---

## 📚 Документация

### Когда обновлять:

- **README.md** - при добавлении major features
- **QUICK_START_DEV.md** - при изменении setup процесса
- **DEPLOYMENT.md** - при изменении deploy конфигурации
- Docstrings - всегда для новых функций/классов

### Стиль docstrings:

```python
def calculate_price(usd: float, markup: float = 2.0) -> float:
    """
    Calculate RUB price with markup.
    
    Args:
        usd: Price in USD
        markup: Markup multiplier (default 2.0)
    
    Returns:
        Price in RUB with markup applied
    
    Example:
        >>> calculate_price(0.5)
        78.0  # Assuming USD_TO_RUB = 78
    """
    return usd * get_usd_to_rub() * markup
```

---

## 🔧 Стиль кода

### Python:

- **PEP 8** для стиля
- **Type hints** для всех функций
- **Docstrings** для public API
- **Max line length:** 100 символов
- **Imports:** сортированные, grouped (stdlib, 3rd party, local)

### Пример:

```python
from typing import Dict, Any, Optional
import logging

from aiogram import types
from app.database.services import DatabaseService

logger = logging.getLogger(__name__)


async def handle_payment(
    message: types.Message,
    amount: float,
    db: DatabaseService
) -> Dict[str, Any]:
    """
    Process payment for user.
    
    Args:
        message: Telegram message
        amount: Amount in RUB
        db: Database service
    
    Returns:
        Payment result dict
    """
    user_id = message.from_user.id
    
    # Check balance
    balance = await db.get_balance(user_id)
    if balance < amount:
        return {"success": False, "reason": "insufficient_balance"}
    
    # Process payment
    await db.deduct_balance(user_id, amount)
    
    logger.info(f"Payment processed: user={user_id}, amount={amount}")
    
    return {"success": True, "new_balance": balance - amount}
```

---

## 🚫 Чего НЕ делать

### ❌ НЕ редактируйте напрямую:

- `models/KIE_SOURCE_OF_TRUTH.json` - только через скрипты
- Generated files (`__pycache__`, `.pyc`)
- `bot_local.db` - локальная БД

### ❌ НЕ коммитьте:

- `.env` файлы
- API keys/secrets
- Локальные БД (`*.db`)
- IDE конфиги (`.vscode/`, `.idea/`)
- Большие binary файлы

### ❌ НЕ ломайте:

- Обратную совместимость API
- Существующие тесты без причины
- Production конфигурацию

---

## 🎨 Типичные задачи

### Добавить новую модель:

1. Обновите `models/KIE_SOURCE_OF_TRUTH.json` через scraper
2. Добавьте тесты в `tests/test_kie_real.py`
3. Проверьте pricing в `tests/test_pricing.py`

### Исправить баг:

1. Напишите failing test
2. Исправьте баг
3. Убедитесь что test проходит
4. Проверьте что не сломали другие тесты

### Добавить feature:

1. Обсудите в Issue (для больших изменений)
2. Создайте feature branch
3. Напишите код + тесты
4. Обновите документацию
5. Отправьте PR

---

## 🐛 Баг репорты

### Хороший баг репорт содержит:

- **Описание:** что ожидалось vs что получилось
- **Steps to reproduce:** как воспроизвести
- **Environment:** OS, Python version, bot mode
- **Logs:** релевантные логи (без secrets!)
- **Screenshots:** если UI баг

### Template:

```markdown
**Описание:**
Бот не отвечает на /start команду

**Воспроизведение:**
1. Запустить бота локально
2. Отправить /start
3. Никакого ответа

**Environment:**
- OS: Ubuntu 22.04
- Python: 3.11
- BOT_MODE: polling

**Логи:**
```
2025-12-25 10:00:00 ERROR - Command /start failed...
```

**Ожидаемое поведение:**
Бот должен ответить приветственным сообщением
```

---

## 💡 Feature requests

### Хороший feature request:

- **Use case:** зачем это нужно
- **Proposed solution:** как это может работать
- **Alternatives:** рассмотренные альтернативы
- **Impact:** кого это затронет

---

## 📞 Контакты

- **Issues:** [GitHub Issues](https://github.com/ferixdi-png/5656/issues)
- **Discussions:** [GitHub Discussions](https://github.com/ferixdi-png/5656/discussions)
- **Security:** Приватные уязвимости → прямой контакт с maintainer

---

## 📜 License

Проверьте LICENSE файл в корне репозитория.

---

**Спасибо за вклад в проект! 🎉**
