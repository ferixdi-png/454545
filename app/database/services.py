"""
Storage layer for database operations (asyncpg-based).

Production-safe with:
- Transactions for atomic operations
- Idempotency for payments
- Connection pooling
- Error handling
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

from app.database.schema import apply_schema, verify_schema

logger = logging.getLogger(__name__)


class DatabaseService:
    """Main database service with connection pooling."""
    
    def __init__(self, dsn: str):
        self.dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        """Initialize connection pool and apply schema."""
        if not HAS_ASYNCPG:
            raise ImportError("asyncpg is required for database operations")
        
        self._pool = await asyncpg.create_pool(
            self.dsn,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        
        # Apply schema
        async with self._pool.acquire() as conn:
            await apply_schema(conn)
            schema_ok = await verify_schema(conn)
            if not schema_ok:
                raise RuntimeError("Schema verification failed")
        
        logger.info("✅ Database initialized with schema")
    
    async def close(self):
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("Database pool closed")
    
    @asynccontextmanager
    async def transaction(self):
        """Context manager for transactions."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                yield conn
    
    async def acquire(self):
        """Acquire connection from pool."""
        return await self._pool.acquire()
    
    async def release(self, conn):
        """Release connection back to pool."""
        await self._pool.release(conn)
    
    @asynccontextmanager
    async def get_connection(self):
        """Get connection context manager (compatible with FreeModelManager, AdminService, etc)."""
        conn = await self._pool.acquire()
        try:
            yield conn
        finally:
            await self._pool.release(conn)


class UserService:
    """User management operations."""
    
    def __init__(self, db: DatabaseService):
        self.db = db
    
    async def get_or_create(self, user_id: int, username: str = None, 
                           first_name: str = None) -> Dict[str, Any]:
        """Get or create user."""
        async with self.db.transaction() as conn:
            # Try to get existing user
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE user_id = $1",
                user_id
            )
            
            if user:
                # Update last_seen
                await conn.execute(
                    "UPDATE users SET last_seen_at = NOW() WHERE user_id = $1",
                    user_id
                )
                return dict(user)
            
            # Create new user + wallet
            user = await conn.fetchrow("""
                INSERT INTO users (user_id, username, first_name)
                VALUES ($1, $2, $3)
                RETURNING *
            """, user_id, username, first_name)
            
            # Create wallet
            await conn.execute("""
                INSERT INTO wallets (user_id, balance_rub, hold_rub)
                VALUES ($1, 0.00, 0.00)
            """, user_id)
            
            logger.info(f"Created new user {user_id}")
            return dict(user)


