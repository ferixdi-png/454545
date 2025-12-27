#!/usr/bin/env python3
"""
СРОЧНОЕ ИСПРАВЛЕНИЕ ЦЕН
Применяет реальные USD цены из parse_all_models к SOURCE_OF_TRUTH
"""
import json

USD_TO_RUB = 79.0  # ФИКСИРОВАННЫЙ КУРС

# Маппинг model_id SOT → manual_overrides
PRICE_MAPPING = {
    # Veo 3.1
    "veo3_fast": "google-veo-31-text-to-video-fast",  # $0.3
    
    # Elevenlabs (правильные model_id с слешами!)
    "elevenlabs/speech-to-text": "elevenlabs-speech-to-text",  # $0.0175
    "elevenlabs/text-to-speech-turbo-2-5": "elevenlabs-text-to-speech-turbo-25",  # $0.03
    "elevenlabs/text-to-speech-multilingual-v2": "elevenlabs-text-to-speech-multilingual-v2",  # $0.06
    "elevenlabs/sound-effect-v2": "elevenlabs-sound-effect-v2",  # $0.0012
    "elevenlabs/audio-isolation": "elevenlabs-audio-isolation",  # $0.001
    
    # Bytedance
    "bytedance/seedream": "bytedance-seedream-text-to-image",  # $0.0175
    "bytedance/seedream-v4-text-to-image": "bytedance-seedream-40-text-to-image",  # $0.025
    "bytedance/seedream-v4-edit": "bytedance-seedream-45-image-edit-basichigh-00s",  # $0.0325
    
    # Qwen
    "qwen/text-to-image": "qwen-image-text-to-image",  # $0.02
    "qwen/image-to-image": "qwen-image-image-to-image",  # $0.02
    "qwen/image-edit": "qwen-image-edit-image-to-image",  # $0.03
    "z-image": "qwen-z-image-text-to-image-10s",  # $0.004
}

def load_manual_overrides():
    """Загрузить спарсенные USD цены"""
    with open('/workspaces/5656/models/manual_overrides.json') as f:
        return {m['model_id']: m['pricing']['usd_per_run'] for m in json.load(f)}

def load_auto_mapping():
    """Загрузить автоматический маппинг"""
    try:
        with open('/workspaces/5656/scripts/price_mapping.json') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def main():
    # Загрузка
    with open('/workspaces/5656/models/KIE_SOURCE_OF_TRUTH.json') as f:
        sot = json.load(f)
    
    manual_prices = load_manual_overrides()
    auto_mapping = load_auto_mapping()
    
    # Объединение маппингов (вручную + авто)
    full_mapping = {**auto_mapping, **PRICE_MAPPING}  # Manual overrides имеют приоритет
    
    models = sot.get('models', {})
    updated = 0
    skipped = 0
    
    print("🔧 ПОЛНОЕ ИСПРАВЛЕНИЕ ЦЕН (72 модели)\n")
    
    for model_id in models.keys():
        # Пропустить FREE модели
        if models[model_id].get('pricing', {}).get('is_free', False):
            print(f"⏭️  {model_id} - FREE (пропущено)")
            skipped += 1
            continue
        
        override_id = full_mapping.get(model_id)
        
        if not override_id or override_id not in manual_prices:
            print(f"⚠️  {model_id} - нет маппинга")
            skipped += 1
            continue
        
        # Новая USD цена
        new_usd = manual_prices[override_id]
        
        # Старые значения
        old_pricing = models[model_id].get('pricing', {})
        old_usd = old_pricing.get('usd_per_gen', 0)
        
        # Новые значения
        new_rub = round(new_usd * USD_TO_RUB, 2)
        new_credits = new_usd / 0.005  # 1 credit = $0.005
        
        # Обновление
        models[model_id]['pricing']['usd_per_gen'] = new_usd
        models[model_id]['pricing']['rub_per_gen'] = new_rub
        models[model_id]['pricing']['credits_per_gen'] = new_credits
        
        if abs(old_usd - new_usd) > 0.001:  # Только если изменилось
            print(f"✅ {model_id}: ${old_usd:.4f} → ${new_usd:.4f} (RUB: {new_rub:.2f})")
            updated += 1
    
    # Сохранение
    with open('/workspaces/5656/models/KIE_SOURCE_OF_TRUTH.json', 'w') as f:
        json.dump(sot, f, indent=2, ensure_ascii=False)
    
    print(f"\n📊 Статистика:")
    print(f"  ✅ Обновлено: {updated}")
    print(f"  ⏭️  Пропущено: {skipped}")
    print(f"  📦 Всего моделей: {len(models)}")
    
    # Финальная валидация
    print("\n✅ ВАЛИДАЦИЯ (примеры с наценкой ×2):")
    for model_id in ['veo3_fast', 'elevenlabs/speech-to-text', 'z-image']:
        if model_id in models:
            p = models[model_id]['pricing']
            user_price = p['rub_per_gen'] * 2
            print(f"  {model_id}: {p['rub_per_gen']:.2f} RUB (Kie) → {user_price:.2f} RUB (user)")

if __name__ == '__main__':
    main()
