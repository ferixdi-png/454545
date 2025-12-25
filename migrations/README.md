# Database Migrations

This directory contains Alembic migration files for database schema changes.

## MASTER PROMPT Compliance

According to MASTER PROMPT requirements:
- NO MVP - production-level migrations only
- NO guesses - all schema changes documented
- NO breaking changes without migration path

## Setup

```bash
# Initialize (already done)
alembic init migrations

# Create new migration
alembic revision -m "description of change"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Migration Policy

1. **NEVER** modify existing migrations after deployment
2. **ALWAYS** test migration both upgrade and downgrade
3. **ALWAYS** include data migration if schema changes affect existing data
4. **DOCUMENT** breaking changes in migration docstring

## Current Schema

See `app/database/schema.py` for the current production schema.
All migrations should be compatible with this baseline.
