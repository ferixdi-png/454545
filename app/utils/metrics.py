"""
Metrics and observability system for production monitoring.

MASTER PROMPT compliance:
- Track performance metrics
- Monitor system health
- Detect issues early
- Enable data-driven decisions
"""

import time
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
import asyncio


@dataclass
class MetricValue:
    """Single metric value with timestamp."""
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    labels: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """
    Collect and track application metrics.
    
    Thread-safe metrics collection for async environments.
    """
    
    def __init__(self):
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, list] = {}
        self._lock = asyncio.Lock()
    
    async def increment(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        async with self._lock:
            key = self._make_key(name, labels)
            self._counters[key] = self._counters.get(key, 0) + value
    
    async def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric."""
        async with self._lock:
            key = self._make_key(name, labels)
            self._gauges[key] = value
    
    async def observe(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Observe a value for histogram metric."""
        async with self._lock:
            key = self._make_key(name, labels)
            if key not in self._histograms:
                self._histograms[key] = []
            self._histograms[key].append(value)
            
            # Keep only last 1000 values
            if len(self._histograms[key]) > 1000:
                self._histograms[key] = self._histograms[key][-1000:]
    
    async def get_metrics(self) -> Dict[str, Dict]:
        """Get all metrics snapshot."""
        async with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    k: {
                        "count": len(v),
                        "sum": sum(v),
                        "avg": sum(v) / len(v) if v else 0,
                        "min": min(v) if v else 0,
                        "max": max(v) if v else 0,
                    }
                    for k, v in self._histograms.items()
                }
            }
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Create metric key with labels."""
        if not labels:
            return name
        
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


class Timer:
    """Context manager for timing operations."""
    
    def __init__(self, collector: MetricsCollector, metric_name: str, labels: Optional[Dict[str, str]] = None):
        self.collector = collector
        self.metric_name = metric_name
        self.labels = labels
        self.start_time: Optional[float] = None
    
    async def __aenter__(self):
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            await self.collector.observe(
                f"{self.metric_name}_duration_seconds",
                duration,
                self.labels
            )
            
            # Also track success/failure
            status = "error" if exc_type else "success"
            labels_with_status = {**(self.labels or {}), "status": status}
            await self.collector.increment(
                f"{self.metric_name}_total",
                labels=labels_with_status
            )


# Global metrics collector
_metrics = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance."""
    return _metrics


# Standard metrics that should be tracked

async def track_generation(model_id: str, success: bool, duration: float, price_rub: float):
    """Track generation metrics."""
    labels = {"model_id": model_id, "status": "success" if success else "error"}
    
    await _metrics.increment("generations_total", labels=labels)
    await _metrics.observe("generation_duration_seconds", duration, {"model_id": model_id})
    
    if success:
        await _metrics.observe("generation_price_rub", price_rub, {"model_id": model_id})


async def track_payment(user_id: int, amount_rub: float, payment_type: str):
    """Track payment metrics."""
    labels = {"payment_type": payment_type}
    
    await _metrics.increment("payments_total", labels=labels)
    await _metrics.observe("payment_amount_rub", amount_rub, labels=labels)


async def track_refund(user_id: int, amount_rub: float, reason: str):
    """Track refund metrics."""
    labels = {"reason": reason}
    
    await _metrics.increment("refunds_total", labels=labels)
    await _metrics.observe("refund_amount_rub", amount_rub, labels=labels)


async def track_error(error_type: str, handler: str):
    """Track error metrics."""
    labels = {"error_type": error_type, "handler": handler}
    
    await _metrics.increment("errors_total", labels=labels)


async def track_user_activity(user_id: int, action: str):
    """Track user activity."""
    labels = {"action": action}
    
    await _metrics.increment("user_actions_total", labels=labels)


async def track_database_query(query_type: str, duration: float, success: bool):
    """Track database query metrics."""
    labels = {"query_type": query_type, "status": "success" if success else "error"}
    
    await _metrics.increment("db_queries_total", labels=labels)
    await _metrics.observe("db_query_duration_seconds", duration, {"query_type": query_type})


