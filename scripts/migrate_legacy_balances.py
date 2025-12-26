#!/usr/bin/env python3
"""
Migration script: Remove legacy 200₽ welcome bonuses.

CONTEXT:
- Old code gave 200₽ welcome bonus by default
- New code has START_BONUS_RUB=0 by default
- This script identifies and optionally removes legacy balances

SAFETY:
- Dry-run by default (no DB changes)
- Requires --confirm flag to execute
- Logs all operations to migrations.log
- Idempotent (safe to run multiple times)

USAGE:
    # Dry run (check what would be migrated):
    python scripts/migrate_legacy_balances.py

    # Execute migration:
    python scripts/migrate_legacy_balances.py --confirm

    # Custom thresholds:
    python scripts/migrate_legacy_balances.py --min-balance 190 --max-balance 210 --confirm
"""
import asyncio
import asyncpg
import os
import sys
import logging
from pathlib import Path
from decimal import Decimal
from datetime import datetime
import argparse

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.utils.config import load_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('migrations.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def find_legacy_balances(conn, min_balance: Decimal, max_balance: Decimal):
    """Find wallets with likely legacy welcome balances.
    
    Heuristic: Balance between min_balance and max_balance (default 190-210₽)
    AND no other ledger entries besides 'welcome_*' topups.
    """
    query = """
        SELECT 
            w.user_id,
            w.balance_rub,
            w.hold_rub,
            w.created_at,
            COUNT(l.id) FILTER (WHERE l.kind != 'topup' OR l.ref NOT LIKE 'welcome_%') as other_entries,
            SUM(l.amount_rub) FILTER (WHERE l.kind = 'topup' AND l.ref LIKE 'welcome_%') as welcome_sum
        FROM wallets w
        LEFT JOIN ledger l ON l.user_id = w.user_id
        WHERE w.balance_rub BETWEEN $1 AND $2
            AND w.hold_rub = 0  -- No pending holds
        GROUP BY w.user_id, w.balance_rub, w.hold_rub, w.created_at
        HAVING COUNT(l.id) FILTER (WHERE l.kind != 'topup' OR l.ref NOT LIKE 'welcome_%') = 0
        ORDER BY w.created_at DESC
    """
    
    rows = await conn.fetch(query, min_balance, max_balance)
    
    candidates = []
    for row in rows:
        candidates.append({
            'user_id': row['user_id'],
            'balance_rub': row['balance_rub'],
            'welcome_sum': row['welcome_sum'] or Decimal('0'),
            'created_at': row['created_at']
        })
    
    return candidates


async def migrate_user_balance(conn, user_id: int, amount: Decimal, dry_run: bool = True):
    """Migrate single user's legacy balance.
    
    Creates compensating 'legacy_migration' ledger entry to zero out the balance.
    """
    if dry_run:
        logger.info(f"  [DRY RUN] Would create ledger entry: user={user_id} amount=-{amount}₽")
        return True
    
    try:
        # Create compensating ledger entry
        ref = f"legacy_migration_{user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        await conn.execute("""
            INSERT INTO ledger (user_id, kind, amount_rub, status, ref, meta)
            VALUES ($1, 'adjustment', $2, 'done', $3, $4)
        """, user_id, -amount, ref, {
            'reason': 'Legacy welcome bonus removal',
            'original_amount': str(amount),
            'migration_date': datetime.utcnow().isoformat()
        })
        
        # Update wallet
        await conn.execute("""
            UPDATE wallets
            SET balance_rub = balance_rub - $2,
                updated_at = NOW()
            WHERE user_id = $1
        """, user_id, amount)
        
        logger.info(f"  ✅ Migrated: user={user_id} removed {amount}₽")
        return True
        
    except Exception as e:
        logger.error(f"  ❌ Failed to migrate user {user_id}: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description='Migrate legacy 200₽ welcome balances')
    parser.add_argument('--confirm', action='store_true', help='Execute migration (default: dry-run)')
    parser.add_argument('--min-balance', type=float, default=190.0, help='Minimum balance to consider (default: 190)')
    parser.add_argument('--max-balance', type=float, default=210.0, help='Maximum balance to consider (default: 210)')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of users to migrate')
    
    args = parser.parse_args()
    
    dry_run = not args.confirm
    min_balance = Decimal(str(args.min_balance))
    max_balance = Decimal(str(args.max_balance))
    
    # Load config
    cfg = load_config()
    
    if not cfg.database_url:
        logger.error("❌ DATABASE_URL not configured. This migration requires PostgreSQL.")
        return 1
    
    logger.info("=" * 80)
    logger.info("LEGACY BALANCE MIGRATION")
    logger.info("=" * 80)
    logger.info(f"Mode: {'DRY RUN (no changes)' if dry_run else '🔥 LIVE EXECUTION'}")
    logger.info(f"Balance range: {min_balance}₽ - {max_balance}₽")
    logger.info(f"Limit: {args.limit or 'None'}")
    logger.info(f"Current START_BONUS_RUB: {cfg.start_bonus_rub}₽")
    logger.info("=" * 80)
    
    # Connect to DB
    conn = await asyncpg.connect(cfg.database_url)
    
    try:
        # Find candidates
        logger.info("\n🔍 Searching for legacy balances...")
        candidates = await find_legacy_balances(conn, min_balance, max_balance)
        
        if not candidates:
            logger.info("✅ No legacy balances found. Migration complete!")
            return 0
        
        logger.info(f"\n📊 Found {len(candidates)} candidate wallets:")
        logger.info("-" * 80)
        
        total_amount = Decimal('0')
        for i, c in enumerate(candidates, 1):
            logger.info(
                f"{i:3d}. user_id={c['user_id']:10d} | "
                f"balance={c['balance_rub']:7.2f}₽ | "
                f"welcome_sum={c['welcome_sum']:7.2f}₽ | "
                f"created={c['created_at'].strftime('%Y-%m-%d')}"
            )
            total_amount += c['balance_rub']
        
        logger.info("-" * 80)
        logger.info(f"Total amount to migrate: {total_amount}₽")
        logger.info("")
        
        if dry_run:
            logger.info("⚠️  This is a DRY RUN. No changes will be made.")
            logger.info("⚠️  Run with --confirm to execute migration.")
            return 0
        
        # Confirm execution
        logger.warning("🔥 LIVE EXECUTION MODE - This will modify the database!")
        logger.warning(f"🔥 {len(candidates)} wallets will be adjusted")
        logger.warning(f"🔥 Total amount: -{total_amount}₽")
        
        # Execute migration
        logger.info("\n🚀 Starting migration...")
        
        success_count = 0
        fail_count = 0
        
        limit = args.limit or len(candidates)
        
        for i, c in enumerate(candidates[:limit], 1):
            logger.info(f"\n[{i}/{min(limit, len(candidates))}] Migrating user {c['user_id']}...")
            
            success = await migrate_user_balance(
                conn, 
                c['user_id'], 
                c['balance_rub'],
                dry_run=False
            )
            
            if success:
                success_count += 1
            else:
                fail_count += 1
        
        logger.info("\n" + "=" * 80)
        logger.info("MIGRATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"✅ Success: {success_count}")
        logger.info(f"❌ Failed: {fail_count}")
        logger.info(f"📊 Total processed: {success_count + fail_count}")
        logger.info("=" * 80)
        
        return 0 if fail_count == 0 else 1
        
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
