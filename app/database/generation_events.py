"""Generation events tracking for diagnostics and admin."""
import time
from typing import Optional, List, Dict, Any
import logging
from app.logging.policy import log_expected, log_crash

logger = logging.getLogger(__name__)


# Feature flag: disable if tables don't exist
_LOGGING_ENABLED = True


async def log_generation_event(
    db_service,
    user_id: int,
    model_id: str,
    status: str,
    chat_id: Optional[int] = None,
    category: Optional[str] = None,
    is_free_applied: bool = False,
    price_rub: float = 0.0,
    request_id: Optional[str] = None,
    task_id: Optional[str] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> Optional[int]:
    """
    Log generation event to database for diagnostics.
    
    BEST-EFFORT: Never raises exceptions. Returns None on failure.
    
    Args:
        status: 'started', 'success', 'failed', 'timeout'
        error_message: Sanitized error message (no secrets, max 500 chars)
    
    Returns:
        Event ID or None if logging failed
    """
    global _LOGGING_ENABLED
    
    if not _LOGGING_ENABLED:
        return None
        
    if not db_service:
        logger.warning("log_generation_event: no db_service, skipping")
        return None
        
    try:
        # Ensure user exists FIRST (prevent FK violations)
        from app.database.users import ensure_user_exists
        await ensure_user_exists(db_service, user_id)
        
        # Sanitize error message (no secrets, truncate)
        if error_message:
            error_message = str(error_message)[:500]
        
        event_id = await db_service.fetchval(
            """
            INSERT INTO generation_events (
                user_id, chat_id, model_id, category, status,
                is_free_applied, price_rub, request_id, task_id,
                error_code, error_message, duration_ms
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id
            """,
            user_id, chat_id, model_id, category, status,
            is_free_applied, price_rub, request_id, task_id,
            error_code, error_message, duration_ms,
        )
        
        return event_id
        
    except Exception as e:
        # Check if tables don't exist (UndefinedTableError)
        error_str = str(e).lower()
        if 'generation_events' in error_str and ('does not exist' in error_str or 'undefined' in error_str):
            _LOGGING_ENABLED = False
            log_expected(logger, e, "generation_events table missing")
            return None
        
        # Best-effort logging: don't crash generation if logging fails
        log_expected(logger, e, "event logging failed (non-critical)")
        return None


async def get_recent_failures(
    db_service,
    limit: int = 20,
    user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Get recent failed generation events for admin diagnostics.
    
    Args:
        limit: Max number of events to return
        user_id: Filter by user (optional)
    
    Returns:
        List of event dicts
    """
    try:
        where_clause = "WHERE status IN ('failed', 'timeout')"
        params = [limit]
        
        if user_id:
            where_clause += " AND user_id = $2"
            params.insert(0, user_id)
        
        rows = await db_service.fetch(
            f"""
            SELECT 
                id, created_at, user_id, chat_id, model_id, category,
                status, is_free_applied, price_rub, request_id, task_id,
                error_code, error_message, duration_ms
            FROM generation_events
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${1 if not user_id else 2}
            """,
            *params
        )
        
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to fetch recent failures: {e}", exc_info=True)
        return []


async def get_user_stats(
    db_service,
    user_id: int,
    hours: int = 24,
) -> Dict[str, Any]:
    """
    Get user generation stats for diagnostics.
    
    Returns:
        {
            'total': int,
            'success': int,
            'failed': int,
            'free_used': int,
            'total_cost': float
        }
    """
    try:
        row = await db_service.fetchrow(
            """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                SUM(CASE WHEN status = 'failed' OR status = 'timeout' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN is_free_applied THEN 1 ELSE 0 END) as free_used,
                SUM(CASE WHEN status = 'success' AND NOT is_free_applied THEN price_rub ELSE 0 END) as total_cost
            FROM generation_events
            WHERE user_id = $1
              AND created_at > NOW() - INTERVAL '1 hour' * $2
            """,
            user_id, hours
        )
        
        return {
            'total': row['total'] or 0,
            'success': row['success'] or 0,
            'failed': row['failed'] or 0,
            'free_used': row['free_used'] or 0,
            'total_cost': float(row['total_cost'] or 0),
        }
    except Exception as e:
        logger.error(f"Failed to fetch user stats: {e}", exc_info=True)
        return {'total': 0, 'success': 0, 'failed': 0, 'free_used': 0, 'total_cost': 0.0}