async def track_api_call(api: str, endpoint: str, duration: float, status_code: int):
    """Track external API call metrics."""
    labels = {
        "api": api,
        "endpoint": endpoint,
        "status_code": str(status_code)
    }
    
    await _metrics.increment("api_calls_total", labels=labels)
    await _metrics.observe("api_call_duration_seconds", duration, {"api": api, "endpoint": endpoint})


async def set_active_users(count: int):
    """Set active users gauge."""
    await _metrics.set_gauge("active_users", count)


async def set_pool_connections(available: int, used: int):
    """Set database pool connection metrics."""
    await _metrics.set_gauge("db_pool_available", available)
    await _metrics.set_gauge("db_pool_used", used)


# System metrics for monitoring dashboard
async def get_system_metrics(db_service) -> Dict[str, any]:
    """
    Collect comprehensive system metrics for monitoring.
    
    Returns:
        Dict with metrics data including database stats, generation stats, error rates
    """
    from datetime import timedelta
    
    metrics = {
        "timestamp": datetime.utcnow().isoformat(),
        "database": {},
        "generation": {},
        "errors": {},
        "models": {}
    }
    
    try:
        async with db_service.pool.acquire() as conn:
            # Database stats
            processed_count = await conn.fetchval("SELECT COUNT(*) FROM processed_updates")
            metrics["database"]["processed_updates_count"] = processed_count
            
            oldest_update = await conn.fetchval(
                "SELECT MIN(processed_at) FROM processed_updates"
            )
            metrics["database"]["oldest_update"] = oldest_update.isoformat() if oldest_update else None
            
            # Generation stats (last 24h)
            day_ago = datetime.utcnow() - timedelta(days=1)
            
            total_gens = await conn.fetchval("""
                SELECT COUNT(*) FROM generation_events
                WHERE created_at > $1
            """, day_ago)
            metrics["generation"]["last_24h_total"] = total_gens
            
            success = await conn.fetchval("""
                SELECT COUNT(*) FROM generation_events
                WHERE created_at > $1 AND status = 'success'
            """, day_ago)
            metrics["generation"]["last_24h_success"] = success
            
            failed = await conn.fetchval("""
                SELECT COUNT(*) FROM generation_events
                WHERE created_at > $1 AND status = 'failed'
            """, day_ago)
            metrics["generation"]["last_24h_failed"] = failed
            
            # Error rate
            if total_gens > 0:
                error_rate = (failed / total_gens) * 100
                metrics["errors"]["error_rate_24h_percent"] = round(error_rate, 2)
            else:
                metrics["errors"]["error_rate_24h_percent"] = 0.0
            
            # Top errors
            top_errors = await conn.fetch("""
                SELECT error_code, COUNT(*) as count
                FROM generation_events
                WHERE created_at > $1 AND status = 'failed' AND error_code IS NOT NULL
                GROUP BY error_code
                ORDER BY count DESC
                LIMIT 5
            """, day_ago)
            
            metrics["errors"]["top_errors"] = [
                {"error_code": row['error_code'], "count": row['count']}
                for row in top_errors
            ]
            
            # Top models
            top_models = await conn.fetch("""
                SELECT model_id, COUNT(*) as count
                FROM generation_events
                WHERE created_at > $1
                GROUP BY model_id
                ORDER BY count DESC
                LIMIT 5
            """, day_ago)
            
            metrics["models"]["top_5_last_24h"] = [
                {"model_id": row['model_id'], "count": row['count']}
                for row in top_models
            ]
            
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to collect metrics: {e}", exc_info=True)
        metrics["error"] = str(e)
    
    return metrics


async def get_health_status(db_service) -> Dict[str, any]:
    """
    Quick health check for readiness probes.
    
    Returns:
        Dict with health status (status: healthy/unhealthy, checks)
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    # Check database
    try:
        async with db_service.pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        health["checks"]["database"] = "ok"
    except Exception as e:
        health["checks"]["database"] = f"error: {e}"
        health["status"] = "unhealthy"
    
    return health
