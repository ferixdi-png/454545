# Database Bootstrap Guide

This document explains the required database tables and how the system handles missing tables gracefully.

---

## Required Tables

### Core Tables (Always Required)
These tables are essential for basic operation:

```sql
-- Users (FK target for most tables)
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- User balances (for paid models)
CREATE TABLE balances (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
    balance_rub DECIMAL(10, 2) DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Optional Tables (Graceful Degradation)
If these tables don't exist, the system logs a WARNING and continues:

```sql
-- Generation events (diagnostics/admin)
CREATE TABLE generation_events (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    chat_id BIGINT,
    model_id TEXT NOT NULL,
    category TEXT,
    status TEXT NOT NULL,  -- 'started', 'success', 'failed', 'timeout'
    is_free_applied BOOLEAN DEFAULT FALSE,
    price_rub DECIMAL(10, 2) DEFAULT 0,
    request_id TEXT,
    task_id TEXT,
    error_code TEXT,
    error_message TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_generation_events_user_id ON generation_events(user_id);
CREATE INDEX idx_generation_events_created_at ON generation_events(created_at DESC);
CREATE INDEX idx_generation_events_status ON generation_events(status);

-- Projects (user organization)
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Project history (generation results)
CREATE TABLE project_history (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    model_id TEXT NOT NULL,
    inputs JSONB NOT NULL,
    outputs JSONB,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Referrals (gamification)
CREATE TABLE referrals (
    id SERIAL PRIMARY KEY,
    referrer_id BIGINT NOT NULL REFERENCES users(user_id),
    referred_id BIGINT NOT NULL REFERENCES users(user_id),
    reward_rub DECIMAL(10, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(referrer_id, referred_id)
);

-- Payment transactions (audit trail)
CREATE TABLE payment_transactions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    amount_rub DECIMAL(10, 2) NOT NULL,
    type TEXT NOT NULL,  -- 'topup', 'deduction', 'refund', 'referral'
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Bootstrap Script

Run this to create all tables:

```bash
# Using Alembic (recommended)
alembic upgrade head

# OR manually via psql
psql $DATABASE_URL < migrations/bootstrap.sql
```

---

## Graceful Degradation Behavior

### If `generation_events` missing:
- ✅ FREE models work normally
- ✅ Paid models work normally
- ⚠️ No diagnostics/admin stats available
- ⚠️ Logs WARNING: "generation_events table missing"
- **Impact:** Admin can't see failure patterns, but users unaffected

### If `projects` missing:
- ✅ All generations work
- ⚠️ "💼 Мои проекты" shows: "⚠️ База временно недоступна"
- **Impact:** Users can't organize/save results, but can still generate

### If `referrals` missing:
- ✅ All generations work
- ⚠️ "🤝 Партнёрка" shows: "⚠️ База временно недоступна"
- **Impact:** No referral rewards, but core functionality unaffected

### If `balances` missing:
- ✅ FREE models work
- ❌ Paid models show: "⚠️ База временно недоступна"
- **Impact:** Only free models usable until DB restored

### If `users` missing:
- ❌ System cannot function (FK target for everything)
- **Impact:** Critical failure, bot will crash

---

## FK Violation Prevention

### Problem:
Inserting into `generation_events` (or other tables) before user exists in `users` table causes FK violation.

### Solution:
`app/database/user_upsert.py` provides `ensure_user_exists()`:

```python
from app.database.user_upsert import ensure_user_exists

# Before any FK-dependent operation
await ensure_user_exists(db_service, user_id, username, first_name, last_name)

# Now safe to insert into generation_events, balances, etc.
```

### Where it's called:
1. `/start` handler (on first contact)
2. Middleware (every request, with TTL cache)
3. `log_generation_event()` (before insert)
4. Balance operations (before deduction)
5. Payment reservations (before creation)

### Caching:
- TTL: 600 seconds (10 minutes)
- Prevents DB spam for repeated requests
- Cleared on user data changes

---

## Startup Cleanup

On bot startup, the following cleanup runs (app/payments/recovery.py):

```python
async def cleanup_on_startup(db_service):
    # Release stuck payment reservations (older than 1 hour)
    # Release stale job locks (no heartbeat for TTL seconds)
    # Clear old idempotency records (older than 24 hours)
```

Called in `main_render.py` before webhook starts accepting requests.

---

## Migration Strategy

### New Deployment (Fresh DB):
1. Create database: `createdb mybot`
2. Run migrations: `alembic upgrade head`
3. Verify tables: `psql mybot -c '\dt'`
4. Start bot

### Existing Deployment (Add Tables):
1. Create migration: `alembic revision -m "add generation_events"`
2. Edit migration file to add table
3. Apply: `alembic upgrade head`
4. Restart bot

### Rollback (If Needed):
```bash
alembic downgrade -1  # Rollback last migration
```

---

## Monitoring

### Check Table Existence:
```sql
SELECT tablename FROM pg_tables WHERE schemaname = 'public';
```

### Check FK Constraints:
```sql
SELECT conname, conrelid::regclass, confrelid::regclass
FROM pg_constraint
WHERE contype = 'f';
```

### Check Recent Failures (if generation_events exists):
```sql
SELECT model_id, error_code, error_message, COUNT(*)
FROM generation_events
WHERE status IN ('failed', 'timeout')
  AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY model_id, error_code, error_message
ORDER BY COUNT(*) DESC
LIMIT 10;
```

---

## Troubleshooting

### Issue: FK violation on generation_events.user_id_fkey
**Cause:** User not created before event logged  
**Fix:** Ensure `ensure_user_exists()` called before insert  
**Verify:** Check `app/database/generation_events.py` line ~50

### Issue: "generation_events table missing" in logs
**Cause:** Table not created  
**Fix:** Run `alembic upgrade head`  
**Impact:** Non-critical, diagnostics unavailable but users unaffected

### Issue: "База временно недоступна" in UI
**Cause:** DB connection lost or tables missing  
**Fix:** Check DB connectivity, run migrations  
**Workaround:** FREE models still work

### Issue: Double charges on payments
**Cause:** Idempotency not enforced  
**Fix:** Check `app/payments/callback.py` has deduplication  
**Verify:** Test rapid duplicate callbacks

---

## Environment Variables

Required for DB connection:

```bash
# Render/Heroku style
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Split components (alternative)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mybot
DB_USER=postgres
DB_PASSWORD=secret
```

---

## Backup & Recovery

### Daily Backup:
```bash
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql
```

### Restore:
```bash
psql $DATABASE_URL < backup_20250101.sql
```

### Critical Data (Minimal):
- `users` table (FK target)
- `balances` table (money!)
- Rest can be recreated or is optional

---

## Performance Tuning

### Indexes (Already Created):
- `generation_events(user_id)` - User stats queries
- `generation_events(created_at)` - Recent failures
- `generation_events(status)` - Failure counts

### Connection Pooling:
```python
# In db_service initialization
pool = await asyncpg.create_pool(
    dsn=DATABASE_URL,
    min_size=5,
    max_size=20,
    command_timeout=30,
)
```

### Query Optimization:
- Use prepared statements (asyncpg does this automatically)
- Batch inserts where possible
- Use transactions for multi-step operations

---

**Status:** Complete  
**Last Updated:** $(date)  
**Alembic Migrations:** See `migrations/versions/`
