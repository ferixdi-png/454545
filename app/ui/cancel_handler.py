"""Cancel handler: graceful cancellation with lock release."""
import logging
from typing import Optional, Dict
from datetime import datetime
import asyncio

log = logging.getLogger(__name__)

# In-memory cancel flags
_cancel_flags: Dict[str, bool] = {}  # task_id -> cancelled


def set_cancel_flag(task_id: str):
    """Set cancel flag for task.
    
    Args:
        task_id: Task/job ID to cancel
    """
    _cancel_flags[task_id] = True
    log.info(f"Cancel flag set for task: {task_id}")


def is_cancelled(task_id: str) -> bool:
    """Check if task is cancelled.
    
    Args:
        task_id: Task/job ID
    
    Returns:
        True if cancelled
    """
    return _cancel_flags.get(task_id, False)


def clear_cancel_flag(task_id: str):
    """Clear cancel flag after processing.
    
    Args:
        task_id: Task/job ID
    """
    if task_id in _cancel_flags:
        del _cancel_flags[task_id]
        log.info(f"Cancel flag cleared for task: {task_id}")


async def cancel_task(
    task_id: str,
    user_id: int,
    release_lock_func=None,
    finalize_idempotency_func=None,
) -> bool:
    """Cancel task and cleanup resources.
    
    Args:
        task_id: Task/job ID to cancel
        user_id: User ID
        release_lock_func: Optional function to release job lock
        finalize_idempotency_func: Optional function to finalize idempotency
    
    Returns:
        True if cancelled successfully
    """
    log.info(f"Cancelling task {task_id} for user {user_id}")
    
    # Set cancel flag (stops polling)
    set_cancel_flag(task_id)
    
    # Release job lock if function provided
    if release_lock_func:
        try:
            await release_lock_func(user_id)
            log.info(f"Released job lock for user {user_id}")
        except Exception as e:
            log.error(f"Failed to release lock: {e}")
    
    # Finalize idempotency as cancelled
    if finalize_idempotency_func:
        try:
            await finalize_idempotency_func(task_id, status="cancelled")
            log.info(f"Finalized idempotency for task {task_id}")
        except Exception as e:
            log.error(f"Failed to finalize idempotency: {e}")
    
    # Wait a bit for polling to notice
    await asyncio.sleep(0.5)
    
    # Clear flag
    clear_cancel_flag(task_id)
    
    return True


async def handle_timeout(
    task_id: str,
    user_id: int,
    elapsed_seconds: int,
) -> Dict[str, any]:
    """Handle timeout gracefully.
    
    Args:
        task_id: Task/job ID
        user_id: User ID
        elapsed_seconds: Seconds elapsed
    
    Returns:
        Dict with status and suggested action
    """
    log.warning(f"Task {task_id} timed out after {elapsed_seconds}s")
    
    # Decide action based on elapsed time
    if elapsed_seconds < 120:
        # Less than 2 minutes - suggest waiting
        return {
            "status": "timeout_short",
            "action": "wait_more",
            "message": "Генерация идёт дольше обычного. Подожди ещё немного?",
        }
    elif elapsed_seconds < 300:
        # 2-5 minutes - suggest retry
        return {
            "status": "timeout_medium",
            "action": "retry",
            "message": "Слишком долго. Рекомендую повторить запрос.",
        }
    else:
        # 5+ minutes - definitely failed
        return {
            "status": "timeout_long",
            "action": "failed",
            "message": "Похоже, запрос завис. Попробуй другую модель или упрости промпт.",
        }


def get_cancel_confirmation_message() -> str:
    """Get cancellation confirmation message.
    
    Returns:
        Confirmation message text
    """
    return "✅ Отменил. Что дальше?"


def should_allow_cancel(elapsed_seconds: int) -> bool:
    """Check if cancellation should be allowed.
    
    Args:
        elapsed_seconds: Seconds since task started
    
    Returns:
        True if can cancel
    """
    # Allow cancel after 5 seconds (avoid accidental instant cancels)
    return elapsed_seconds >= 5
