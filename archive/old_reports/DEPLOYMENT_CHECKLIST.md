# 🚀 PRODUCTION DEPLOYMENT CHECKLIST

## Pre-Deploy Validation

```bash
# 1. Проверка registry
python scripts/validate_registry.py

# 2. Health check
PYTHONPATH=/workspaces/5656 python scripts/quick_health_check.py

# 3. Компиляция
python -m compileall app/ bot/ scripts/

# Ожидаемый результат:
# ✅ ALL CHECKS PASSED - READY FOR PRODUCTION
```

## Environment Setup

```bash
# Required variables
export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
export KIE_API_KEY="sk-..."

# Optional
export ADMIN_IDS="12345,67890"
export PORT="8080"
```

## Database Migration

```bash
# Run migrations
alembic upgrade head

# Verify tables
psql $DATABASE_URL -c "\dt"

# Expected tables:
# - users
# - wallets
# - ledger
# - free_models
# - free_usage
# - admin_actions
```

## FREE Tier Setup

```bash
# Auto-configure 5 cheapest models
python scripts/setup_free_tier.py

# Expected output:
# ✅ recraft/crisp-upscale configured (10/day, 3/hour)
# ✅ qwen/z-image configured (10/day, 3/hour)
# ✅ recraft/remove-background configured (10/day, 3/hour)
# ✅ midjourney/image-to-image:relaxed-v3 configured (10/day, 3/hour)
# ✅ midjourney/text-to-image:relaxed-v3 configured (10/day, 3/hour)
```

## Smoke Testing (Optional but Recommended)

```bash
# DRY RUN (no API calls, just validation)
python scripts/smoke_test_kie.py

# REAL API test (costs ~7₽)
python scripts/smoke_test_kie.py --real

# Expected:
# ✅ Tested 5/5 cheapest models
# 💰 Credits used: ~10
```

## Start Application

```bash
# Development
python main_render.py

# Production (with logs)
python main_render.py 2>&1 | tee bot.log

# Expected startup:
# ✅ PostgreSQL storage initialized
# ✅ DatabaseService initialized
# ✅ FreeModelManager initialized
# ✅ Free tier auto-setup: 5 models
# ✅ Rate limit middleware registered
# 🤖 Bot polling started
```

## Post-Deploy Verification

```bash
# 1. Check bot is running
curl http://localhost:8080/health
# Expected: {"status": "ok"}

# 2. Test in Telegram
# Send: /marketing
# Expected: Marketing menu with 6 categories

# 3. Test FREE tier
# Click: 🎁 Бесплатно попробовать
# Expected: List of 5 FREE models with 🎁 badges

# 4. Check database
psql $DATABASE_URL -c "SELECT COUNT(*) FROM free_models;"
# Expected: 5

# 5. Monitor logs
tail -f bot.log | grep -E "(ERROR|WARN|FREE|Auto-configured)"
```

## Rollback Plan

If something goes wrong:

```bash
# 1. Stop bot
pkill -f main_render.py

# 2. Rollback git
git reset --hard 0d89cb5  # Previous working commit

# 3. Restart
python main_render.py
```

## Common Issues

### Issue: "No module named 'app'"
```bash
# Fix: Set PYTHONPATH
export PYTHONPATH=/workspaces/5656:$PYTHONPATH
```

### Issue: "Registry not found"
```bash
# Fix: Check file exists
ls -la models/kie_models_final_truth.json
```

### Issue: "Database connection failed"
```bash
# Fix: Test connection
psql $DATABASE_URL -c "SELECT 1;"
```

### Issue: "FREE models not showing"
```bash
# Fix: Re-run setup
python scripts/setup_free_tier.py
```

## Monitoring

Watch these metrics:
- FREE tier usage (daily/hourly)
- Credits consumption
- Error rate in generations
- User conversion (FREE → paid)

## Support

Logs location: `bot.log`  
Health check: `http://localhost:8080/health`  
Registry validation: `python scripts/validate_registry.py`  
System check: `PYTHONPATH=/workspaces/5656 python scripts/quick_health_check.py`

---

**Status**: ✅ READY FOR DEPLOYMENT  
**Version**: v6.2  
**Last Update**: 2025-12-24
