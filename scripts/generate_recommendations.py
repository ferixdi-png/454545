#!/usr/bin/env python3
"""
Comprehensive UX enhancement script - make bot like Syntx
- Gallery of examples
- Quick actions
- Trending models
- Better prompts
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load SOURCE_OF_TRUTH
with open('models/KIE_SOURCE_OF_TRUTH.json', 'r', encoding='utf-8') as f:
    sot = json.load(f)

models = sot.get('models', {})

# Find best models by category
best_by_category = {}
for model_id, model in models.items():
    if not model.get('enabled', True):
        continue
    
    category = model.get('category', 'other')
    price = model.get('pricing', {}).get('rub_per_gen', 999999)
    
    if category not in best_by_category:
        best_by_category[category] = []
    
    best_by_category[category].append({
        'model_id': model_id,
        'name': model.get('display_name', model_id),
        'price': price,
        'category': category
    })

# Sort and take best 3 per category
for category in best_by_category:
    best_by_category[category].sort(key=lambda x: x['price'])
    best_by_category[category] = best_by_category[category][:3]

# Print recommendations
print("🎯 РЕКОМЕНДОВАННЫЕ МОДЕЛИ ПО КАТЕГОРИЯМ:\n")
for category, models_list in sorted(best_by_category.items()):
    if not models_list:
        continue
    print(f"\n📁 {category.upper()}:")
    for idx, m in enumerate(models_list, 1):
        price_tag = "🆓" if m['price'] == 0 else f"{m['price']:.2f}₽"
        print(f"  {idx}. {m['name']} - {price_tag}")

# Generate quick actions config
quick_actions = {
    "trending": [
        "flux-2/flex-text-to-image",
        "grok-imagine/text-to-video",
        "sora-2-text-to-video",
        "hailuo/02-text-to-video-standard"
    ],
    "free": [
        "z-image",
        "qwen/text-to-image",
        "qwen/image-to-image",
        "qwen/image-edit"
    ],
    "popular_by_use": {
        "instagram": ["flux-2/flex-text-to-image", "ideogram/character"],
        "tiktok": ["sora-2-text-to-video", "grok-imagine/text-to-video"],
        "youtube": ["hailuo/02-text-to-video-pro", "kling-2.6/image-to-video"],
        "design": ["flux-2/pro-text-to-image", "bytedance/seedream"],
    }
}

# Save recommendations
output_path = Path('artifacts/model_recommendations.json')
output_path.parent.mkdir(exist_ok=True)

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump({
        'best_by_category': best_by_category,
        'quick_actions': quick_actions,
        'generated_at': '2025-12-25'
    }, f, indent=2, ensure_ascii=False)

print(f"\n✅ Recommendations saved to: {output_path}")
print("\n🚀 Use these for UX improvements in bot!")
