# 🔥 SYNTX-LEVEL FINAL FIX - PROGRESS REPORT

**Date**: 2025-12-26  
**Status**: P0-P1 COMPLETE (Critical fixes deployed)  
**Commits**: a1e24f9, 3b2c3cd

---

## ✅ COMPLETED

### P0: Pricing Consistency (CRITICAL BUG FIXED)

**Problem**: 
- Code used both `rub_per_gen` and `rub_per_use` inconsistently
- Example: `rub_per_use=19₽` but `rub_per_gen=427.5₽` for same model
- UI showed wrong prices (427₽ instead of 19₽)
- FREE tier validation failed

**Solution**:
1. **Created `app/payments/pricing_contract.py`** - Single source of truth
   - `PricingContract` class with canonical pricing logic
   - `load_truth()` - reads `models/pricing_source_truth.txt`
   - `compute_rub_price(usd)` - formula: USD × MARKUP × FX_RATE
   - `derive_free_tier()` - auto-calculates TOP-5 cheapest
   - `normalize_registry()` - syncs SOURCE_OF_TRUTH.json
   - `validate_coverage()` - ensures 42/42 models priced

2. **Normalized all 42 models** in SOURCE_OF_TRUTH.json:
   - `rub_per_use == rub_per_gen` (ALWAYS)
   - `usd_per_use == usd_per_gen` (ALWAYS)
   - Example: grok-imagine/image-to-video: 19₽ → 19₽ (was 19₽ → 427.5₽)

3. **Updated FREE tier derivation**:
   - Deterministic: sorted by (price, alphabetically)
   - TOP-5 cheapest:
     1. z-image: 0.76₽
     2. recraft/remove-background: 0.95₽
     3. infinitalk/from-audio: 2.85₽
     4. google/imagen4: 3.80₽
     5. google/imagen4-fast: 3.80₽
   
   - **Changed from**: grok-imagine/text-to-image, google/nano-banana
   - **Reason**: 5 models tied at 3.80₽, alphabetical tie-breaking

**Files Modified**:
- `app/payments/pricing_contract.py` (NEW - 296 lines)
- `models/KIE_SOURCE_OF_TRUTH.json` (all 42 models normalized)
- `app/utils/config.py` (updated default FREE tier)
- `scripts/update_is_free_flags.py` (use pricing_contract)

### P1: Startup Validation

**Problem**:
- Validation used `calculate_kie_cost()` which was inconsistent
- FREE tier check failed on Render

**Solution**:
- `app/utils/startup_validation.py`: Use `pricing_contract.derive_free_tier()`
- Validation now checks against canonical pricing truth
- Passes locally ✅

**Files Modified**:
- `app/utils/startup_validation.py`

---

## 📊 CURRENT STATE

### Pricing System
- ✅ Single source: `pricing_source_truth.txt` (42 models)
- ✅ Formula: RUB = USD × 2.0 × 95.0
- ✅ Registry normalized: `rub_per_use == rub_per_gen`
- ✅ FREE tier: TOP-5 cheapest (deterministic)
- ✅ Validation: 42/42 coverage

### FREE Tier Models
| Rank | Model | Price |
|------|-------|-------|
| 1 | z-image | 0.76₽ |
| 2 | recraft/remove-background | 0.95₽ |
| 3 | infinitalk/from-audio | 2.85₽ |
| 4 | google/imagen4 | 3.80₽ |
| 5 | google/imagen4-fast | 3.80₽ |

### Price Examples (Before → After)
- sora-2-text-to-video: 380₽ → 598₽ ✅
- sora-2-image-to-video: 427.5₽ → 314₽ ✅
- grok-imagine/image-to-video: 427.5₽ → 19₽ ✅
- grok-imagine/text-to-video: 380₽ → 19₽ ✅
- grok-imagine/text-to-image: 47.5₽ → 3.8₽ ✅

---

## 🚀 RENDER DEPLOYMENT STEPS

### 1. Manual Deploy (REQUIRED)
Render needs manual deploy to pull latest code:
1. **Render Dashboard** → **454545** → **Manual Deploy**
2. Select: **"Clear build cache & deploy"**
3. Click: **"Deploy latest commit"**
4. Wait 3-5 minutes

### 2. Verify Logs
After deploy, check logs for:
```
✅ Models: 42 total, 42 enabled
✅ Models with valid pricing: 42
Expected FREE tier (TOP-5 cheapest): ['google/imagen4', 'google/imagen4-fast', 'infinitalk/from-audio', 'recraft/remove-background', 'z-image']
✅ FREE tier: 5 cheapest моделей корректны
✅ Validation passed
🚀 Starting webhook server...
```

### 3. Test in Telegram
- [ ] /start shows balance 0₽
- [ ] Free model (z-image) generates without charging
- [ ] Paid model shows correct price (e.g., grok-imagine/image-to-video: 19₽, not 427₽)
- [ ] On error: RQ-XXXX code shown + in Render logs

---

## 📝 NEXT STEPS (P2-P6)

### P2: Structured Logging
- [ ] Create `app/utils/gen_logger.py`
- [ ] Structured events: GEN_START, GEN_SUCCESS, GEN_FAIL
- [ ] Fields: request_id, user_id, model_id, task_id, price_rub, is_free, duration_ms, error_code
- [ ] All exceptions logged with stacktrace

### P3: UX Redesign
- [ ] /start: compact menu with balance
- [ ] Categories: pagination (8-10 per page)
- [ ] Model buttons: "Name — Price" or "Бесплатно"
- [ ] Confirmation: model, price, ETA, warning
- [ ] Error: short + "🆘 Код: RQ-XXXX" + "Повторить" button

### P4: Verify Scripts + Tests
- [ ] `scripts/verify_pricing_integrity.py`
- [ ] `tests/test_pricing_contract.py`
- [ ] `tests/test_free_tier.py`
- [ ] CI: GitHub Action

### P5: Remove Standby/Lock
- [ ] Check `main_render.py` entrypoint
- [ ] Remove singleton lock logic
- [ ] Add `/healthz` and `/readyz`

### P6: Admin Diagnostics
- [ ] 📉 Recent errors (already exists)
- [ ] 🧪 Smoke test FREE models
- [ ] Request ID search

---

## 🎯 SUCCESS CRITERIA

- [x] P0: Pricing consistency fixed (rub_per_gen == rub_per_use)
- [x] P1: Startup validation uses pricing_contract
- [ ] P2-P6: See Next Steps above
- [ ] Render deployment successful
- [ ] All 42 models visible and priced correctly
- [ ] FREE tier = TOP-5 cheapest (validated)
- [ ] No "200₽ bonus" by default
- [ ] Errors logged with request_id

---

## 💾 COMMITS

1. **a1e24f9**: 🔧 P0 FIX: Pricing consistency (rub_per_gen == rub_per_use)
   - Created pricing_contract.py
   - Normalized 42 models
   - Updated FREE tier

2. **3b2c3cd**: ✅ P1: Update startup validation with pricing_contract
   - Validation uses canonical pricing truth
   - FREE tier check passes

---

## 📞 SUPPORT

If Render deploy fails:
1. Check logs for exact error
2. Verify ENV variables removed (if needed)
3. Try "Clear build cache & deploy"
4. Check latest commit pulled (should be 3b2c3cd or later)

**Ready for Manual Deploy on Render** 🚀
