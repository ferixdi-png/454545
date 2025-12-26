# 🚨 URGENT: Render Deployment Fix

## Problem

Render deployment fails with validation error:
```
❌ FREE tier не совпадает с TOP-5 cheapest
expected=['z-image', 'recraft/remove-background', 'infinitalk/from-audio', 'grok-imagine/text-to-image', 'google/nano-banana']
actual=['flux-2/pro-text-to-image', 'grok-imagine/text-to-image', 'grok-imagine/upscale', 'seedream/4.5-text-to-image', 'sora-watermark-remover']
```

## Root Cause

Render has old ENV variable `FREE_TIER_MODEL_IDS` with outdated list that overrides code default.

## Fix (2 options)

### Option 1: Update ENV Variable (Recommended)

1. Go to Render Dashboard → 454545 → Environment
2. Find `FREE_TIER_MODEL_IDS`
3. Update to:
   ```
   z-image,recraft/remove-background,infinitalk/from-audio,grok-imagine/text-to-image,google/nano-banana
   ```
4. Click "Save Changes"
5. Render will auto-redeploy

### Option 2: Delete ENV Variable (Use Code Default)

1. Go to Render Dashboard → 454545 → Environment
2. Find `FREE_TIER_MODEL_IDS`
3. Click DELETE
4. Save
5. Code will use default from `app/utils/config.py` (line 126)

## Verification

After deploy, check logs for:
```
✅ FREE tier matches TOP-5 cheapest
✅ Bot is READY (webhook mode)
```

## Updated FREE Tier Models

| # | Model | Price | Why Free |
|---|-------|-------|----------|
| 1 | z-image | 0.76₽ | Cheapest (#1) |
| 2 | recraft/remove-background | 0.95₽ | Cheapest (#2) |
| 3 | infinitalk/from-audio | 2.85₽ | Cheapest (#3) |
| 4 | grok-imagine/text-to-image | 3.80₽ | Cheapest (#4) |
| 5 | google/nano-banana | 3.80₽ | Cheapest (#5) |

**Old incorrect list** (removed):
- flux-2/pro-text-to-image (6.65₽) ❌ Not in TOP-5
- grok-imagine/upscale (9.50₽) ❌ Not in TOP-5
- seedream/4.5-text-to-image (6.17₽) ❌ Not in TOP-5
- sora-watermark-remover (9.50₽) ❌ Not in TOP-5

## After Fix

Bot will start successfully and users will see:
- ✅ Correct FREE tier models (5 cheapest)
- ✅ Correct pricing for all 42 models
- ✅ No validation errors
