"""
PostgreSQL schema definitions and migrations.

Tables:
- users: user profiles
- wallets: balance tracking
- ledger: atomic balance operations journal
- jobs: generation tasks
- ui_state: FSM context storage
"""
import logging

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    role TEXT DEFAULT 'user' CHECK (role IN ('user', 'admin', 'banned')),
    locale TEXT DEFAULT 'ru',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Note: tg_username, tg_first_name, tg_last_name added via ALTER TABLE in apply_schema()
-- (for migration-safe deployment to existing production DBs)

CREATE INDEX IF NOT EXISTS idx_users_created ON users(created_at);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Wallets table
CREATE TABLE IF NOT EXISTS wallets (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    balance_rub NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (balance_rub >= 0),
    hold_rub NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (hold_rub >= 0),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT balance_plus_hold_positive CHECK (balance_rub + hold_rub >= 0)
);

CREATE INDEX IF NOT EXISTS idx_wallets_updated ON wallets(updated_at);

-- Ledger table (append-only journal)
CREATE TABLE IF NOT EXISTS ledger (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('topup', 'charge', 'refund', 'hold', 'release', 'adjust')),
    amount_rub NUMERIC(12, 2) NOT NULL,
    status TEXT NOT NULL DEFAULT 'done' CHECK (status IN ('pending', 'done', 'failed', 'cancelled')),
    ref TEXT,
    meta JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ledger_user ON ledger(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_ref ON ledger(ref) WHERE ref IS NOT NULL;

-- Free models configuration
CREATE TABLE IF NOT EXISTS free_models (
    model_id TEXT PRIMARY KEY,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    daily_limit INT NOT NULL DEFAULT 5,
    hourly_limit INT DEFAULT 2,
    meta JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_free_models_enabled ON free_models(enabled);

-- Free usage tracking
CREATE TABLE IF NOT EXISTS free_usage (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    model_id TEXT NOT NULL,
    job_id TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_free_usage_user_model ON free_usage(user_id, model_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_free_usage_created ON free_usage(created_at);

-- Admin actions log
CREATE TABLE IF NOT EXISTS admin_actions (
    id BIGSERIAL PRIMARY KEY,
    admin_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    action_type TEXT NOT NULL CHECK (action_type IN (
        'model_enable', 'model_disable', 'model_price', 'model_free', 
        'user_topup', 'user_charge', 'user_ban', 'user_unban',
        'config_change', 'other'
    )),
    target_type TEXT NOT NULL CHECK (target_type IN ('model', 'user', 'config', 'system')),
    target_id TEXT,
    old_value JSONB,
    new_value JSONB,
    meta JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_actions_admin ON admin_actions(admin_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_actions_type ON admin_actions(action_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_actions_target ON admin_actions(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_ledger_ref ON ledger(ref);
CREATE INDEX IF NOT EXISTS idx_ledger_status ON ledger(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ledger_idempotency ON ledger(ref) WHERE ref IS NOT NULL AND status = 'done';

-- Jobs table (generation tasks)
CREATE TABLE IF NOT EXISTS jobs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    model_id TEXT NOT NULL,
    category TEXT NOT NULL,
    input_json JSONB NOT NULL,
    price_rub NUMERIC(12, 2) NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft', 'await_confirm', 'queued', 'running', 
        'succeeded', 'failed', 'refunded', 'cancelled'
    )),
    kie_task_id TEXT,
    kie_status TEXT,
    result_json JSONB,
    error_text TEXT,
    idempotency_key TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_idempotency ON jobs(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_kie_task ON jobs(kie_task_id);

-- UI State table (FSM context)
CREATE TABLE IF NOT EXISTS ui_state (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    state TEXT NOT NULL,
    data JSONB DEFAULT '{}'::jsonb,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ui_state_expires ON ui_state(expires_at);

-- Singleton heartbeat (already exists, keep it)
CREATE TABLE IF NOT EXISTS singleton_heartbeat (
    lock_id INTEGER PRIMARY KEY,
    instance_name TEXT NOT NULL,
    last_heartbeat TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Generation events tracking (for diagnostics and admin view)
CREATE TABLE IF NOT EXISTS generation_events (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    chat_id BIGINT,
    model_id TEXT NOT NULL,
    category TEXT,
    status TEXT NOT NULL CHECK(status IN ('started', 'success', 'failed', 'timeout')),
    is_free_applied BOOLEAN DEFAULT FALSE,
    price_rub NUMERIC(12, 2) DEFAULT 0.00,
    request_id TEXT,
    task_id TEXT,
    error_code TEXT,
    error_message TEXT,
    duration_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_gen_events_user ON generation_events(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_gen_events_status ON generation_events(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_gen_events_request ON generation_events(request_id);

-- Processed Telegram updates (for multi-instance idempotency)
CREATE TABLE IF NOT EXISTS processed_updates (
    update_id BIGINT PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_processed_updates_timestamp ON processed_updates(processed_at);
"""


async def apply_schema(connection):
    """
    Apply database schema (idempotent + migration-safe).
    
    Handles both fresh installs and migrations from old schema.
    Uses ALTER TABLE ADD COLUMN IF NOT EXISTS for safe production migrations.
    """
    # First: ensure tables exist with CREATE TABLE IF NOT EXISTS
    await connection.execute(SCHEMA_SQL)
    
    # Second: add new columns if they don't exist (migration from old schema)
    # This handles production DBs that were created before tg_username/tg_first_name/tg_last_name
    await connection.execute("""
        -- Add Telegram username fields if not exists (migration-safe)
        DO $$
        BEGIN
            -- Add tg_username column
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'tg_username'
            ) THEN
                ALTER TABLE users ADD COLUMN tg_username TEXT;
            END IF;
            
            -- Add tg_first_name column
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'tg_first_name'
            ) THEN
                ALTER TABLE users ADD COLUMN tg_first_name TEXT;
            END IF;
            
            -- Add tg_last_name column
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'tg_last_name'
            ) THEN
                ALTER TABLE users ADD COLUMN tg_last_name TEXT;
            END IF;
            
            -- Create index on tg_username if doesn't exist
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes 
                WHERE tablename = 'users' AND indexname = 'idx_users_username'
            ) THEN
                CREATE INDEX idx_users_username ON users(tg_username);
            END IF;
        END $$;
    """)
    
    logger.info("✅ Schema applied successfully (idempotent + migration-safe)")


async def verify_schema(connection) -> bool:
    """Verify all tables exist."""
    required_tables = ['users', 'wallets', 'ledger', 'jobs', 'ui_state']
    for table in required_tables:
        result = await connection.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = $1
            )
        """, table)
        if not result:
            return False
    return True
