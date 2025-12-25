"""
Global error handler - user-friendly error messages.
Contract: All errors caught, user always gets response.
"""
from aiogram import Router
from aiogram.types import ErrorEvent
import logging

logger = logging.getLogger(__name__)

router = Router(name="error_handler")


@router.error()
async def global_error_handler(event: ErrorEvent):
    """
    Global error handler - always respond to user.
    
    Contract:
    - User gets friendly message (no stacktrace)
    - Suggests /start as next step
    - Never silent
    """
    exception = event.exception
    update = event.update
    
    # Log error for debugging (with full stacktrace)
    logger.error(f"Error in update {update.update_id}: {exception}", exc_info=exception)
    
    # User-friendly error message (no stacktrace)
    # Определяем тип ошибки для более понятного сообщения
    if "timeout" in str(exception).lower():
        error_message = (
            "⏱ <b>Превышено время ожидания</b>\n\n"
            "Сервер слишком долго отвечает. Попробуйте:\n"
            "• Подождать минуту и повторить\n"
            "• Выбрать другую модель\n"
            "• Нажать /start для главного меню"
        )
    elif "network" in str(exception).lower() or "connection" in str(exception).lower():
        error_message = (
            "🌐 <b>Проблема с подключением</b>\n\n"
            "Не удалось связаться с сервером.\n\n"
            "Попробуйте через минуту или нажмите /start"
        )
    else:
        error_message = (
            "⚠️ <b>Что-то пошло не так</b>\n\n"
            "Мы уже знаем об этой проблеме и работаем над исправлением.\n\n"
            "💡 Попробуйте:\n"
            "• Повторить действие\n"
            "• Нажать /start для главного меню\n"
            "• Обратиться в поддержку, если проблема повторяется"
        )
    
    # Determine update type and respond accordingly
    try:
        if update.message:
            await update.message.answer(error_message)
        elif update.callback_query:
            callback = update.callback_query
            await callback.answer("⚠️ Ошибка")
            try:
                await callback.message.answer(error_message)
            except Exception as msg_err:
                # If edit fails, try to send new message (catch Telegram API errors)
                # MASTER PROMPT: No bare except - catch Exception for Telegram API failures
                logger.debug(f"Failed to send error message via callback: {msg_err}")
                try:
                    await callback.message.answer(error_message)
                except Exception as retry_err:
                    logger.debug(f"Retry also failed: {retry_err}")
                    pass
        elif update.edited_message:
            await update.edited_message.answer(error_message)
    except Exception as e:
        # Last resort - log but don't crash
        logger.critical(f"Failed to send error message to user: {e}")
    
    # Don't re-raise - we've handled it
    return True
