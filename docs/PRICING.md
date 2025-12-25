# 💰 Pricing System Documentation

## Overview

This bot uses a **dual pricing model**:
1. **FREE Tier**: 5 cheapest models with daily limits
2. **Paid Models**: Pay-per-use with automatic wallet deductions

**NO welcome balance** - users must top up to use paid models.

---

## FREE Tier

### Free Models (Top 5 Cheapest)

| Model | Price/Use | Category |
|-------|-----------|----------|
| elevenlabs-audio-isolation | 0.16₽ | Audio |
| elevenlabs-sound-effects | 0.19₽ | Audio |
| suno-convert-to-wav | 0.31₽ | Audio |
| suno-generate-lyrics | 0.31₽ | Music |
| recraft-crisp-upscale | 0.39₽ | Image |

### Limits

**Daily Limits** (per model, per user):
- 5 generations per day

**Hourly Limits** (per model, per user):
- 2 generations per hour

**Reset Times**:
- Daily: 00:00 UTC
- Hourly: Every hour (e.g., 14:00, 15:00, etc.)

### Implementation

FREE tier checks happen in this order:

```python
# 1. Check if model is free
if not is_free_model(model_id):
    return "This model requires payment"

# 2. Check hourly limit
hourly_usage = get_hourly_usage(user_id, model_id)
if hourly_usage >= 2:
    return "⏱ Hourly limit reached (2/hour)"

# 3. Check daily limit
daily_usage = get_daily_usage(user_id, model_id)
if daily_usage >= 5:
    return "📅 Daily limit reached (5/day)"

# 4. Allow generation
proceed_with_generation()
```

Database tables:
- `free_models` - List of free model IDs
- `free_usage` - Usage tracking (user_id, model_id, timestamp)

---

## Paid Models Pricing

### Formula

```
price_rub = price_usd × fx_rate × markup
```

Where:
- `price_usd`: Kie.ai API price (from Kie.ai pricing page)
- `fx_rate`: USD to RUB exchange rate (78.59 as of 2024-12-24)
- `markup`: Profit margin multiplier (2.0 = 100% markup)

### Example

Model: `z-image` (image generation)
- Kie.ai price: 0.03 USD per image
- FX rate: 78.59
- Markup: 2.0

**Calculation:**
```
price_rub = 0.03 × 78.59 × 2.0 = 4.72₽
```

**Rounded**: 4.72₽ (no rounding, precise to kopeks)

### Pricing Tiers

Based on current source of truth (`models/kie_source_of_truth.json`):

| Tier | Price Range | Models Count | Use Cases |
|------|-------------|--------------|-----------|
| FREE | 0.16-0.39₽ | 5 | Audio effects, upscaling |
| Budget | 0.78-3.93₽ | 6 | Music, image editing |
| Standard | 4.72-15.72₽ | 8 | Image generation, voice cloning |
| Premium | 62.87-78.59₽ | 3 | Video generation, advanced AI |

**Full pricing list**: See `/models` command in bot.

---

## Payment Flow

### 1. User Requests Generation

User selects paid model → bot checks balance.

```python
wallet = get_wallet(user_id)
required_amount = get_model_price(model_id)

if wallet.balance < required_amount:
    return "Insufficient balance. Please /topup"
```

### 2. Reserve Funds (Atomic)

Before generation starts:

```python
# Create pending ledger entry
ledger_entry = create_ledger_entry(
    user_id=user_id,
    amount=-required_amount,  # Negative for debit
    status="pending",
    job_id=job_id
)

# Decrement wallet (optimistic lock)
wallet.balance -= required_amount
db.commit()
```

### 3. Generation

Call Kie.ai API:

```python
result = await kie_api.generate(model_id, inputs)
```

### 4a. Success → Commit Charge

```python
# Mark ledger entry as completed
ledger_entry.status = "completed"
db.commit()

# Funds already deducted in step 2
return result
```

### 4b. Failure → Auto-Refund

```python
# Mark ledger entry as refunded
ledger_entry.status = "refunded"

# Return funds to wallet
wallet.balance += required_amount
db.commit()

return "Generation failed. Funds returned."
```

**No manual intervention needed** - refunds are automatic.

---

## Wallet System

### Balance Tracking

Each user has one wallet:

