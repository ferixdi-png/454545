"""
Admin permissions and access control.
"""
import logging
import os
from functools import wraps
from typing import Optional, List

logger = logging.getLogger(__name__)


def get_admin_ids() -> List[int]:
    """Get admin user IDs from ENV."""
    admin_ids_str = os.getenv("ADMIN_IDS", "")
    if not admin_ids_str:
        return []
    
    try:
        return [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]
    except (ValueError, AttributeError) as e:
        # MASTER PROMPT: No bare except - specific exception types
        logger.error(f"Failed to parse ADMIN_IDS from ENV: {e}")
        return []


async def is_admin(user_id: int, db_service=None) -> bool:
    """
    Check if user is admin.
    
    Priority:
    1. Check ADMIN_IDS env variable
    2. Check role in database (if db_service provided)
    """
    # Check ENV
    admin_ids = get_admin_ids()
    if user_id in admin_ids:
        return True
    
    # Check database
    if db_service:
        try:
            async with db_service.get_connection() as conn:
                role = await conn.fetchval(
                    "SELECT role FROM users WHERE user_id = $1",
                    user_id
                )
                return role == 'admin'
        except Exception as e:
            logger.error(f"Failed to check admin status in DB: {e}")
    
    return False


def require_admin(db_service_param: str = "db_service"):
    """
    Decorator to require admin access for handler.
    
    Usage:
        @require_admin()
        async def admin_handler(callback, state, db_service):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find user_id (from Message or CallbackQuery)
            user_id = None
            for arg in args:
                if hasattr(arg, 'from_user'):
                    user_id = arg.from_user.id
                    break
            
            if not user_id:
                logger.error("Cannot determine user_id for admin check")
                return
            
            # Get db_service
            db_service = kwargs.get(db_service_param)
            
            # Check admin status
            if not await is_admin(user_id, db_service):
                logger.warning(f"Non-admin user {user_id} tried to access admin function")
                
                # Try to send message
                for arg in args:
                    if hasattr(arg, 'answer'):
                        await arg.answer("⛔️ Доступ запрещён", show_alert=True)
                        break
                
                return
            
            # Execute handler
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


__all__ = ["is_admin", "require_admin", "get_admin_ids"]
