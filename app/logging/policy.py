"""Production logging policy.

RULES:
- ERROR only for actual crashes that break user experience
- WARNING for expected failures (DB logging, optional features)
- INFO for normal operations

This keeps production logs clean and actionable.
"""
import logging
from typing import Any, Optional


def log_expected(logger: logging.Logger, exception: Exception, context: str) -> None:
    """Log expected/recoverable failures as WARNING (not ERROR).
    
    Use for:
    - DB logging failures (generation still succeeds)
    - Analytics failures (non-critical)
    - Optional feature failures
    """
    logger.warning(
        f"⚠️ Expected failure ({context}): {type(exception).__name__}: {exception}",
        exc_info=False  # Don't log full traceback for expected failures
    )


def log_crash(logger: logging.Logger, exception: Exception, context: str, **extra: Any) -> None:
    """Log unexpected crashes as ERROR (user-visible failure).
    
    Use for:
    - Payment failures
    - Generation failures
    - Critical API errors
    """
    extra_str = " | ".join(f"{k}={v}" for k, v in extra.items()) if extra else ""
    logger.error(
        f"❌ CRASH ({context}): {type(exception).__name__}: {exception} | {extra_str}",
        exc_info=True  # Full traceback for debugging
    )


def log_user_error(logger: logging.Logger, error_type: str, user_id: int, details: str) -> None:
    """Log user-facing errors as INFO (not ERROR - user mistake, not system crash).
    
    Use for:
    - Invalid inputs
    - Insufficient balance
    - Rate limiting
    """
    logger.info(
        f"👤 User error ({error_type}) | user_id={user_id} | {details}"
    )


def log_degraded_feature(logger: logging.Logger, feature: str, reason: str) -> None:
    """Log feature degradation as WARNING.
    
    Use when optional feature is disabled due to:
    - Missing DB tables
    - External service unavailable
    - Configuration issue
    """
    logger.warning(
        f"⚠️ Feature degraded: {feature} | reason={reason}"
    )
