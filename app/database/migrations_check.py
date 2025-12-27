"""Database migrations check and graceful degradation.

On first deploy or DB schema mismatch:
- Check if required tables exist
- If missing, disable DB-dependent features gracefully
- Keep core FREE generation working
"""
import logging
from typing import Dict, Any, Optional
from asyncpg import Connection, UndefinedTableError

log = logging.getLogger(__name__)

# Feature flags (global state)
_DB_LOGGING_ENABLED = True
_BALANCE_ENABLED = True
_REFERRAL_ENABLED = True


def is_db_logging_enabled() -> bool:
    """Check if DB event logging is enabled."""
    return _DB_LOGGING_ENABLED


def is_balance_enabled() -> bool:
    """Check if balance/payment system is enabled."""
    return _BALANCE_ENABLED


def is_referral_enabled() -> bool:
    """Check if referral system is enabled."""
    return _REFERRAL_ENABLED


async def check_required_tables(db: Optional[Connection]) -> Dict[str, bool]:
    """Check which tables exist in database.
    
    Returns dict: {table_name: exists}
    """
    if not db:
        return {}
    
    tables_to_check = [
        "users",
        "balances",
        "generation_events",
        "processed_updates",
        "referrals",
        "transactions",
    ]
    
    results = {}
    
    for table in tables_to_check:
        try:
            # Quick existence check
            await db.fetchval(f"SELECT 1 FROM {table} LIMIT 1")
            results[table] = True
        except UndefinedTableError:
            results[table] = False
        except Exception as e:
            # Other errors (permissions, etc) - assume table exists but has issues
            log.warning(f"Table check for {table} failed: {e}")
            results[table] = True  # Conservative: assume exists
    
    return results


async def configure_features_from_schema(db: Optional[Connection]) -> None:
    """Configure feature flags based on DB schema.
    
    Called at startup to disable features if tables missing.
    """
    global _DB_LOGGING_ENABLED, _BALANCE_ENABLED, _REFERRAL_ENABLED
    
    if not db:
        log.warning("⚠️ No database connection - disabling all DB features")
        _DB_LOGGING_ENABLED = False
        _BALANCE_ENABLED = False
        _REFERRAL_ENABLED = False
        return
    
    try:
        tables = await check_required_tables(db)
        
        # DB logging requires: users, generation_events
        if not tables.get("users") or not tables.get("generation_events"):
            log.warning("⚠️ DB logging tables missing - disabling event logging")
            _DB_LOGGING_ENABLED = False
        
        # Balance system requires: users, balances, transactions
        if not tables.get("balances") or not tables.get("transactions"):
            log.warning("⚠️ Balance tables missing - disabling payment system")
            _BALANCE_ENABLED = False
        
        # Referral system requires: referrals table
        if not tables.get("referrals"):
            log.warning("⚠️ Referral table missing - disabling referral system")
            _REFERRAL_ENABLED = False
        
        # Log final state
        log.info(f"Feature flags: logging={_DB_LOGGING_ENABLED}, balance={_BALANCE_ENABLED}, referral={_REFERRAL_ENABLED}")
        
        if not _BALANCE_ENABLED:
            log.info("💡 FREE models will still work without balance system")
    
    except Exception as e:
        log.error(f"Failed to check DB schema: {e}")
        # Conservative: keep features enabled, let them fail individually
