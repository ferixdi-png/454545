"""Centralized error taxonomy and classification helpers.

Goal: stable short codes for logs + user-friendly messages.
Never leak secrets. Keep messages actionable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class ErrorCode(str, Enum):
    INPUT = "E_INPUT"
    MODEL = "E_MODEL"
    RATE_LIMIT = "E_RATE"
    TIMEOUT = "E_TIMEOUT"
    UPSTREAM = "E_UPSTREAM"
    CALLBACK = "E_CALLBACK"
    PAYMENT = "E_PAYMENT"
    INTERNAL = "E_INTERNAL"


@dataclass(frozen=True)
class BotErrorInfo:
    code: ErrorCode
    user_message: str
    debug_reason: str


def classify_api_failure(fail_code: Optional[str], fail_msg: Optional[str]) -> BotErrorInfo:
    """Map Kie.ai fail_code/fail_msg to our stable codes and user messages."""
    fc = (fail_code or "").upper().strip()
    fm = (fail_msg or "").strip()

    if fc in {"INVALID_INPUT", "INVALID_FILE", "FILE_TOO_LARGE"}:
        return BotErrorInfo(
            code=ErrorCode.INPUT,
            user_message="Некорректные входные данные. Проверьте формат/размер и попробуйте ещё раз.",
            debug_reason=f"fail_code={fc} fail_msg={fm}",
        )
    if fc in {"MODEL_NOT_FOUND"}:
        return BotErrorInfo(
            code=ErrorCode.MODEL,
            user_message="Модель недоступна. Обновите меню (/start) и выберите модель снова.",
            debug_reason=f"fail_code={fc} fail_msg={fm}",
        )
    if fc in {"RATE_LIMIT", "TOO_MANY_REQUESTS"}:
        return BotErrorInfo(
            code=ErrorCode.RATE_LIMIT,
            user_message="Слишком много запросов. Подождите 20–30 секунд и повторите.",
            debug_reason=f"fail_code={fc} fail_msg={fm}",
        )
    if fc in {"TIMEOUT"}:
        return BotErrorInfo(
            code=ErrorCode.TIMEOUT,
            user_message="Превышено время ожидания. Попробуйте ещё раз через минуту.",
            debug_reason=f"fail_code={fc} fail_msg={fm}",
        )
    if fc in {"INSUFFICIENT_CREDITS"}:
        return BotErrorInfo(
            code=ErrorCode.PAYMENT,
            user_message="Недостаточно кредитов для выполнения запроса.",
            debug_reason=f"fail_code={fc} fail_msg={fm}",
        )
    if fc in {"SERVER_ERROR", "INTERNAL_ERROR", "UNKNOWN_ERROR"}:
        return BotErrorInfo(
            code=ErrorCode.UPSTREAM,
            user_message="Ошибка сервиса генерации. Попробуйте позже.",
            debug_reason=f"fail_code={fc} fail_msg={fm}",
        )

    # Fallback
    if fm:
        return BotErrorInfo(
            code=ErrorCode.UPSTREAM,
            user_message="Не удалось выполнить запрос. Попробуйте позже.",
            debug_reason=f"fail_code={fc or '-'} fail_msg={fm}",
        )
    if fc:
        return BotErrorInfo(
            code=ErrorCode.UPSTREAM,
            user_message="Не удалось выполнить запрос. Попробуйте позже.",
            debug_reason=f"fail_code={fc}",
        )

    return BotErrorInfo(
        code=ErrorCode.UPSTREAM,
        user_message="Не удалось выполнить запрос. Попробуйте позже.",
        debug_reason="fail_code=- fail_msg=-",
    )


def classify_exception(exc: Exception) -> BotErrorInfo:
    name = exc.__class__.__name__
    msg = str(exc)[:500]

    # Network-ish
    if name in {"TimeoutError", "ReadTimeout", "ConnectTimeout"}:
        return BotErrorInfo(ErrorCode.TIMEOUT, "Превышено время ожидания. Попробуйте ещё раз.", f"{name}: {msg}")
    if name in {"ClientConnectorError", "ConnectionError"}:
        return BotErrorInfo(ErrorCode.UPSTREAM, "Сервис временно недоступен. Попробуйте позже.", f"{name}: {msg}")

    return BotErrorInfo(ErrorCode.INTERNAL, "Внутренняя ошибка. Попробуйте ещё раз.", f"{name}: {msg}")
