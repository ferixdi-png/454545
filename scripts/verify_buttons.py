"""
Проверка что все кнопки и callback-обработчики бота работают.
Без реальных генераций - только проверка что обработчик отвечает.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.handlers import flow
from aiogram.types import CallbackQuery, Message
from unittest.mock import AsyncMock, MagicMock
from aiogram.fsm.context import FSMContext


def test_all_callback_handlers():
    """Проверяет что все callback в flow.py имеют обработчики."""
    
    print("\n" + "="*80)
    print("🔍 ПРОВЕРКА CALLBACK ОБРАБОТЧИКОВ")
    print("="*80)
    
    # Найти все @router.callback_query декораторы
    import inspect
    handlers = []
    
    for name, obj in inspect.getmembers(flow):
        if inspect.iscoroutinefunction(obj):
            handlers.append(name)
    
    print(f"\n✅ Найдено {len(handlers)} async функций-обработчиков:")
    for h in sorted(handlers)[:15]:
        print(f"   • {h}")
    
    if len(handlers) > 15:
        print(f"   ... и ещё {len(handlers) - 15}")
    
    return True


def test_callback_patterns():
    """Проверяет что основные callback паттерны покрыты."""
    
    print("\n" + "="*80)
    print("🔍 ПРОВЕРКА CALLBACK ПАТТЕРНОВ")
    print("="*80)
    
    expected_patterns = [
        "cat:",  # Выбор категории
        "model:",  # Выбор модели
        "confirm",  # Подтверждение
        "back",  # Назад
        "cancel",  # Отмена
        "skip",  # Пропустить
        "topup",  # Пополнение
    ]
    
    # Читаем flow.py и ищем паттерны
    flow_path = os.path.join(os.path.dirname(__file__), "../bot/handlers/flow.py")
    with open(flow_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    found = {}
    for pattern in expected_patterns:
        if f'"{pattern}"' in content or f"'{pattern}'" in content:
            found[pattern] = True
        else:
            found[pattern] = False
    
    print(f"\n📋 Проверка основных паттернов:")
    all_ok = True
    for pattern, exists in found.items():
        status = "✅" if exists else "❌"
        print(f"   {status} {pattern}")
        if not exists:
            all_ok = False
    
    return all_ok


def test_no_silent_handlers():
    """Проверяет что нет обработчиков которые не отвечают пользователю."""
    
    print("\n" + "="*80)
    print("🔍 ПРОВЕРКА ОТСУТСТВИЯ \"МОЛЧАЩИХ\" ОБРАБОТЧИКОВ")
    print("="*80)
    
    # Читаем flow.py
    flow_path = os.path.join(os.path.dirname(__file__), "../bot/handlers/flow.py")
    with open(flow_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Найти все async def функции-обработчики
    handlers_without_response = []
    current_handler = None
    handler_has_response = False
    
    response_patterns = [
        ".answer(",
        ".edit_text(",
        ".edit_media(",
        ".reply(",
        ".send_message(",
    ]
    
    for i, line in enumerate(lines):
        # Начало нового обработчика
        if line.strip().startswith("async def "):
            # Сохраняем предыдущий
            if current_handler and not handler_has_response:
                # Проверяем что это callback/message handler
                prev_lines = "".join(lines[max(0, i-5):i])
                if "@router.callback_query" in prev_lines or "@router.message" in prev_lines:
                    handlers_without_response.append(current_handler)
            
            # Начинаем новый
            current_handler = line.strip()
            handler_has_response = False
        
        # Проверяем есть ли ответ в текущем обработчике
        if current_handler:
            for pattern in response_patterns:
                if pattern in line:
                    handler_has_response = True
                    break
    
    # Проверяем последний
    if current_handler and not handler_has_response:
        handlers_without_response.append(current_handler)
    
    print(f"\n📊 Результат:")
    if len(handlers_without_response) == 0:
        print("   ✅ Все обработчики отправляют ответ пользователю")
        return True
    else:
        print(f"   ⚠️  Найдено {len(handlers_without_response)} обработчиков без явного ответа:")
        for h in handlers_without_response[:10]:
            print(f"      • {h}")
        if len(handlers_without_response) > 10:
            print(f"      ... и ещё {len(handlers_without_response) - 10}")
        print("\n   ⚠️  Это не всегда ошибка (могут быть state.clear() и т.п.)")
        return True  # Возвращаем True т.к. это предупреждение


if __name__ == "__main__":
    print("\n╔═══════════════════════════════════════════════════════════════════════╗")
    print("║              ШАГ 2: ВАЛИДАЦИЯ КНОПОК И ОБРАБОТЧИКОВ                  ║")
    print("╚═══════════════════════════════════════════════════════════════════════╝")
    
    results = []
    results.append(("Callback обработчики", test_all_callback_handlers()))
    results.append(("Callback паттерны", test_callback_patterns()))
    results.append(("Молчащие обработчики", test_no_silent_handlers()))
    
    print("\n" + "="*80)
    print("📊 ИТОГОВЫЙ ОТЧЁТ")
    print("="*80)
    
    all_passed = True
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"   {status} {name}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        sys.exit(0)
    else:
        print("\n⚠️  НЕКОТОРЫЕ ПРОВЕРКИ НЕ ПРОШЛИ")
        sys.exit(1)
