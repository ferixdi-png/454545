# 🤖 Model Registry Documentation

## Overview

This bot supports **22 AI models** from Kie.ai platform, organized by task-oriented categories.

**Source of Truth**: `models/kie_source_of_truth.json` (version 3.0)

---

## Model Categories

Models are organized by **what users want to create**, not by technical type.

### 🎨 Creative (8 models)

User intent: "I want to create image/logo/design"

| Model | Display Name | Price | Description |
|-------|--------------|-------|-------------|
| z-image | Генератор Изображений | 4.72₽ | Fast image generation |
| flux-dev | FLUX Pro | 15.72₽ | Professional quality images |
| flux-schnell | FLUX Fast | 7.86₽ | Quick image generation |
| stable-diffusion-3.5 | Stable Diffusion 3.5 | 7.86₽ | Classic SD model |
| ideogram-v2 | Ideogram v2 | 7.86₽ | Design-focused |
| ideogram-v2-turbo | Ideogram Turbo | 3.93₽ | Fast design mode |

### 🎵 Music (7 models)

User intent: "I want to create music/song/sound"

| Model | Display Name | Price | Description |
|-------|--------------|-------|-------------|
| suno-generate-lyrics | Тексты Песен | 0.31₽ | Generate song lyrics |
| suno-convert-to-wav | Конвертер WAV | 0.31₽ | Convert to WAV format |
| elevenlabs-sound-effects | Звуковые Эффекты | 0.19₽ | Create sound effects |
| suno-v4 | Suno v4 | 7.86₽ | Full song generation |
| mureka-music-generator | Mureka Music | 0.78₽ | Background music |

### 🎙️ Voice (5 models)

User intent: "I want to create voice/speech/narration"

| Model | Display Name | Price | Description |
|-------|--------------|-------|-------------|
| elevenlabs-text-to-speech | Озвучка Текста | 1.57₽ | Text to speech |
| elevenlabs-speech-to-speech | Конвертер Голоса | 7.86₽ | Voice conversion |
| elevenlabs-audio-isolation | Изоляция Голоса | 0.16₽ | Remove background noise |

### 🎬 Video (2 models)

User intent: "I want to create video/animation"

| Model | Display Name | Price | Description |
|-------|--------------|-------|-------------|
| kling-image-to-video | Видео из Фото | 78.59₽ | Animate images |
| kling-text-to-video | Генератор Видео | 62.87₽ | Text to video |

**Note**: Video models are most expensive (60-80₽ per generation).

---

## FREE Tier Models (Top 5 Cheapest)

Always free with daily limits (5/day, 2/hour):

1. **elevenlabs-audio-isolation** - 0.16₽ (Audio noise removal)
2. **elevenlabs-sound-effects** - 0.19₽ (Sound effects)
3. **suno-convert-to-wav** - 0.31₽ (Audio conversion)
4. **suno-generate-lyrics** - 0.31₽ (Lyric generation)
5. **recraft-crisp-upscale** - 0.39₽ (Image upscaling)

**Total FREE value**: 1.36₽ per full use (all 5 models)

---

## Source of Truth Format

### Structure

```json
{
  "version": "3.0",
  "last_updated": "2024-12-24T00:00:00Z",
  "models": [
    {
      "model_id": "unique-kebab-case-id",
      "api_endpoint": "vendor/model-name",
      "display_name": "User-Friendly Name",
      "category": "creative|music|voice|video",
      "vendor": "openai|anthropic|elevenlabs|etc",
      "pricing": {
        "usd_per_use": 0.03,
        "rub_per_use": 4.72
      },
      "input_schema": {
        "param_name": {
          "type": "string|integer|float|boolean|url",
          "required": true|false,
          "default": "value",
          "min": 1,
          "max": 100,
          "description": "What this parameter does"
        }
      },
      "metadata": {
        "task_label": "What user wants to do",
        "emoji": "🎨",
        "description_short": "One-liner",
        "description_full": "Detailed explanation"
      }
    }
  ]
}
```

### Field Descriptions

**model_id**
- Unique identifier (kebab-case)
- Used in database, logs, callbacks
- **Immutable** - never change existing IDs

**api_endpoint**
- Kie.ai API path (e.g., `openai/gpt-4o`)
- Found in Kie.ai docs
- Used for actual API calls

