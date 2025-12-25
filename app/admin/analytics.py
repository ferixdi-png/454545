"""
Analytics for admin panel.
"""
import logging
from decimal import Decimal
from typing import Dict, List, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class Analytics:
    """Analytics service for admin panel."""
    
    def __init__(self, db_service):
        self.db_service = db_service
    
    async def get_top_models(self, limit: int = 10, period_days: int = 30) -> List[Dict[str, Any]]:
        """Get top models by usage."""
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        
        async with self.db_service.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    model_id,
                    COUNT(*) as total_uses,
                    COUNT(*) FILTER (WHERE status = 'succeeded') as success_count,
                    COUNT(*) FILTER (WHERE status = 'failed') as fail_count,
                    COALESCE(SUM(price_rub) FILTER (WHERE status = 'succeeded'), 0) as revenue
                FROM jobs
                WHERE created_at >= $1
                GROUP BY model_id
                ORDER BY total_uses DESC
                LIMIT $2
                """,
                cutoff, limit
            )
        
        return [
            {
                "model_id": row['model_id'],
                "total_uses": row['total_uses'],
                "success_count": row['success_count'],
                "fail_count": row['fail_count'],
                "revenue": float(row['revenue']),
                "success_rate": (row['success_count'] / row['total_uses'] * 100) if row['total_uses'] > 0 else 0
            }
            for row in rows
        ]
    
    async def get_free_to_paid_conversion(self) -> Dict[str, Any]:
        """
        Get free to paid conversion stats.
        
        Users who:
        1. Used free models
        2. Later used paid models
        """
        async with self.db_service.get_connection() as conn:
            # Total users who used free
            total_free_users = await conn.fetchval(
                "SELECT COUNT(DISTINCT user_id) FROM free_usage"
            ) or 0
            
            # Users who also used paid
            converted_users = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT fu.user_id)
                FROM free_usage fu
                WHERE EXISTS (
                    SELECT 1 FROM jobs j
                    WHERE j.user_id = fu.user_id
                    AND j.status = 'succeeded'
                    AND j.price_rub > 0
                )
                """
            ) or 0
            
            conversion_rate = (converted_users / total_free_users * 100) if total_free_users > 0 else 0
        
        return {
            "total_free_users": total_free_users,
            "converted_users": converted_users,
            "conversion_rate": conversion_rate
        }
    
    async def get_error_stats(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get failed generation stats."""
        async with self.db_service.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    model_id,
                    COUNT(*) as fail_count,
                    MAX(updated_at) as last_fail
                FROM jobs
                WHERE status = 'failed'
                GROUP BY model_id
                ORDER BY fail_count DESC
                LIMIT $1
                """,
                limit
            )
        
        return [
            {
                "model_id": row['model_id'],
                "fail_count": row['fail_count'],
                "last_fail": row['last_fail']
            }
            for row in rows
        ]
    
    async def get_revenue_stats(self, period_days: int = 30) -> Dict[str, Any]:
        """Get revenue statistics."""
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        
        async with self.db_service.get_connection() as conn:
            # Total revenue
            total_revenue = await conn.fetchval(
                """
                SELECT COALESCE(SUM(price_rub), 0)
                FROM jobs
                WHERE status = 'succeeded' AND created_at >= $1
                """,
                cutoff
            ) or Decimal("0.00")
            
            # Total topups
            total_topups = await conn.fetchval(
                """
                SELECT COALESCE(SUM(amount_rub), 0)
                FROM ledger
                WHERE kind = 'topup' AND created_at >= $1
                """,
                cutoff
            ) or Decimal("0.00")
            
            # Total refunds
            total_refunds = await conn.fetchval(
                """
                SELECT COALESCE(SUM(amount_rub), 0)
                FROM ledger
                WHERE kind = 'refund' AND created_at >= $1
                """,
                cutoff
            ) or Decimal("0.00")
            
            # Number of paying users
            paying_users = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT user_id)
                FROM jobs
                WHERE status = 'succeeded' AND price_rub > 0 AND created_at >= $1
                """,
                cutoff
            ) or 0
        
        return {
            "period_days": period_days,
            "total_revenue": float(total_revenue),
            "total_topups": float(total_topups),
            "total_refunds": float(total_refunds),
            "paying_users": paying_users,
            "avg_revenue_per_user": float(total_revenue / paying_users) if paying_users > 0 else 0
        }
    
    async def get_user_activity(self, period_days: int = 7) -> Dict[str, Any]:
        """Get user activity stats."""
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        
        async with self.db_service.get_connection() as conn:
            # New users
            new_users = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE created_at >= $1",
                cutoff
            ) or 0
            
            # Active users (made at least one job)
            active_users = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT user_id)
                FROM jobs
                WHERE created_at >= $1
                """,
                cutoff
            ) or 0
            
            # Total users
            total_users = await conn.fetchval(
                "SELECT COUNT(*) FROM users"
            ) or 0
        
        return {
            "period_days": period_days,
            "new_users": new_users,
            "active_users": active_users,
            "total_users": total_users
        }


__all__ = ["Analytics"]
