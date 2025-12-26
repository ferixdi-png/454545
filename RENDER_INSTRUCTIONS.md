# 🚀 Render Deployment - Complete Instructions

## ✅ Code is Ready

All fixes are committed and pushed to GitHub (main branch):
- ✅ FREE tier updated to TOP-5 cheapest models
- ✅ `is_free` flags corrected in SOURCE_OF_TRUTH
- ✅ START_BONUS_RUB defaults to 0 (no magic 200₽)
- ✅ Webhook mode (no singleton lock)
- ✅ All 42 models enabled and validated

**Latest commit**: `acd2301 - SYNTX-LEVEL: Update FREE tier to TOP-5 cheapest + update is_free flags`

---

## 🎯 Critical Action Required on Render

### Problem

Render has environment variable `FREE_TIER_MODEL_IDS` with outdated value that overrides code defaults.

### Solution: Update ENV Variable

**Step 1**: Go to [Render Dashboard](https://dashboard.render.com/)

**Step 2**: Navigate to: Services → **454545** → Environment

**Step 3**: Find `FREE_TIER_MODEL_IDS`

**Step 4**: Update value to:
```
z-image,recraft/remove-background,infinitalk/from-audio,grok-imagine/text-to-image,google/nano-banana
```

**Step 5**: Click **"Save Changes"**

**Step 6**: Render will automatically redeploy

---

## 📋 All Environment Variables (Reference)

Copy these to Render if not already set:

```bash
# === REQUIRED ===
TELEGRAM_BOT_TOKEN=<from_BotFather>
KIE_API_KEY=<from_kie.ai>
DATABASE_URL=<postgres_internal_url>
ADMIN_ID=<your_telegram_user_id>
BOT_MODE=webhook
WEBHOOK_BASE_URL=https://454545.onrender.com

# === CRITICAL FIX ===
FREE_TIER_MODEL_IDS=z-image,recraft/remove-background,infinitalk/from-audio,grok-imagine/text-to-image,google/nano-banana

# === PRICING ===
PRICING_MARKUP_MULTIPLIER=2.0
START_BONUS_RUB=0

# === OPTIONAL ===
TELEGRAM_WEBHOOK_SECRET_TOKEN=<auto_generated>
TELEGRAM_WEBHOOK_PATH=/webhook
PORT=10000
LOG_LEVEL=INFO
```

---

## ✅ Verification After Deploy

### Check Logs

Go to: Render → 454545 → Logs (Live tail)

**Look for**:
```
✅ Source of truth загружен
✅ Models: 42 total, 42 enabled
✅ FREE tier matches TOP-5 cheapest
✅ Bot is READY (webhook mode)
```

**Should NOT see**:
```
❌ FREE tier не совпадает с TOP-5 cheapest
❌ Startup validation failed
```

### Test Bot

1. Open Telegram and find your bot
2. Send `/start`
3. Check balance shows `0₽` (not 200₽)
4. Go to "🎁 Бесплатные"
5. Should see exactly 5 models:
   - z-image (0.76₽)
   - recraft/remove-background (0.95₽)
   - infinitalk/from-audio (2.85₽)
   - grok-imagine/text-to-image (3.80₽)
   - google/nano-banana (3.80₽)

### Health Checks

```bash
curl https://454545.onrender.com/healthz
# Should return: {"status":"ok"}

curl https://454545.onrender.com/readyz
# Should return: {"status":"ready",...}
```

---

## 🐛 Troubleshooting

### Deploy Still Fails with OLD FREE tier

**Symptom**: Logs show old models like `flux-2/pro-text-to-image`

**Solution**: Clear render cache
1. Go to Render → 454545 → Manual Deploy
2. Click "Clear build cache & deploy"

### Bot Shows 200₽ Balance

**Symptom**: New users see 200₽ instead of 0₽

**Check ENV**:
- `START_BONUS_RUB` should be `0` (or deleted to use default)
- If you WANT bonus, set to desired amount (e.g., `100`)

### Validation Passes but Models Missing

**Symptom**: Bot starts but some models don't work

**Solution**: Check `MINIMAL_MODEL_IDS` ENV variable
- Should include all 42 models
- Or delete it to use default from code

---

## 📊 Expected Results

After successful deploy:

| Metric | Expected Value |
|--------|----------------|
| Enabled Models | 42 |
| FREE Tier Models | 5 (TOP-5 cheapest) |
| Default Balance | 0₽ |
| Webhook Mode | ✅ Active |
| Health `/healthz` | 200 OK |
| Health `/readyz` | 200 OK (when ready) |
| Startup Time | ~30-60 seconds |

---

## 🎉 Success Criteria

✅ No validation errors in logs  
✅ Bot responds to `/start`  
✅ Free models list shows 5 correct models  
✅ New users have 0₽ balance  
✅ All 42 models visible in catalog  
✅ Webhook endpoints working  

---

## 💡 Next Steps (After Deploy Success)

1. Test generation with free model (e.g., z-image)
2. Test generation with paid model (topup required)
3. Check admin panel `/admin` for metrics
4. Monitor logs for any errors
5. Test request_id search in admin

---

## 📞 Support

If deployment still fails after following these steps, check:
1. Render logs for specific error message
2. GitHub Actions (if enabled) for build errors
3. Render service status page

**Last updated**: December 26, 2025  
**Latest commit**: acd2301
