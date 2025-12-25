"""
PostgreSQL advisory lock with TTL and stale detection for singleton instance management.

Features:
- Advisory lock via PostgreSQL
- TTL-based stale detection (60s)
- Automatic heartbeat every 20s
- Graceful release on shutdown
- Supports asyncpg and psycopg
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

try:
    import psycopg
    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False


# Lock TTL in seconds (aggressive for zero-downtime rolling deployment)
LOCK_TTL = 10
HEARTBEAT_INTERVAL = 3  # Heartbeat more frequently to avoid false stale detection


class SingletonLock:
    """
    PostgreSQL advisory lock with TTL for ensuring only one active instance.
    """
    
    def __init__(self, dsn: Optional[str] = None, instance_name: str = "bot-instance"):
        self.dsn = dsn
        self.instance_name = instance_name
        self._connection = None
        self._lock_id = 12345
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._acquired = False
    
    async def _ensure_heartbeat_table(self):
        """Create heartbeat table if not exists."""
        if not self._connection:
            return
        
        try:
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS singleton_heartbeat (
                    lock_id INTEGER PRIMARY KEY,
                    instance_name TEXT NOT NULL,
                    last_heartbeat TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
        except Exception as e:
            logger.warning(f"Could not create heartbeat table: {e}")
    
    async def _update_heartbeat(self):
        """Update heartbeat timestamp."""
        if not self._connection:
            return
        
        try:
            await self._connection.execute("""
                INSERT INTO singleton_heartbeat (lock_id, instance_name, last_heartbeat)
                VALUES ($1, $2, NOW())
                ON CONFLICT (lock_id) DO UPDATE
                SET instance_name = EXCLUDED.instance_name,
                    last_heartbeat = NOW()
            """, self._lock_id, self.instance_name)
        except Exception as e:
            logger.warning(f"Could not update heartbeat: {e}")
    
    async def _cleanup_stale_locks(self):
        """
        Release stale locks (no heartbeat for LOCK_TTL seconds).
        Also forcefully unlock PostgreSQL advisory lock if stale.
        """
        if not self._connection:
            return
        
        try:
            # Check if there's a stale lock
            result = await self._connection.fetchrow(f"""
                SELECT instance_name, last_heartbeat
                FROM singleton_heartbeat
                WHERE lock_id = $1
                AND last_heartbeat < NOW() - INTERVAL '{LOCK_TTL} seconds'
            """, self._lock_id)
            
            if result:
                logger.warning(f"🔓 Found STALE lock from {result['instance_name']} "
                             f"(last heartbeat: {result['last_heartbeat']}) - force unlocking!")
                
                # Force release PostgreSQL advisory lock
                if HAS_ASYNCPG:
                    unlocked = await self._connection.fetchval(
                        "SELECT pg_advisory_unlock_all()"
                    )
                    logger.info(f"Advisory lock force released: {unlocked}")
                else:  # psycopg
                    async with self._connection.cursor() as cur:
                        await cur.execute("SELECT pg_advisory_unlock_all()")
                        result_unlock = await cur.fetchone()
                        logger.info(f"Advisory lock force released: {result_unlock[0] if result_unlock else False}")
                
                # Delete stale heartbeat record
                await self._connection.execute(
                    "DELETE FROM singleton_heartbeat WHERE lock_id = $1",
                    self._lock_id
                )
                logger.info("✅ Stale lock cleaned up - ready for new acquisition")
        except Exception as e:
            logger.warning(f"Could not check stale locks: {e}")
    
    async def _heartbeat_loop(self):
        """Background task to update heartbeat."""
        while self._acquired:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                if self._acquired:
                    await self._update_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
    
    async def acquire(self, timeout: float = 5.0) -> bool:
        """
        Acquire singleton lock with stale detection.
        
        Returns:
            True if lock acquired, False otherwise
        """
        if not self.dsn:
            logger.warning("No database URL - running without singleton lock")
            return False
        
        if not HAS_ASYNCPG and not HAS_PSYCOPG:
            logger.warning("No PostgreSQL driver available - running without lock")
            return False
        
        try:
            if HAS_ASYNCPG:
                self._connection = await asyncio.wait_for(
                    asyncpg.connect(self.dsn),
                    timeout=timeout
                )
            elif HAS_PSYCOPG:
                self._connection = await asyncio.wait_for(
                    psycopg.AsyncConnection.connect(self.dsn),
                    timeout=timeout
                )
            else:
                return False
            
            # Create heartbeat table
            await self._ensure_heartbeat_table()
            
            # Cleanup stale locks
            await self._cleanup_stale_locks()
            
            # Try to acquire advisory lock
            if HAS_ASYNCPG:
                acquired = await self._connection.fetchval(
                    "SELECT pg_try_advisory_lock($1)",
                    self._lock_id
                )
            else:  # psycopg
                async with self._connection.cursor() as cur:
                    await cur.execute("SELECT pg_try_advisory_lock(%s)", (self._lock_id,))
                    result = await cur.fetchone()
                    acquired = result[0] if result else False
            
            if acquired:
                self._acquired = True
                await self._update_heartbeat()
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                logger.info(f"✅ Singleton lock acquired by {self.instance_name}")
                return True
            else:
                logger.warning(f"⚠️ Singleton lock NOT acquired - another instance is active")
                await self._connection.close()
                self._connection = None
                return False
        
        except asyncio.TimeoutError:
            logger.error("Timeout acquiring singleton lock")
            return False
        except Exception as e:
            logger.error(f"Error acquiring singleton lock: {e}")
            if self._connection:
                try:
                    await self._connection.close()
                except Exception as close_err:
                    # MASTER PROMPT: No bare except - specific exception type
                    logger.debug(f"Error closing connection during cleanup: {close_err}")
                    pass
                self._connection = None
            return False
    
    async def release(self):
        """Release singleton lock with detailed logging for zero-downtime deployment tracking."""
        if not self._acquired:
            logger.debug("Lock already released or not acquired - skipping release")
            return
        
        logger.info(f"🔓 Starting lock release for {self.instance_name}...")
        self._acquired = False
        
        # Cancel heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
                logger.info("Heartbeat task cancelled successfully")
            except asyncio.CancelledError:
                logger.info("Heartbeat task cancelled (expected)")
            self._heartbeat_task = None
        
        if not self._connection:
            logger.warning("No connection available for lock release")
            return
        
        try:
            # Release advisory lock
            if HAS_ASYNCPG:
                released = await self._connection.fetchval(
                    "SELECT pg_advisory_unlock($1)",
                    self._lock_id
                )
                logger.info(f"Advisory lock released: {released}")
            else:  # psycopg
                async with self._connection.cursor() as cur:
                    await cur.execute("SELECT pg_advisory_unlock(%s)", (self._lock_id,))
                    result = await cur.fetchone()
                    logger.info(f"Advisory lock released: {result[0] if result else False}")
            
            # Remove heartbeat record
            deleted = await self._connection.execute(
                "DELETE FROM singleton_heartbeat WHERE lock_id = $1",
                self._lock_id
            )
            logger.info(f"Heartbeat record removed (rows affected: {deleted})")
            
            logger.info(f"✅ Singleton lock fully released by {self.instance_name} - new instance can acquire")
        except Exception as e:
            logger.error(f"❌ Error releasing lock: {e}", exc_info=True)
        finally:
            try:
                await self._connection.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
            self._connection = None

