#!/usr/bin/env python3
"""
РЕАЛЬНЫЕ ЦЕНЫ с https://kie.ai/pricing (по скриншоту пользователя)
ФОРМУЛА: USD × 79 × 2 = RUB
"""
import json
from pathlib import Path

# РЕАЛЬНЫЕ ЦЕНЫ с pricing page (по скриншоту)
REAL_PRICES_USD = {
    # Image models (с pricing page screenshot)
    'qwen/z-image': 0.004,  # 0.8 credits = $0.004
    'google/nano-banana-pro': {
        '1/2K': 0.09,  # 18.0 credits
        '4K': 0.12,    # 24.0 credits
    },
    'flux-2/pro': 0.025,  # Black Forest Labs flux-2 pro, 5.0 credits
    
    # Video models (с pricing page screenshot)
    'wan/2.5': 0.3,  # wan 2.5, image-to-video, 60.0 credits = $0.3
    'google/veo-3.1': {
        'fast': 0.3,  # 60.0 credits
        'text-to-video': 1.2,  # Google veo 3.1, text-to-video, Fast: 60.0 credits
    },
    
    # Grok models
    'grok-imagine/image-to-video': 0.1,  # 6.0s: 20.0 credits = $0.1
    'grok-imagine/text-to-video': 0.1,   # 6.0s: 20.0 credits = $0.1
    
    # Известные цены из предыдущего pricing_table
    'elevenlabs/speech-to-text': 3.0,
    'elevenlabs/audio-isolation': 5.0,
    'elevenlabs/text-to-speech': 5.0,
    'elevenlabs/text-to-speech-multilingual-v2': 5.0,
    'elevenlabs/sound-effect': 8.0,
    'elevenlabs/sound-effect-v2': 8.0,
    'google/nano-banana': 8.0,
    'recraft/remove-background': 8.0,
    'bytedance/seedream': 10.0,
    'flux-2/flex-text-to-image': 10.0,
}

# Формула
EXCHANGE_RATE = 79.0
MARKUP = 2.0

def convert_to_pricing(usd: float, is_free: bool = False) -> dict:
    """Конвертация USD в полный pricing объект"""
    rub = usd * EXCHANGE_RATE * MARKUP if not is_free else 0
    
    return {
        'usd_per_gen': usd,
        'rub_per_gen': round(rub, 2),
        'credits_per_gen': usd * 200,  # 1 USD = 200 credits
        'is_free': is_free,
        'source': 'kie_pricing_page_real'
    }

def main():
    print("=" * 80)
    print("💰 REAL PRICES FROM KIE.AI/PRICING")
    print("=" * 80)
    
    pricing_map = {}
    
    for model_id, price in REAL_PRICES_USD.items():
        if isinstance(price, dict):
            # Используем среднее для моделей с вариантами
            avg_price = sum(price.values()) / len(price.values())
            pricing_map[model_id] = convert_to_pricing(avg_price)
            print(f"{model_id}: ${avg_price:.3f} → {pricing_map[model_id]['rub_per_gen']}₽")
        else:
            pricing_map[model_id] = convert_to_pricing(price)
            print(f"{model_id}: ${price:.3f} → {pricing_map[model_id]['rub_per_gen']}₽")
    
    # Пометить free модели
    free_models = [
        'elevenlabs/speech-to-text',
        'elevenlabs/audio-isolation',
        'elevenlabs/text-to-speech',
        'elevenlabs/text-to-speech-multilingual-v2',
        'elevenlabs/sound-effect'
    ]
    
    for mid in free_models:
        if mid in pricing_map:
            pricing_map[mid]['is_free'] = True
            print(f"  🆓 {mid} marked as FREE")
    
    # Сохраняем
    output = Path('artifacts/real_prices_from_screenshot.json')
    with open(output, 'w') as f:
        json.dump(pricing_map, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Saved: {output}")
    print(f"   Models: {len(pricing_map)}")
    
    # Показываем примеры
    print(f"\n📊 EXAMPLES:")
    print(f"   z-image: $0.004 × 79 × 2 = {0.004 * 79 * 2:.2f}₽")
    print(f"   nano-banana-pro: $0.105 × 79 × 2 = {0.105 * 79 * 2:.2f}₽")
    print(f"   flux-2/pro: $0.025 × 79 × 2 = {0.025 * 79 * 2:.2f}₽")

if __name__ == '__main__':
    main()
