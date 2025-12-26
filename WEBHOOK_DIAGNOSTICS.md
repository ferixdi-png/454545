# Webhook Diagnostics & Troubleshooting

## 🔍 Quick Health Check

### 1. Check Render Logs (Critical!)

After deployment, look for these key logs:

```
✅ Bot identity: @your_bot_username (id=123456789, name=Bot Name)
📱 You should test with: @your_bot_username
```

**If you don't see this** → Wrong `TELEGRAM_BOT_TOKEN` or bot API is down.

```
🔍 WebhookInfo:
  - URL: https://five656.onrender.com/webhook/****
  - Pending updates: 0
  - IP address: 91.108.56.123
  - No delivery errors ✅
```

**If you see errors here** → Telegram cannot reach your webhook.

```
📨 Incoming webhook POST | path=/webhook/**** status=200
```

**If you don't see this within 30 seconds after /start** → Telegram is not sending updates.

---

## 🚨 Common Issues

### Issue 1: Wrong Bot Token

**Symptoms**:
- Logs show different `@username` than you expect
- You're testing with `@bot_a` but logs show `@bot_b`

**Fix**:
```bash
# On Render → Environment → TELEGRAM_BOT_TOKEN
# Make sure it matches your bot from @BotFather
```

---

### Issue 2: Webhook Delivery Errors

**Symptoms**:
```
⚠️ Last webhook error: 2025-12-26T12:00:00
⚠️ Error message: Wrong response from the webhook: 401 Unauthorized
```

**Common errors**:
- `401/403` → Secret mismatch (should be fixed by our dual security)
- `404` → Path mismatch (check `WEBHOOK_BASE_URL`)
- `502/503` → Server timeout/crash
- `SSL error` → Certificate issue (Render handles this automatically)

**Fix**: Check logs for crashes/errors during webhook POST handling.

---

### Issue 3: No Updates at All

**Symptoms**:
- Webhook registered ✅
- No delivery errors ✅
- But still no `📨 Incoming webhook POST` logs
- `/start` doesn't work

**Possible causes**:

1. **Bot blocked by Telegram**:
   - Send `/start` to `@BotFather`
   - Check your bot status

2. **Webhook URL mismatch**:
   - Verify `WEBHOOK_BASE_URL` matches your Render service URL
   - Check logs: `Full webhook URL: https://...`

3. **Old webhook cached**:
   - Bot might be registered to old URL
   - Check WebhookInfo in logs
   - If URL is wrong → fix `WEBHOOK_BASE_URL` and redeploy

---

## 🧪 Manual Testing

### Test 1: Probe Webhook Path

```bash
# Replace with your actual Render URL and secret path from logs
curl https://five656.onrender.com/webhook/YOUR_SECRET_HERE

# Expected response:
{
  "ok": true,
  "path": "/webhook/abcd****wxyz",
  "method": "GET",
  "note": "Telegram sends POST requests to this path"
}
```

**If this fails** → Your server is not reachable or path is wrong.

---

### Test 2: Check Bot Identity

In Telegram, send to your bot:
```
/diag
```

Should show:
```
🩺 Диагностика бота

🤖 Bot State:
  • Mode: webhook
  ...

🌐 Webhook Info:
  • URL: https://five656.onrender.com/webhook/****
  • Pending updates: 0
  
✅ No webhook errors
🟢 Status: HEALTHY
```

**If bot doesn't respond** → Check Render logs for crashes.

---

## 📋 Startup Checklist

After each deployment:

### Step 1: Check Bot Identity
```
Look for: 🤖 Bot identity: @your_bot_username
Action: Verify this matches your bot
```

### Step 2: Check WebhookInfo
```
Look for: 🔍 WebhookInfo:
  - URL: https://your-service.onrender.com/webhook/****
  - No delivery errors ✅
  
Action: If errors present → investigate
```

### Step 3: Send /start
```
In Telegram: Send /start to your bot
Look for: 📨 Incoming webhook POST | path=/webhook/**** status=200
Wait: 30 seconds max
```

### Step 4: Verify Response
```
Bot should reply with welcome message
If not → check logs for handler errors
```

---

## 🔧 Debug Commands

### Get current webhook info
```bash
# Using Telegram Bot API directly
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo"
```

### Delete webhook (emergency)
```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/deleteWebhook"
```

### Set webhook manually (if needed)
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook" \
  -d "url=https://five656.onrender.com/webhook/YOUR_SECRET" \
  -d "secret_token=YOUR_SECRET"
```

---

## 📊 Log Patterns to Watch

### ✅ Healthy Startup
```
✅ Startup validation PASSED
✅ Webhook registered successfully
🤖 Bot identity: @your_bot (id=123)
🔍 WebhookInfo: No delivery errors ✅
📨 Incoming webhook POST (after /start)
```

### ❌ Unhealthy Startup
```
❌ Failed to get bot identity: Unauthorized
⚠️ Last webhook error: 401 Unauthorized
🚫 Unauthorized webhook access (wrong path/secret)
```

---

## 🆘 Emergency Recovery

If bot is completely broken:

1. **Check Render logs** for startup errors
2. **Verify environment variables**:
   - `TELEGRAM_BOT_TOKEN` (correct token)
   - `WEBHOOK_BASE_URL` (matches Render URL)
   - `DATABASE_URL` (if using DB)
3. **Restart service** on Render (Manual Deploy → Deploy latest commit)
4. **Check bot with BotFather** (`/mybots` → verify bot exists)
5. **Test with curl** (probe endpoint)

---

## 📞 Support

If nothing helps:

1. **Collect logs**: Last 100 lines from Render
2. **Check bot identity**: What username does log show?
3. **Check WebhookInfo**: Any errors?
4. **Test probe**: Does `curl https://your-url/webhook/secret` work?

Include all this info when asking for help.