class WalletService:
    """Wallet and balance operations."""
    
    def __init__(self, db: DatabaseService):
        self.db = db
    
    async def get_balance(self, user_id: int) -> Dict[str, Decimal]:
        """Get wallet balance."""
        async with self.db.transaction() as conn:
            wallet = await conn.fetchrow(
                "SELECT balance_rub, hold_rub FROM wallets WHERE user_id = $1",
                user_id
            )
            if not wallet:
                return {"balance_rub": Decimal("0.00"), "hold_rub": Decimal("0.00")}
            return dict(wallet)
    
    async def get_history(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get ledger history."""
        async with self.db.transaction() as conn:
            rows = await conn.fetch("""
                SELECT kind, amount_rub, status, ref, meta, created_at
                FROM ledger
                WHERE user_id = $1 AND status = 'done'
                ORDER BY created_at DESC
                LIMIT $2
            """, user_id, limit)
            return [dict(row) for row in rows]
    
    async def topup(self, user_id: int, amount_rub: Decimal, 
                   ref: str, meta: Dict = None) -> bool:
        """Add funds (idempotent)."""
        async with self.db.transaction() as conn:
            # Check idempotency
            existing = await conn.fetchval(
                "SELECT id FROM ledger WHERE ref = $1 AND status = 'done'",
                ref
            )
            if existing:
                logger.warning(f"Topup {ref} already processed")
                return False
            
            # Insert ledger entry
            await conn.execute("""
                INSERT INTO ledger (user_id, kind, amount_rub, status, ref, meta)
                VALUES ($1, 'topup', $2, 'done', $3, $4)
            """, user_id, amount_rub, ref, meta or {})
            
            # Update wallet
            await conn.execute("""
                UPDATE wallets
                SET balance_rub = balance_rub + $2,
                    updated_at = NOW()
                WHERE user_id = $1
            """, user_id, amount_rub)
            
            logger.info(f"Topup {user_id}: +{amount_rub} RUB (ref: {ref})")
            return True
    
    async def hold(self, user_id: int, amount_rub: Decimal, 
                  ref: str, meta: Dict = None) -> bool:
        """Hold funds for pending operation."""
        async with self.db.transaction() as conn:
            # Check available balance
            wallet = await conn.fetchrow(
                "SELECT balance_rub FROM wallets WHERE user_id = $1 FOR UPDATE",
                user_id
            )
            if not wallet or wallet['balance_rub'] < amount_rub:
                return False
            
            # Insert ledger
            await conn.execute("""
                INSERT INTO ledger (user_id, kind, amount_rub, status, ref, meta)
                VALUES ($1, 'hold', $2, 'done', $3, $4)
            """, user_id, amount_rub, ref, meta or {})
            
            # Move balance to hold
            await conn.execute("""
                UPDATE wallets
                SET balance_rub = balance_rub - $2,
                    hold_rub = hold_rub + $2,
                    updated_at = NOW()
                WHERE user_id = $1
            """, user_id, amount_rub)
            
            logger.info(f"Hold {user_id}: {amount_rub} RUB (ref: {ref})")
            return True
    
    async def charge(self, user_id: int, amount_rub: Decimal, 
                    ref: str, meta: Dict = None) -> bool:
        """Charge held funds."""
        async with self.db.transaction() as conn:
            # Check hold exists
            wallet = await conn.fetchrow(
                "SELECT hold_rub FROM wallets WHERE user_id = $1 FOR UPDATE",
                user_id
            )
            if not wallet or wallet['hold_rub'] < amount_rub:
                return False
            
            # Insert ledger
            await conn.execute("""
                INSERT INTO ledger (user_id, kind, amount_rub, status, ref, meta)
                VALUES ($1, 'charge', $2, 'done', $3, $4)
            """, user_id, amount_rub, ref, meta or {})
            
            # Deduct from hold
            await conn.execute("""
                UPDATE wallets
                SET hold_rub = hold_rub - $2,
                    updated_at = NOW()
                WHERE user_id = $1
            """, user_id, amount_rub)
            
            logger.info(f"Charge {user_id}: -{amount_rub} RUB (ref: {ref})")
            return True
    
    async def refund(self, user_id: int, amount_rub: Decimal, 
                    ref: str, meta: Dict = None) -> bool:
        """Refund from hold to balance."""
        async with self.db.transaction() as conn:
            # Check idempotency
            existing = await conn.fetchval(
                "SELECT id FROM ledger WHERE ref = $1 AND kind = 'refund' AND status = 'done'",
                ref
            )
            if existing:
                logger.warning(f"Refund {ref} already processed")
                return False
            
            # Insert ledger
            await conn.execute("""
                INSERT INTO ledger (user_id, kind, amount_rub, status, ref, meta)
                VALUES ($1, 'refund', $2, 'done', $3, $4)
            """, user_id, amount_rub, ref, meta or {})
            
            # Move hold back to balance
            await conn.execute("""
                UPDATE wallets
                SET hold_rub = hold_rub - $2,
                    balance_rub = balance_rub + $2,
                    updated_at = NOW()
                WHERE user_id = $1
            """, user_id, amount_rub)
            
            logger.info(f"Refund {user_id}: +{amount_rub} RUB (ref: {ref})")
            return True


class JobService:
    """Job (generation task) operations."""
    
    def __init__(self, db: DatabaseService):
        self.db = db
    
    async def create(self, user_id: int, model_id: str, category: str,
                    input_json: Dict, price_rub: Decimal, 
                    idempotency_key: str) -> Optional[int]:
        """Create new job (idempotent)."""
        async with self.db.transaction() as conn:
            # Check idempotency
            existing = await conn.fetchval(
                "SELECT id FROM jobs WHERE idempotency_key = $1",
                idempotency_key
            )
            if existing:
                logger.warning(f"Job {idempotency_key} already exists")
                return existing
            
            # Insert job
            job_id = await conn.fetchval("""
                INSERT INTO jobs (user_id, model_id, category, input_json, price_rub, 
                                 status, idempotency_key)
                VALUES ($1, $2, $3, $4, $5, 'draft', $6)
                RETURNING id
            """, user_id, model_id, category, input_json, price_rub, idempotency_key)
            
            logger.info(f"Created job {job_id} for user {user_id}")
            return job_id
    
    async def get(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Get job by ID."""
        async with self.db.transaction() as conn:
            job = await conn.fetchrow(
                "SELECT * FROM jobs WHERE id = $1",
                job_id
            )
            return dict(job) if job else None
    
    async def update_status(self, job_id: int, status: str, 
                           kie_task_id: str = None, kie_status: str = None,
                           result_json: Dict = None, error_text: str = None):
        """Update job status."""
        async with self.db.transaction() as conn:
            await conn.execute("""
                UPDATE jobs
                SET status = $2,
                    kie_task_id = COALESCE($3, kie_task_id),
                    kie_status = COALESCE($4, kie_status),
                    result_json = COALESCE($5, result_json),
                    error_text = COALESCE($6, error_text),
                    updated_at = NOW(),
                    finished_at = CASE WHEN $2 IN ('succeeded', 'failed', 'refunded', 'cancelled') 
                                      THEN NOW() ELSE finished_at END
                WHERE id = $1
            """, job_id, status, kie_task_id, kie_status, result_json, error_text)
    
    async def list_user_jobs(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get user's jobs."""
        async with self.db.transaction() as conn:
            rows = await conn.fetch("""
                SELECT id, model_id, status, price_rub, created_at, finished_at
                FROM jobs
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, user_id, limit)
            return [dict(row) for row in rows]


class UIStateService:
    """UI state management (FSM)."""
    
    def __init__(self, db: DatabaseService):
        self.db = db
    
    async def get(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get UI state."""
        async with self.db.transaction() as conn:
            state = await conn.fetchrow(
                "SELECT state, data FROM ui_state WHERE user_id = $1",
                user_id
            )
            return dict(state) if state else None
    
    async def set(self, user_id: int, state: str, data: Dict = None, 
                 ttl_minutes: int = 60):
        """Set UI state with TTL."""
        async with self.db.transaction() as conn:
            expires_at = datetime.now() + timedelta(minutes=ttl_minutes)
            await conn.execute("""
                INSERT INTO ui_state (user_id, state, data, expires_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) DO UPDATE
                SET state = EXCLUDED.state,
                    data = EXCLUDED.data,
                    updated_at = NOW(),
                    expires_at = EXCLUDED.expires_at
            """, user_id, state, data or {}, expires_at)
    
    async def clear(self, user_id: int):
        """Clear UI state."""
        async with self.db.transaction() as conn:
            await conn.execute(
                "DELETE FROM ui_state WHERE user_id = $1",
                user_id
            )
    
    async def cleanup_expired(self):
        """Remove expired states."""
        async with self.db.transaction() as conn:
            deleted = await conn.execute(
                "DELETE FROM ui_state WHERE expires_at < NOW()"
            )
            if deleted != "DELETE 0":
                logger.info(f"Cleaned up expired UI states: {deleted}")
