"""
PostgreSQL storage implementation with async connection testing.
"""
import asyncio
import logging
from typing import Optional
import os

logger = logging.getLogger(__name__)

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False
    try:
        import psycopg
        from psycopg.rows import dict_row
        HAS_PSYCOPG = True
    except ImportError:
        HAS_PSYCOPG = False


async def async_check_pg(dsn: str, timeout: float = 5.0) -> bool:
    """
    Async check PostgreSQL connection.
    Does NOT use asyncio.run() or run_until_complete() - safe for nested event loops.
    
    Args:
        dsn: PostgreSQL connection string
        timeout: Connection timeout in seconds
        
    Returns:
        True if connection successful, False otherwise
    """
    if not dsn:
        return False
        
    try:
        if HAS_ASYNCPG:
            conn = await asyncio.wait_for(
                asyncpg.connect(dsn),
                timeout=timeout
            )
            await conn.close()
            return True
        elif HAS_PSYCOPG:
            conn = await asyncio.wait_for(
                psycopg.AsyncConnection.connect(dsn),
                timeout=timeout
            )
            await conn.close()
            return True
        else:
            logger.error("No async PostgreSQL driver available (asyncpg or psycopg)")
            return False
    except asyncio.TimeoutError:
        logger.warning(f"PostgreSQL connection test timed out after {timeout}s")
        return False
    except Exception as e:
        logger.warning(f"PostgreSQL connection test failed: {e}")
        return False


def sync_check_pg(dsn: str, timeout: float = 5.0) -> bool:
    """
    Synchronous check PostgreSQL connection (for CLI tools only).
    Uses asyncio.run() - should NOT be called from async context.
    
    Args:
        dsn: PostgreSQL connection string
        timeout: Connection timeout in seconds
        
    Returns:
        True if connection successful, False otherwise
    """
    if not dsn:
        return False
        
    try:
        return asyncio.run(async_check_pg(dsn, timeout))
    except RuntimeError as e:
        if "asyncio.run() cannot be called from a running event loop" in str(e):
            logger.error("sync_check_pg() called from async context. Use async_check_pg() instead.")
            raise
        logger.warning(f"PostgreSQL connection test failed: {e}")
        return False
    except Exception as e:
        logger.warning(f"PostgreSQL connection test failed: {e}")
        return False


class PGStorage:
    """PostgreSQL storage backend."""
    
    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or os.getenv("DATABASE_URL")
        self._pool = None
        self._connection = None
        
    async def initialize(self) -> bool:
        """Initialize PostgreSQL connection pool."""
        if not self.dsn:
            raise ValueError("DATABASE_URL not set - storage requires database URL")
            
        # Test connection first
        if not await async_check_pg(self.dsn):
            raise ConnectionError("PostgreSQL connection test failed")
            
        if HAS_ASYNCPG:
            # Create connection pool with production-ready sizing
            # min_size=2: minimum connections always available
            # max_size=10: maximum concurrent connections
            self._pool = await asyncpg.create_pool(
                self.dsn,
                min_size=2,
                max_size=10,
                command_timeout=60.0
            )
            logger.info("PostgreSQL connection pool created (min=2, max=10)")
            return True
        elif HAS_PSYCOPG:
            self._connection = await psycopg.AsyncConnection.connect(self.dsn)
            logger.info("PostgreSQL connection created")
            return True
        else:
            raise ImportError("No async PostgreSQL driver available (asyncpg or psycopg required)")
    
    async def close(self):
        """Close PostgreSQL connections."""
        if self._pool:
            await self._pool.close()
            self._pool = None
        if self._connection:
            await self._connection.close()
            self._connection = None


# Alias for compatibility
PostgresStorage = PGStorage