```sql
CREATE TABLE wallets (
    user_id BIGINT PRIMARY KEY,
    balance NUMERIC(10,2) DEFAULT 0.00,  -- In rubles
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Balance Rules**:
- Cannot go negative
- Atomic updates (row-level locks)
- All changes logged in ledger

### Ledger (Audit Log)

Every transaction is recorded:

```sql
CREATE TABLE ledger (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    amount NUMERIC(10,2) NOT NULL,  -- Positive = credit, Negative = debit
    operation VARCHAR(50) NOT NULL,  -- 'topup', 'charge', 'refund', 'admin_adjustment'
    status VARCHAR(20) DEFAULT 'completed',  -- 'pending', 'completed', 'refunded'
    job_id VARCHAR(100),  -- Link to generation job
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Immutable** - entries are never deleted, only status changed.

### Invariants (Verified Nightly)

```python
# Sum of all ledger entries = total wallet balance
assert sum(ledger.amount for all users) == sum(wallet.balance for all users)

# No negative balances
assert all(wallet.balance >= 0 for wallet in wallets)

# All pending charges have corresponding jobs
assert all(job_exists(entry.job_id) for entry in ledger if entry.status == 'pending')
```

Run: `python scripts/verify_payment_invariants.py`

---

## Top-Up Methods

### Telegram Stars (Recommended)

Built-in Telegram payment system:

```python
# User taps "Top Up" → chooses amount
await bot.send_invoice(
    chat_id=user_id,
    title="Balance Top-Up",
    description=f"Add {amount}₽ to your balance",
    currency="XTR",  # Telegram Stars
    prices=[LabeledPrice(label="Balance", amount=amount * 100)]
)
```

**Fees**: ~5% (Telegram's cut)

### Card OCR (Manual)

User sends screenshot of card top-up:

```python
# 1. User sends screenshot
# 2. OCR extracts amount
# 3. Admin manually verifies and confirms
# 4. Balance added
```

**Admin command**: `/admin_topup user_id amount`

**Audit**: All manual top-ups logged in `admin_actions` table.

---

## Pricing Updates

### Automatic Sync (Recommended)

Run nightly:

```bash
python scripts/kie_sync_pricing.py
```

Updates `models/kie_source_of_truth.json` from Kie.ai API:

1. Fetch current USD prices from Kie.ai
2. Calculate RUB prices (formula above)
3. Update source of truth
4. Re-sync FREE tier (top 5 cheapest)
5. Commit changes

### Manual Update

Edit `models/kie_source_of_truth.json`:

```json
{
  "model_id": "some-model",
  "pricing": {
    "usd_per_use": 0.05,  // Update this
    "rub_per_use": 7.86   // Or this
  }
}
```

Restart bot to reload.

---

## FX Rate Updates

### Current Rate

```python
USD_TO_RUB = 78.59  # As of 2024-12-24
```

**Source**: Central Bank of Russia API (auto-fetch planned)

### Update Frequency

- **Manual**: Update `app/pricing/constants.py` when rate changes > 5%
- **Automatic** (future): Fetch daily from CBR API

### Impact Example

If USD/RUB changes from 78.59 → 90.00:

```python
# Old price (z-image)
0.03 × 78.59 × 2.0 = 4.72₽

# New price
0.03 × 90.00 × 2.0 = 5.40₽
```

**Change**: +14% price increase

**Recommendation**: Update monthly or when change > 10%.

---

## Markup Strategy

### Current Markup: 2.0x (100% profit)

```python
MARKUP_MULTIPLIER = 2.0
```

**Example**:
- Kie.ai charges us: 4.72₽
- We charge user: 4.72₽ × 2.0 = 9.44₽
- Profit: 4.72₽ (50% of user payment)

### Why 2.0x?

- **Infrastructure costs**: Hosting, database, support
- **FREE tier costs**: We pay for 5 free models
- **Risk buffer**: API failures, refunds
- **Profit margin**: Business sustainability

### Alternative Markups

```python
# Budget (1.5x = 50% markup)
MARKUP_MULTIPLIER = 1.5
# User pays: 4.72₽ × 1.5 = 7.08₽

# Premium (3.0x = 200% markup)
MARKUP_MULTIPLIER = 3.0
# User pays: 4.72₽ × 3.0 = 14.16₽
```

Edit `app/pricing/constants.py` and restart bot.

---

## Rounding Rules

### No Rounding (Current)

Prices shown to 2 decimal places (kopeks):

```
4.72₽ (exact)
```

**Pros**: Fair, transparent, precise  
**Cons**: Looks "weird" to users

### Rounding Up (Alternative)

```python
import math

price_rub = math.ceil(price_rub * 10) / 10  # Round up to 0.1₽
# 4.72₽ → 4.80₽
```

**Pros**: Clean prices  
**Cons**: Slightly overcharges users

### Rounding to Whole Rubles (Alternative)

```python
price_rub = math.ceil(price_rub)  # Round up to 1₽
# 4.72₽ → 5.00₽
```

**Pros**: Very clean  
**Cons**: Significant overcharge on cheap models

**Current choice**: No rounding (precise pricing).

---

## Cost Analysis (Example Month)

### Assumptions

- 1000 active users
- Each user: 3 FREE generations/day + 2 paid generations/week
- Average paid model price: 7.86₽ (z-image)

### Kie.ai API Costs

**FREE Tier**:
```
1000 users × 3 gen/day × 30 days × 0.16₽ avg = 14,400₽
```

**Paid Models**:
```
1000 users × 2 gen/week × 4 weeks × (7.86₽ / 2.0 markup) = 31,440₽
```

**Total API Costs**: 45,840₽/month

### Revenue

**Paid Models**:
```
1000 users × 2 gen/week × 4 weeks × 7.86₽ = 62,880₽
```

### Profit

```
Revenue: 62,880₽
Costs:   45,840₽
------
Profit:  17,040₽/month
```

**Margin**: 27% (after FREE tier subsidy)

### Break-Even Point

With 2.0x markup and FREE tier:

```
Users needed to cover $14/month hosting:
~50 users (paying users)

Users needed to be profitable:
~100 users
```

---

## Admin Tools

### View User Balance

```
/admin → Users → Select user → View balance
```

Shows:
- Current balance
- Total top-ups (lifetime)
- Total spent (lifetime)
- Recent transactions (last 10)

### Manual Balance Adjustment

```
/admin → Balance → Add/Remove
```

**Use cases**:
- Compensation for failed generation
- Promotional credits
- Refund for support case

**Audit**: All adjustments logged with admin_id and reason.

### Pricing Audit

```bash
python scripts/audit_pricing.py
```

Checks:
- ✅ All models have prices
- ✅ FREE tier is actually cheapest 5
- ✅ Markup applied correctly
- ✅ FX rate is current
- ✅ No negative prices

---

## FAQ

### Why no welcome balance?

**Answer**: User directive - only FREE tier for new users.

**Before**: 200₽ welcome credit  
**After**: 0₽ starting balance, must use FREE tier or top up

### Can users withdraw balance?

**No** - balance is non-refundable (like Steam Wallet).

### What happens to refunded amounts?

Automatically returned to wallet balance, not to original payment method.

### How long do top-ups take?

- **Telegram Stars**: Instant (< 1 second)
- **Card OCR**: 5-30 minutes (manual verification)

### Can prices change during generation?

**No** - price is locked when job starts (reserve step).

Example:
```python
# Price changed mid-generation
# User pays old price (locked at job creation)
job.locked_price = 4.72₽  # Won't change even if source updates
```

---

## Migration Notes

### Removing Welcome Balance

**Date**: 2024-12-24  
**Change**: Removed automatic 200₽ credit on /start

**Impact**:
- New users: Start with 0₽ balance
- Existing users: Keep current balance
- No retroactive changes

**Code change**: `bot/handlers/flow.py` - removed `ensure_welcome_credit()`

### Previous System (Deprecated)

```python
# OLD CODE (removed)
@router.message(Command("start"))
async def start_cmd(message, state):
    charge_manager.ensure_welcome_credit(user_id, 200.00)  # REMOVED
    await message.answer("Welcome! You have 200₽ to start.")
```

**Migration**: No database changes needed - ledger preserves history.

---

## References

- **Source of Truth**: `models/kie_source_of_truth.json`
- **Pricing Constants**: `app/pricing/constants.py`
- **FREE Tier Config**: `app/free/manager.py`
- **Payment Integration**: `app/payments/integration.py`
- **Kie.ai Pricing**: https://kie.ai/pricing

---

**Last Updated**: 2024-12-24  
**Version**: 1.0  
**Status**: Production Ready ✅
