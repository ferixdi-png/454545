# 🚀 Deploy to Render.com - Partner Guide

## Quick Start

This bot is production-ready and can be deployed to Render.com in under 5 minutes.

### Prerequisites

1. **Render.com Account** (free tier works)
2. **PostgreSQL Database** (Render provides free tier)
3. **Telegram Bot Token** (from @BotFather)
4. **Kie.ai API Key** (from https://kie.ai/settings/api-keys)
5. **Admin Telegram ID** (your user ID)

---

## Step 1: Create PostgreSQL Database

1. Go to Render Dashboard → New → PostgreSQL
2. Name: `5656-db` (or any name)
3. Region: Same as your web service (e.g., Oregon)
4. Plan: **Free** (for testing) or **Starter** (for production)
5. Click **Create Database**
6. Copy **Internal Database URL** (starts with `postgres://`)

---

## Step 2: Fork Repository

1. Fork this repository to your GitHub account
2. Clone your fork locally (optional, for customization)
3. Keep `main` branch as default

---

## Step 3: Create Web Service on Render

1. Go to Render Dashboard → New → Web Service
2. Connect your GitHub account
3. Select your forked repository
4. Configure:

**Basic Settings:**
- Name: `your-bot-name` (will be part of URL)
- Region: Oregon (US West) recommended
- Branch: `main`
- Root Directory: (leave empty)
- Runtime: **Python 3**

**Build & Deploy:**
- Build Command: `pip install -r requirements.txt`
- Start Command: `python3 main_render.py`

**Plan:**
- Free tier (for testing)
- Starter+ (for production, $7/month)

---

## Step 4: Environment Variables

Add these environment variables in Render Dashboard → Environment:

### Required

```bash
# Telegram Bot Token (from @BotFather)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Kie.ai API Key (from kie.ai/settings/api-keys)
KIE_API_KEY=kie_abc123def456ghi789jkl

# PostgreSQL Database URL (from Step 1)
DATABASE_URL=postgres://user:pass@host/db

# Your Telegram User ID (Admin access)
# Get it from @userinfobot
ADMIN_ID=123456789
```

### Optional

```bash
# Database connection pool size (default: 10)
DB_MAXCONN=10

# Log level (default: INFO)
LOG_LEVEL=INFO

# Payment card for top-ups (mask for OCR)
PAYMENT_CARD=2202 2000 0000 0000
```

---

## Step 5: Deploy

1. Click **Create Web Service**
2. Render will:
   - Clone your repository
   - Install dependencies
   - Run database migrations automatically
   - Start the bot
3. Wait 2-3 minutes for deployment
4. Check logs for `✅ Bot started successfully`

---

## Step 6: Verify Deployment

### Health Check

Visit: `https://your-bot-name.onrender.com/health`

Expected response:
```json
{
  "status": "ok",
  "mode": "active",
  "reason": "lock_acquired"
}
```

### Test Bot

1. Open Telegram
2. Find your bot (@your_bot_username)
3. Send `/start`
4. You should see main menu with FREE models

---

## Step 7: Admin Panel

1. Send `/admin` in Telegram (only works for ADMIN_ID)
2. You should see admin menu:
   - Users management
   - Balance operations
   - Model configuration
   - System logs

---

## Troubleshooting

### Bot not responding

**Check 1: Logs**
```
Render Dashboard → Your Service → Logs
Look for errors or warnings
```

**Check 2: Environment Variables**
```
All required vars set?
TELEGRAM_BOT_TOKEN correct?
DATABASE_URL accessible?
```

**Check 3: Database**
```
Can connect to PostgreSQL?
Tables created? (auto-migration on startup)
```

### "Service Unavailable"

**Cause**: No active instance (Render free tier spins down)
**Fix**: Upgrade to Starter plan ($7/month) for 24/7 uptime

### Double Polling Error

**Cause**: Two instances running (old + new)
**Fix**: Wait 30 seconds - singleton lock prevents this automatically

### Database Migration Failed

**Symptom**: Errors about missing tables
**Fix**: 
```bash
# Restart service (Render Dashboard → Manual Deploy)
# Migrations run automatically on startup
```

---

## Configuration

### Customize FREE Tier

Edit `app/pricing/free_models.py`:

```python
# Change number of free models
TOP_N_FREE = 5  # Default: 5 cheapest

# Or manually set free models
MANUAL_FREE_MODELS = [
    'elevenlabs-audio-isolation',
    'z-image',
    # ... add more
]
```

### Customize Pricing Formula

Edit `app/payments/pricing.py`:

```python
# Current: price_usd × 78.59 (fx_rate) × 2.0 (markup)
MARKUP_MULTIPLIER = 2.0  # Change markup

# Update FX rate (auto-fetch or manual)
USD_TO_RUB = 78.59
```

### Add More Models

Edit `models/kie_source_of_truth.json`:

```json
{
  "models": [
    {
      "model_id": "new-model",
      "api_endpoint": "vendor/new-model",
      "display_name": "New Model",
      "category": "text-to-image",
      "pricing": {
        "usd_per_use": 0.05,
        "rub_per_use": 7.86
      },
      "input_schema": {
        "prompt": {"type": "string", "required": true}
      }
    }
  ]
}
```

Commit and push - Render auto-deploys from GitHub.

---

## Zero-Downtime Deployment

When you push to `main`:

1. Render detects change
2. Builds new instance
3. New instance waits for singleton lock
4. Old instance receives SIGTERM (graceful shutdown)
5. Old instance releases lock
6. New instance acquires lock and starts polling
7. **No duplicate messages**

Total downtime: **~5-10 seconds** (lock handover)

---

## Monitoring

### Logs

Render Dashboard → Logs → Real-time stream

Look for:
- `✅ Bot started successfully`
- `🆓 FREE tier models: 5`
- `✅ Database connected`
- `✅ Singleton lock acquired`

### Health Endpoint

Monitor: `https://your-service.onrender.com/health`

Use external monitoring (UptimeRobot, Pingdom):
- Interval: 5 minutes
- Alert if down for 10+ minutes

### Database

Render Dashboard → PostgreSQL → Connections

Watch:
- Active connections (should be < DB_MAXCONN)
- Slow queries (optimize if > 100ms)

---

## Scaling

### Free Tier Limits

- CPU: Shared
- RAM: 512MB
- Spins down after 15 min inactivity
- Cold start: ~30 seconds

**Use for**: Testing, demos, low-traffic bots

### Starter Plan ($7/month)

- CPU: Shared
- RAM: 512MB
- **Always on** (no spin down)
- Better for: Small production deployments

### Pro Plans ($25+/month)

- Dedicated CPU
- More RAM (1GB+)
- Better performance
- Use for: High-traffic production

---

## Partner Deployment Checklist

Before giving to partners:

- [ ] Fork repository to partner's GitHub
- [ ] Set up Render account (partner's card)
- [ ] Create PostgreSQL database
- [ ] Set environment variables (unique API keys)
- [ ] Deploy and verify
- [ ] Test FREE tier (5 models)
- [ ] Test paid generation (small amount)
- [ ] Give partner admin access (/admin)
- [ ] Document custom configuration (if any)

---

## Security Best Practices

### API Keys

- **Never commit** API keys to git
- Use Render environment variables
- Rotate keys periodically
- Different keys per environment (dev/prod)

### Database

- Use internal URL (not external)
- Enable SSL (Render default)
- Regular backups (Render auto-backup)

### Admin Access

- Set ADMIN_ID to your Telegram user ID only
- Don't share admin credentials
- Use /admin commands carefully

---

## Support

### Issues

GitHub Issues: https://github.com/ferixdi-png/5656/issues

### Documentation

- `docs/PRICING.md` - Pricing formula and FREE tier
- `docs/MODELS.md` - Model registry and parameters
- `PRODUCTION_READY_REPORT_v1.md` - Complete system documentation

### Render Support

- Free tier: Community support only
- Paid plans: Email support
- Enterprise: Priority support

---

## Cost Estimate (Monthly)

### Minimum (Free Tier)

- Render Web Service: **$0**
- PostgreSQL: **$0**
- Kie.ai API: ~$5-20 (depends on usage)
- **Total**: ~$5-20/month

### Recommended (Production)

- Render Web Service (Starter): **$7**
- PostgreSQL (Starter): **$7**
- Kie.ai API: ~$50-200 (depends on traffic)
- **Total**: ~$64-214/month

### Notes

- FREE tier models don't consume Kie.ai credits
- User top-ups cover Kie.ai costs
- Markup (2x) provides profit margin

---

## Quick Deploy Script (Advanced)

```bash
#!/bin/bash
# deploy.sh - Automated deployment

# Set variables
export RENDER_API_KEY="your_render_api_key"
export SERVICE_NAME="your-bot-name"
export GITHUB_REPO="your-username/5656"

# Create service via Render API
curl -X POST "https://api.render.com/v1/services" \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "web",
    "name": "'$SERVICE_NAME'",
    "repo": "https://github.com/'$GITHUB_REPO'",
    "branch": "main",
    "runtime": "python",
    "buildCommand": "pip install -r requirements.txt",
    "startCommand": "python3 main_render.py"
  }'
```

---

**Last Updated**: 2024-12-24  
**Version**: 1.0  
**Status**: Production Ready ✅