**display_name**
- User-facing name (Russian)
- Shows in bot menus
- Keep short (< 30 chars)

**category**
- Task-oriented: `creative`, `music`, `voice`, `video`
- **NOT** technical: ~~`text-to-image`~~, ~~`llm`~~
- Determines menu placement

**vendor**
- API provider: `openai`, `anthropic`, `elevenlabs`, `stability`, etc.
- For logging/debugging only

**pricing.usd_per_use**
- Kie.ai USD price (from their pricing page)
- Used to calculate RUB price

**pricing.rub_per_use**
- Final price shown to users
- Formula: `usd_per_use × 78.59 × 2.0`

**input_schema**
- **Flat format** (no nesting)
- Each parameter is top-level key
- **Required fields**: `type`, `required`

**metadata**
- Optional descriptive data
- Not used in runtime logic
- Helps admins/partners understand model

---

## Input Schema Format

### Flat Format (Current)

```json
{
  "input_schema": {
    "prompt": {
      "type": "string",
      "required": true,
      "description": "Text prompt for generation"
    },
    "width": {
      "type": "integer",
      "required": false,
      "default": 1024,
      "min": 512,
      "max": 2048
    },
    "seed": {
      "type": "integer",
      "required": false,
      "description": "Random seed for reproducibility"
    }
  }
}
```

**Why flat?**
- Simple to parse
- Easy to validate
- No nested complexity

### Supported Types

**string**: Text input
```json
{"prompt": {"type": "string", "required": true}}
```

**integer**: Whole numbers
```json
{"steps": {"type": "integer", "min": 1, "max": 100, "default": 50}}
```

**float**: Decimal numbers
```json
{"temperature": {"type": "float", "min": 0.0, "max": 2.0, "default": 1.0}}
```

**boolean**: True/False
```json
{"hd_mode": {"type": "boolean", "default": false}}
```

**url**: File URL (image, audio, video)
```json
{"image_url": {"type": "url", "required": true}}
```

### Example: Complete Model

```json
{
  "model_id": "z-image",
  "api_endpoint": "z-image/generate",
  "display_name": "Генератор Изображений",
  "category": "creative",
  "vendor": "z-image",
  "pricing": {
    "usd_per_use": 0.03,
    "rub_per_use": 4.72
  },
  "input_schema": {
    "prompt": {
      "type": "string",
      "required": true,
      "description": "Описание желаемого изображения"
    },
    "negative_prompt": {
      "type": "string",
      "required": false,
      "description": "Что не должно быть на изображении"
    },
    "width": {
      "type": "integer",
      "required": false,
      "default": 1024,
      "min": 512,
      "max": 2048
    },
    "height": {
      "type": "integer",
      "required": false,
      "default": 1024,
      "min": 512,
      "max": 2048
    },
    "steps": {
      "type": "integer",
      "required": false,
      "default": 50,
      "min": 1,
      "max": 100
    },
    "seed": {
      "type": "integer",
      "required": false,
      "description": "Для воспроизводимости результата"
    }
  },
  "metadata": {
    "task_label": "создать изображение",
    "emoji": "🎨",
    "description_short": "Быстрая генерация изображений",
    "description_full": "Создавайте уникальные изображения из текстовых описаний"
  }
}
```

---

## Adding New Models

### Step 1: Get Model Info

From Kie.ai documentation:

1. **Model ID**: What to call it internally (e.g., `new-cool-model`)
2. **API Endpoint**: Kie.ai path (e.g., `vendor/new-cool-model`)
3. **Pricing**: USD price per use (e.g., $0.05)
4. **Parameters**: What inputs it accepts

### Step 2: Calculate RUB Price

```python
usd_price = 0.05
fx_rate = 78.59  # Current USD/RUB
markup = 2.0

rub_price = usd_price * fx_rate * markup
# 0.05 × 78.59 × 2.0 = 7.86₽
```

### Step 3: Create Input Schema

List all parameters:

```json
{
  "prompt": {
    "type": "string",
    "required": true
  },
  "style": {
    "type": "string",
    "required": false,
    "default": "realistic"
  }
}
```

### Step 4: Choose Category

Map user intent to category:

- "I want to create logo" → `creative`
- "I want to create song" → `music`
- "I want to create voice" → `voice`
- "I want to create video" → `video`

### Step 5: Add to Source of Truth

