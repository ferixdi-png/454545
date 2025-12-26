# 🚀 Deployment Checklist — Final Fixpack

## Pre-deployment Verification

### 1. Run Verify Scripts ✅
```bash
python scripts/verify_fixpack.py
# Expected: 9/9 checks passed

python scripts/health_check_fixpack.py
# Expected: All systems operational
```

### 2. Check ENV Variables
Required for production (Render):
- `TELEGRAM_BOT_TOKEN` — bot token from @BotFather
- `TELEGRAM_BOT_USERNAME` — bot username (WITHOUT @)
- `KIE_API_KEY` — Kie.ai API key
- `ADMIN_ID` — admin user ID(s)
- `DATABASE_URL` — PostgreSQL connection string

Optional:
- `START_BONUS_RUB` — welcome bonus (default: 0)
- `BOT_MODE` — "polling" or "webhook" (default: polling)

### 3. Manual Testing (Critical Flows)

#### Test 1: Basic Generation Flow
```
/start
→ Click "🧩 Форматы"
→ Select "✍️ Text → Image"
→ Choose any free model
→ Wizard: enter prompt "test sunset"
→ Confirm
→ Verify: generation starts, result received
```

#### Test 2: Required Field Validation
```
Navigate to Image→Video model
→ Wizard should ask for image_url
→ Try to skip (should not allow if required)
→ Enter valid URL
→ Confirm
→ Verify: generation works
```

#### Test 3: Referral Link
```
Menu → "🤝 Партнёрка"
→ Verify: link shows as https://t.me/YOUR_BOT_USERNAME?start=ref_...
→ Click link (opens Telegram)
→ Verify: bot starts correctly
```

#### Test 4: Error Handling
```
Trigger any generation error (invalid input, API error, etc.)
→ Verify: user sees friendly message
→ Verify: buttons "🔁 Повторить", "🏠 В меню", "�� Поддержка" present
→ Verify: bot doesn't crash, state recoverable
```

### 4. Database Health

If using PostgreSQL:
```bash
# Check that tables exist
psql $DATABASE_URL -c "\dt"

# Should see:
# - users
# - generation_events
# - processed_updates
# - referral_links (if applicable)

# Check FK constraint exists
psql $DATABASE_URL -c "\d generation_events"
# Should show FK to users(user_id)
```

### 5. Logs Check

After deployment, monitor logs for:
- ✅ "Bot application created successfully"
- ✅ "Database initialized with schema"
- ✅ "Bot username cached: @YOUR_BOT"
- ❌ NO "fetchrow" errors
- ❌ NO "FK violation" errors
- ❌ NO "bot not found" in referral links

---

## Deployment Steps (Render)

### 1. Push to GitHub
```bash
git add .
git commit -m "feat: Final Fixpack - Premium AI Studio UX + Critical Fixes"
git push origin main
```

### 2. Render Auto-Deploy
- Render will auto-deploy on push to main
- Monitor deploy logs in Render dashboard

### 3. Configure ENV in Render
Navigate to: Dashboard → Service → Environment
Add all required ENV variables (see section 2 above)

### 4. Verify Deployment
```bash
# Check health endpoint (if configured)
curl https://your-bot.onrender.com/health

# Or check logs
# Render Dashboard → Logs → verify startup messages
```

### 5. Test Bot in Telegram
- Send `/start` to your bot
- Run through all 4 test scenarios above
- Verify no errors in Render logs

---

## Rollback Plan

If issues detected:

### Quick Rollback
```bash
# In Render Dashboard:
# Manual Deploy → Select previous successful deploy → Deploy
```

### Investigate Issues
```bash
# Check logs
# Render Dashboard → Logs → Filter by error level

# Check database
psql $DATABASE_URL -c "SELECT * FROM generation_events WHERE status = 'failed' ORDER BY created_at DESC LIMIT 10;"
```

### Fix and Redeploy
1. Fix issue locally
2. Test with `python scripts/verify_fixpack.py`
3. Commit and push
4. Monitor new deployment

---

## Post-Deployment Monitoring

### First 24 Hours
- [ ] Monitor error rate in logs
- [ ] Check generation success rate
- [ ] Verify referral links work
- [ ] Monitor database FK violations (should be 0)
- [ ] Check user feedback

### Metrics to Watch
- Generation success rate (target: >95%)
- API error rate (target: <5%)
- Database errors (target: 0)
- User retention (Day 1)

---

## Success Criteria

✅ All verify scripts pass  
✅ No critical errors in logs  
✅ Referral links work correctly  
✅ Generation flow works end-to-end  
✅ Error messages are user-friendly  
✅ No FK violations  
✅ No "fetchrow" errors  

**If all criteria met: DEPLOYMENT SUCCESSFUL** 🎉

---

## Quick Reference

### Verify Commands
```bash
python scripts/verify_fixpack.py          # Full verification
python scripts/health_check_fixpack.py    # Quick health check
```

### Logs
```bash
# Render Dashboard → Logs
# Or via CLI:
render logs -t your-service-name
```

### Database
```bash
psql $DATABASE_URL -c "SELECT COUNT(*) FROM users;"
psql $DATABASE_URL -c "SELECT COUNT(*) FROM generation_events WHERE status = 'success';"
```
