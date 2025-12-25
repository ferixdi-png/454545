"""
Free Model Manager - управление бесплатными моделями и лимитами.

Концепция:
- Бесплатные модели НЕ списывают баланс
- Используются для onboarding / demo / вовлечения
- Имеют лимиты (daily, hourly)
- Логируется каждое использование
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from decimal import Decimal

logger = logging.getLogger(__name__)


class FreeModelManager:
    """Manager for free models with usage limits."""
    
    def __init__(self, db_service):
        self.db_service = db_service
    
    async def is_model_free(self, model_id: str) -> bool:
        """Check if model is free."""
        async with self.db_service.get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT enabled FROM free_models WHERE model_id = $1",
                model_id
            )
            return row is not None and row['enabled'] if row else False
    
    async def get_free_model_config(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get free model configuration."""
        async with self.db_service.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT model_id, enabled, daily_limit, hourly_limit, meta
                FROM free_models
                WHERE model_id = $1 AND enabled = TRUE
                """,
                model_id
            )
            if not row:
                return None
            
            return {
                "model_id": row['model_id'],
                "enabled": row['enabled'],
                "daily_limit": row['daily_limit'],
                "hourly_limit": row['hourly_limit'],
                "meta": row['meta']
            }
    
    async def check_limits(self, user_id: int, model_id: str) -> Dict[str, Any]:
        """
        Check if user can use free model.
        
        Returns:
            {
                "allowed": bool,
                "reason": str,
                "daily_used": int,
                "daily_limit": int,
                "hourly_used": int,
                "hourly_limit": int
            }
        """
        config = await self.get_free_model_config(model_id)
        
        if not config:
            return {
                "allowed": False,
                "reason": "not_free",
                "daily_used": 0,
                "daily_limit": 0,
                "hourly_used": 0,
                "hourly_limit": 0
            }
        
        # Count daily usage
        now = datetime.utcnow()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        
        async with self.db_service.get_connection() as conn:
            # Daily count
            daily_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM free_usage
                WHERE user_id = $1 AND model_id = $2 AND created_at >= $3
                """,
                user_id, model_id, day_start
            )
            
            # Hourly count
            hourly_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM free_usage
                WHERE user_id = $1 AND model_id = $2 AND created_at >= $3
                """,
                user_id, model_id, hour_start
            )
        
        daily_limit = config['daily_limit']
        hourly_limit = config.get('hourly_limit') or 999
        
        # Check limits
        if daily_count >= daily_limit:
            return {
                "allowed": False,
                "reason": "daily_limit_exceeded",
                "daily_used": daily_count,
                "daily_limit": daily_limit,
                "hourly_used": hourly_count,
                "hourly_limit": hourly_limit
            }
        
        if hourly_count >= hourly_limit:
            return {
                "allowed": False,
                "reason": "hourly_limit_exceeded",
                "daily_used": daily_count,
                "daily_limit": daily_limit,
                "hourly_used": hourly_count,
                "hourly_limit": hourly_limit
            }
        
        return {
            "allowed": True,
            "reason": "ok",
            "daily_used": daily_count,
            "daily_limit": daily_limit,
            "hourly_used": hourly_count,
            "hourly_limit": hourly_limit
        }
    
    async def log_usage(self, user_id: int, model_id: str, job_id: Optional[str] = None):
        """Log free model usage."""
        async with self.db_service.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO free_usage (user_id, model_id, job_id, created_at)
                VALUES ($1, $2, $3, NOW())
                """,
                user_id, model_id, job_id
            )
        
        logger.info(f"Free usage logged: user={user_id}, model={model_id}, job={job_id}")
    
    async def get_daily_usage(self, user_id: int, model_id: str) -> int:
        """Get daily usage count for a user and model."""
        from datetime import datetime, timezone, timedelta
        
        day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        async with self.db_service.get_connection() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM free_usage
                WHERE user_id = $1 AND model_id = $2 AND created_at >= $3
                """,
                user_id, model_id, day_start
            )
        
        return count or 0
    
    async def get_hourly_usage(self, user_id: int, model_id: str) -> int:
        """Get hourly usage count for a user and model."""
        from datetime import datetime, timezone, timedelta
        
        hour_start = datetime.now(timezone.utc) - timedelta(hours=1)
        
        async with self.db_service.get_connection() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM free_usage
                WHERE user_id = $1 AND model_id = $2 AND created_at >= $3
                """,
                user_id, model_id, hour_start
            )
        
        return count or 0
    async def get_all_free_models(self) -> List[Dict[str, Any]]:
        """Get all enabled free models."""
        async with self.db_service.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT model_id, daily_limit, hourly_limit, meta
                FROM free_models
                WHERE enabled = TRUE
                ORDER BY model_id
                """
            )
            
            return [
                {
                    "model_id": row['model_id'],
                    "daily_limit": row['daily_limit'],
                    "hourly_limit": row['hourly_limit'],
                    "meta": row['meta']
                }
                for row in rows
            ]
    
    async def add_free_model(
        self,
        model_id: str,
        daily_limit: int = 5,
        hourly_limit: int = 2,
        meta: Optional[Dict] = None
    ):
        """Add or update free model configuration."""
        async with self.db_service.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO free_models (model_id, enabled, daily_limit, hourly_limit, meta, updated_at)
                VALUES ($1, TRUE, $2, $3, $4, NOW())
                ON CONFLICT (model_id) DO UPDATE SET
                    enabled = TRUE,
                    daily_limit = EXCLUDED.daily_limit,
                    hourly_limit = EXCLUDED.hourly_limit,
                    meta = EXCLUDED.meta,
                    updated_at = NOW()
                """,
                model_id, daily_limit, hourly_limit, json.dumps(meta or {})
            )
        
        logger.info(f"Free model configured: {model_id} (daily={daily_limit}, hourly={hourly_limit})")
    
    async def remove_free_model(self, model_id: str):
        """Disable free model (soft delete)."""
        async with self.db_service.get_connection() as conn:
            await conn.execute(
                """
                UPDATE free_models
                SET enabled = FALSE, updated_at = NOW()
                WHERE model_id = $1
                """,
                model_id
            )
        
        logger.info(f"Free model disabled: {model_id}")
    
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user's free usage statistics."""
        now = datetime.utcnow()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        async with self.db_service.get_connection() as conn:
            # Total free uses today
            total_today = await conn.fetchval(
                """
                SELECT COUNT(*) FROM free_usage
                WHERE user_id = $1 AND created_at >= $2
                """,
                user_id, day_start
            )
            
            # Total free uses all time
            total_all_time = await conn.fetchval(
                "SELECT COUNT(*) FROM free_usage WHERE user_id = $1",
                user_id
            )
            
            # By model
            by_model = await conn.fetch(
                """
                SELECT model_id, COUNT(*) as count
                FROM free_usage
                WHERE user_id = $1
                GROUP BY model_id
                ORDER BY count DESC
                """,
                user_id
            )
        
        return {
            "total_today": total_today,
            "total_all_time": total_all_time,
            "by_model": [
                {"model_id": row['model_id'], "count": row['count']}
                for row in by_model
            ]
        }


__all__ = ["FreeModelManager"]