Edit `models/kie_source_of_truth.json`:

```json
{
  "models": [
    // ... existing models ...
    {
      "model_id": "new-cool-model",
      "api_endpoint": "vendor/new-cool-model",
      "display_name": "Крутая Модель",
      "category": "creative",
      "vendor": "vendor-name",
      "pricing": {
        "usd_per_use": 0.05,
        "rub_per_use": 7.86
      },
      "input_schema": {
        "prompt": {
          "type": "string",
          "required": true
        }
      }
    }
  ]
}
```

### Step 6: Verify

Run validation:

```bash
python scripts/verify_project.py
```

Checks:
- ✅ Valid JSON syntax
- ✅ All required fields present
- ✅ No duplicate model_ids
- ✅ Pricing formula correct
- ✅ Input schema valid

### Step 7: Test

```bash
# Restart bot
# In Telegram: /start → Browse Models → Your Category
# Should see new model
```

### Step 8: Commit

```bash
git add models/kie_source_of_truth.json
git commit -m "feat: add new-cool-model (7.86₽)"
git push
```

Render auto-deploys in ~2 minutes.

---

## Model Registry API

### Load Models

```python
from app.kie.registry import get_registry

registry = get_registry()
# Loads models/kie_source_of_truth.json

# Get all models
all_models = registry.get_all_models()

# Get by category
creative_models = registry.get_models_by_category("creative")

# Get specific model
z_image = registry.get_model("z-image")
```

### Check FREE Tier

```python
from app.free.manager import is_free_model

if is_free_model("elevenlabs-audio-isolation"):
    print("This model is FREE!")
```

### Get Price

```python
price_rub = registry.get_price("z-image")
# Returns: 4.72
```

### Validate Input

```python
from app.kie.validator import validate_input

params = {
    "prompt": "a beautiful sunset",
    "width": 1024
}

is_valid = validate_input("z-image", params)
# Returns: True (all required params present)
```

---

## Model Coverage

### By Category

| Category | Models | FREE | Paid | Avg Price |
|----------|--------|------|------|-----------|
| Creative | 8 | 1 | 7 | 8.64₽ |
| Music | 7 | 3 | 4 | 2.31₽ |
| Voice | 5 | 2 | 3 | 3.20₽ |
| Video | 2 | 0 | 2 | 70.73₽ |

### By Price Tier

| Tier | Range | Count | % of Total |
|------|-------|-------|------------|
| FREE | 0.16-0.39₽ | 5 | 23% |
| Budget | 0.78-3.93₽ | 6 | 27% |
| Standard | 4.72-15.72₽ | 8 | 36% |
| Premium | 62.87-78.59₽ | 3 | 14% |

### By Vendor

| Vendor | Models | Categories |
|--------|--------|------------|
| elevenlabs | 5 | music, voice |
| suno | 4 | music |
| kling | 2 | video |
| flux | 2 | creative |
| ideogram | 2 | creative |
| recraft | 2 | creative |
| openai | 1 | creative |
| others | 4 | various |

---

## Input Schema Patterns

### Text-to-Image

```json
{
  "prompt": {"type": "string", "required": true},
  "negative_prompt": {"type": "string", "required": false},
  "width": {"type": "integer", "default": 1024},
  "height": {"type": "integer", "default": 1024},
  "steps": {"type": "integer", "default": 50},
  "seed": {"type": "integer", "required": false}
}
```

### Text-to-Speech

```json
{
  "text": {"type": "string", "required": true},
  "voice_id": {"type": "string", "required": true},
  "stability": {"type": "float", "default": 0.5},
  "similarity_boost": {"type": "float", "default": 0.75}
}
```

### Image-to-Video

```json
{
  "image_url": {"type": "url", "required": true},
  "duration": {"type": "integer", "default": 5, "max": 10},
  "mode": {"type": "string", "default": "standard"}
}
```

### Audio Processing

```json
{
  "audio_url": {"type": "url", "required": true},
  "output_format": {"type": "string", "default": "wav"}
}
```

---

## Maintenance Tasks

### Weekly: Sync Pricing

```bash
python scripts/kie_sync_pricing.py
```

Updates USD prices from Kie.ai, recalculates RUB prices.

### Monthly: Audit Coverage

```bash
python scripts/audit_model_coverage.py
```

