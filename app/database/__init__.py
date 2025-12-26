"""Database layer for Telegram bot."""
try:
    import asyncpg  # type: ignore
except ImportError:  # pragma: no cover
    asyncpg = None
import os
from .schema import apply_schema, verify_schema


async def init_db():
    """
    Initialize database: apply schema if needed.
    
    Returns:
        bool: True if successful
    """
    database_url = os.getenv('DATABASE_URL')
    if asyncpg is None:
        raise RuntimeError("asyncpg is not installed. Install dependencies or use STORAGE_MODE=json")
    if not database_url:
        raise ValueError("DATABASE_URL not set")
    
    conn = await asyncpg.connect(database_url)
    try:
        # Apply schema (idempotent)
        await apply_schema(conn)
        
        # Verify
        is_valid = await verify_schema(conn)
        if not is_valid:
            raise RuntimeError("Database schema verification failed")
        
        return True
    finally:
        await conn.close()


__all__ = ['init_db']