Checks:
- All models have input_schema
- All models tested recently
- No orphaned models
- Category distribution balanced

### Quarterly: User Preferences

```bash
python scripts/analyze_model_usage.py
```

Shows:
- Most used models
- Least used models (candidates for removal)
- Category popularity
- FREE vs Paid usage ratio

---

## Troubleshooting

### Model Not Showing in Bot

**Check 1**: Model in source of truth?
```bash
grep "model-id" models/kie_source_of_truth.json
```

**Check 2**: Category valid?
```python
category in ['creative', 'music', 'voice', 'video']
```

**Check 3**: Bot restarted?
```bash
# Models loaded at startup only
# Restart required after changes
```

### Generation Fails

**Check 1**: API endpoint correct?
```python
# Test directly
curl -X POST https://api.kie.ai/v1/vendor/model \
  -H "Authorization: Bearer $KIE_API_KEY"
```

**Check 2**: Input schema matches Kie.ai?
```python
# Compare with Kie.ai docs
# Especially parameter names (case-sensitive)
```

**Check 3**: Pricing blocking?
```python
# Check if model is FREE but not in FREE list
# Or balance insufficient for paid model
```

### FREE Tier Not Working

**Check 1**: Model in FREE list?
```python
from app.free.manager import get_free_models
print(get_free_models())  # Should be cheapest 5
```

**Check 2**: Limits reached?
```sql
SELECT * FROM free_usage 
WHERE user_id = ? AND model_id = ?
ORDER BY created_at DESC LIMIT 10;
```

**Check 3**: Database table exists?
```bash
python scripts/verify_project.py
# Checks free_models and free_usage tables
```

---

## Best Practices

### DO ✅

- Use kebab-case for model_id (`my-cool-model`)
- Keep display_name short and descriptive
- Always specify both USD and RUB prices
- Include all required parameters in input_schema
- Test model before adding to production
- Document parameter descriptions
- Use task-oriented categories

### DON'T ❌

- Change existing model_ids (breaks database references)
- Use technical categories (`llm`, `diffusion`)
- Skip input_schema validation
- Hardcode prices in code (use source of truth)
- Forget to sync FREE tier after price changes
- Add models without testing API endpoint
- Use nested input_schema

---

## Examples

### Full Model Definitions

**Simple (Sound Effects)**
```json
{
  "model_id": "elevenlabs-sound-effects",
  "api_endpoint": "elevenlabs/sound-effects",
  "display_name": "Звуковые Эффекты",
  "category": "music",
  "vendor": "elevenlabs",
  "pricing": {
    "usd_per_use": 0.0012,
    "rub_per_use": 0.19
  },
  "input_schema": {
    "text": {
      "type": "string",
      "required": true,
      "description": "Описание звука"
    },
    "duration": {
      "type": "float",
      "default": 5.0,
      "max": 22.0
    }
  }
}
```

**Complex (Image Generation)**
```json
{
  "model_id": "flux-dev",
  "api_endpoint": "black-forest-labs/flux-1.1-pro",
  "display_name": "FLUX Pro",
  "category": "creative",
  "vendor": "black-forest-labs",
  "pricing": {
    "usd_per_use": 0.1,
    "rub_per_use": 15.72
  },
  "input_schema": {
    "prompt": {
      "type": "string",
      "required": true
    },
    "width": {
      "type": "integer",
      "default": 1024,
      "min": 256,
      "max": 2048
    },
    "height": {
      "type": "integer",
      "default": 1024,
      "min": 256,
      "max": 2048
    },
    "guidance_scale": {
      "type": "float",
      "default": 7.5,
      "min": 1.0,
      "max": 20.0
    },
    "num_inference_steps": {
      "type": "integer",
      "default": 50,
      "min": 1,
      "max": 100
    },
    "seed": {
      "type": "integer",
      "required": false
    }
  }
}
```

---

## References

- **Source File**: `models/kie_source_of_truth.json`
- **Registry Code**: `app/kie/registry.py`
- **Validation Script**: `scripts/verify_project.py`
- **Kie.ai Docs**: https://kie.ai/docs
- **Pricing Sync**: `scripts/kie_sync_pricing.py`

---

**Last Updated**: 2024-12-24  
**Version**: 1.0  
**Models Count**: 22  
**FREE Models**: 5  
**Status**: Production Ready ✅
