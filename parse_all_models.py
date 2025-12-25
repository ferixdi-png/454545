#!/usr/bin/env python3
"""
Парсер ВСЕХ моделей из таблицы Kie.ai
"""
import json
import re

RAW_DATA = """
wan 2.5, image-to-video, default-5.0s-720p|$0.3
Google veo 3.1, text-to-video, Fast|$0.3
grok-imagine, image-to-video, 6.0s|$0.1
grok-imagine, text-to-video, 6.0s|$0.1
Google nano banana pro, 1/2K|$0.09
Google nano banana pro, 4K|$0.12
Qwen z-image, text-to-image, 1.0s|$0.004
Black Forest Labs flux-2 pro, image to image, 1.0s-1K|$0.025
kling 2.6, image-to-video, without audio-5.0s|$0.275
wan 2.6, video-to-video, 15.0s-1080p|$1.575
Runway Aleph|$0.55
wan 2.2 Animate, 2.2 Animate Replace, 1.0s-720p|$0.0625
wan 2.2 Animate, 2.2 Animate Replace, 1.0s-580p|$0.0475
wan 2.2 Animate, 2.2 Animate Replace, 1.0s-480p|$0.03
Midjourney, image-to-image, fast|$0.04
Midjourney, image-to-image, turbo|$0.08
Midjourney, image-to-video|$0.3
Midjourney, text-to-image, fast|$0.04
Midjourney, text-to-image, turbo|$0.08
Midjourney, image-to-image, relaxed|$0.015
google imagen4, text-to-image, default|$0.04
Midjourney, text-to-image, relaxed|$0.015
google imagen4, text-to-image, Fast|$0.02
wan 2.2, image-to-video, 5.0s-480p|$0.2
google imagen4, text-to-image, Ultra|$0.06
wan 2.2, image-to-video, 5.0s-720p|$0.4
wan 2.2, image-to-video, 5.0s-580p|$0.3
wan 2.2, text-to-video, 5.0s-580p|$0.3
wan 2.2, text-to-video, 5.0s-480p|$0.2
ideogram v3-remix, image-to-image, BALANCED|$0.035
ideogram v3-remix, image-to-image, QUALITY|$0.05
wan 2.2, text-to-video, 5.0s-720p|$0.4
ideogram v3-edit, image-to-image, QUALITY|$0.05
ideogram v3-remix, image-to-image, TURBO|$0.0175
ideogram v3-edit, image-to-image, BALANCED|$0.035
ideogram v3, text-to-image, QUALITY|$0.05
ideogram v3-edit, image-to-image, TURBO|$0.0175
ideogram v3, text-to-image, TURBO|$0.0175
ideogram v3, text-to-image, BALANCED|$0.035
Kling 2.1, video-generation, Pro-10.0s|$0.5
Kling 2.1, text-to-video, Master-5.0s|$0.8
Kling 2.1, text-to-video, Master-10.0s|$1.6
Kling 2.1, video-generation, Standard-5.0s|$0.125
Kling 2.1, video-generation, Standard-10.0s|$0.25
Kling 2.1, video-generation, Pro-5.0s|$0.25
Kling 2.1, image-to-video, Master-5.0s|$0.8
Kling 2.1, image-to-video, Master-10.0s|$1.6
Bytedance Seedance 1.0, image-to-video, Pro Fast-5.0s-1080p|$0.18
Bytedance Seedance 1.0, image-to-video, Pro Fast-10.0s-1080p|$0.36
Bytedance Seedance 1.0, image-to-video, Pro Fast-5.0s-720p|$0.08
Bytedance Seedance 1.0, image-to-video, Pro Fast-10.0s-720p|$0.18
Bytedance Seedance 1.0, text-to-video, Pro-10.0s-720p|$0.3
Bytedance Seedance 1.0, text-to-video, Pro-10.0s-1080p|$0.7
Bytedance Seedance 1.0, text-to-video, Lite-5.0s-720p|$0.15
Bytedance Seedance 1.0, text-to-video, Lite-5.0s-1080p|$0.35
Bytedance Seedance 1.0, text-to-video, Pro-10.0s-480p|$0.14
Bytedance Seedance 1.0, text-to-video, Lite-5.0s-480p|$0.07
Bytedance Seedance 1.0, image-to-video, Pro-10.0s-480p|$0.14
Bytedance Seedance 1.0, image-to-video, Pro-10.0s-720p|$0.3
Bytedance Seedance 1.0, image-to-video, Pro-10.0s-1080p|$0.7
Bytedance Seedance 1.0, image-to-video, Pro-5.0s-1080p|$0.35
Bytedance Seedance 1.0, image-to-video, Pro-5.0s-480p|$0.07
Bytedance Seedance 1.0, image-to-video, Pro-5.0s-720p|$0.15
Bytedance Seedance 1.0, image-to-video, Lite-10.0s-480p|$0.1
Bytedance Seedance 1.0, image-to-video, Lite-10.0s-720p|$0.225
Bytedance Seedance 1.0, image-to-video, Lite-10.0s-1080p|$0.5
Bytedance Seedance 1.0, image-to-video, Lite-5.0s-1080p|$0.25
Bytedance Seedance 1.0, image-to-video, Lite-5.0s-480p|$0.05
Bytedance Seedance 1.0, image-to-video, Lite-5.0s-720p|$0.1125
ideogram character, image-to-image, BALANCED|$0.09
ideogram character, image-to-image, QUALITY|$0.12
ideogram character-remix, image-to-image, BALANCED|$0.09
ideogram character-remix, image-to-image, QUALITY|$0.12
ideogram character, image-to-image, TURBO|$0.06
ideogram character-remix, image-to-image, TURBO|$0.06
ideogram character-edit, image-to-image, QUALITY|$0.12
Qwen image-edit, image-to-image|$0.03
ideogram character-edit, image-to-image, TURBO|$0.06
ideogram character-edit, image-to-image, BALANCED|$0.09
Suno, convert-to-wav-format|$0.002
Suno, Generate Lyrics|$0.002
Suno, upload-and-cover-audio|$0.06
Suno, create-music-video|$0.06
Suno, upload-and-extend-audio|$0.01
Suno, add-instrumental|$0.06
Suno, Generate Music|$0.06
Suno, Extend Music|$0.06
Suno, add-vocals|$0.06
Runway, text-to-video, 5.0s-720p|$0.06
Runway, text-to-video, 10.0s-720p|$0.15
Runway, text-to-video, 5.0s-1080p|$0.15
Runway, image-to-video, 5.0s-720p|$0.06
Runway, image-to-video, 10.0s-720p|$0.15
Runway, image-to-video, 5.0s-1080p|$0.15
Google nano banana, text-to-image|$0.02
Google nano banana edit, image-to-image|$0.02
Qwen Image, text-to-image|$0.02
ByteDance Seedream, text-to-image|$0.0175
Qwen Image, image-to-image|$0.02
Wan 2.2 A14B Turbo API Speech to Video, 480p|$0.06
Elevenlabs Text to Speech, turbo 2.5|$0.03
Wan 2.2 A14B Turbo API Speech to Video, 720p|$0.12
Wan 2.2 A14B Turbo API Speech to Video, 580p|$0.09
Elevenlabs Sound Effect V2|$0.0012
Elevenlabs Speech to Text|$0.0175
Elevenlabs Text to Speech, multilingual v2|$0.06
Ideogram V3 Reframe, image to image, Quality|$0.05
Elevenlabs Audio Isolation|$0.001
Ideogram V3 Reframe, image to image, Balanced|$0.035
Recraft Crisp Upscale, image to image|$0.0025
Ideogram V3 Reframe, image to image, Turbo|$0.0175
MeiGen-AI InfiniteTalk, lip sync, up to 15 secondss-480p|$0.015
MeiGen-AI InfiniteTalk, lip sync, up to 15 secondss-720p|$0.06
Recraft Remove Background, image to image|$0.005
Bytedance seedream 4.0, text-to-image|$0.025
Bytedance seedream 4.0, image-to-video|$0.025
Topaz Video Upscaler, upscale factor 1x/2x/4xs|$0.06
Kling AI Avtar , lip sync, Standard-up to 15 secondss-720p|$0.04
Kling AI Avtar , lip sync, Pro-up to 15 secondss-1080p|$0.08
hailuo 02, text-to-video, Standard-10.0s-768p|$0.25
hailuo 02, image-to-video, Standard-10.0s-512p|$0.1
hailuo 02, image-to-video, Standard-10.0s-768p|$0.25
hailuo 02, text-to-video, Standard-6.0s-768p|$0.15
hailuo 02, image-to-video, Standard-6.0s-512p|$0.06
hailuo 02, image-to-video, Pro-6.0s-1080p|$0.285
hailuo 02, text-to-video, Pro-6.0s-1080p|$0.285
wan 2.2 Animate, 2.2 Animate Move, 1.0s-480p|$0.03
wan 2.2 Animate, 2.2 Animate Move, 1.0s-580p|$0.0475
wan 2.2 Animate, 2.2 Animate Move, 1.0s-720p|$0.0625
wan 2.5, text-to-video, default-10.0s-720p|$0.6
wan 2.5, text-to-video, default-5.0s-1080p|$0.5
wan 2.5, text-to-video, default-10.0s-1080p|$1.0
wan 2.5, image-to-video, default-10.0s-1080p|$1.0
wan 2.5, text-to-video, default-5.0s-720p|$0.3
wan 2.5, image-to-video, default-10.0s-720p|$0.6
wan 2.5, image-to-video, default-5.0s-1080p|$0.5
kling 2.5 turbo , text-to-video, Turbo Pro-10.0s|$0.42
kling 2.5 turbo , image-to-video, Turbo Pro-5.0s|$0.21
kling 2.5 turbo , image-to-video, Turbo Pro-10.0s|$0.42
kling 2.5 turbo , text-to-video, Turbo Pro-5.0s|$0.21
Topaz Image Upscaler, image-upscale, ≤2K|$0.05
Topaz Image Upscaler, image-upscale, 4K|$0.01
Topaz Image Upscaler, image-upscale, 8K|$0.02
OpenAI 4o image, text-to-image|$0.03
Black Forest Labs flux1-kontext, text-to-image, Pro|$0.025
Black Forest Labs flux1-kontext, text-to-image, Max|$0.05
Open AI sora 2, image-to-video, Standard-15.0s|$0.125
Open AI sora 2, text-to-video, Standard-15.0s|$0.125
Open AI sora 2, image-to-video, Standard-10.0s|$0.1
Open AI sora 2, text-to-video, Standard-10.0s|$0.1
Open AI sora 2 pro, image-to-video, Pro High-10.0s|$1.65
Open AI sora 2 pro, image-to-video, Pro High-15.0s|$3.15
Open AI sora 2-watermark-remover|$0.05
Open AI sora 2 pro, text-to-video, Pro High-15.0s|$3.15
Open AI sora 2 pro, image-to-video, Pro Standard-10.0s|$0.75
Open AI sora 2 pro, image-to-video, Pro Standard-15.0s|$1.35
Open AI sora 2 pro, text-to-video, Pro Standard-15.0s|$1.35
Open AI sora 2 pro, text-to-video, Pro High-10.0s|$1.65
Open AI sora 2 pro, storyboard, Pro-10.0s|$0.75
Open AI sora 2 pro, storyboard, Pro-15-25s|$1.35
Open AI sora 2 pro, text-to-video, Pro Standard-10.0s|$0.75
Google veo 3.1, reference-to-video, Fast|$0.3
Google veo 3.1, text-to-video, Quality|$1.25
Google veo 3.1, image-to-video, Fast|$0.3
Google veo 3.1, image-to-video, Quality|$1.25
hailuo 2.3, image-to-video, Pro-10.0s-768p|$0.45
hailuo 2.3, image-to-video, Pro-6.0s-1080p|$0.4
hailuo 2.3, image-to-video, Pro-6.0s-768p|$0.225
hailuo 2.3, image-to-video, Standard-6.0s-768p|$0.15
hailuo 2.3, image-to-video, Standard-10.0s-768p|$0.25
hailuo 2.3, image-to-video, Standard-6.0s-1080p|$0.25
grok-imagine, text-to-image|$0.02
grok-imagine, upscale, 360p→720p|$0.05
Bytedance seedance-v1-pro-fast, image-to-video, Fast-10.0s-1080p|$0.36
Bytedance seedance-v1-pro-fast, image-to-video, Fast-5.0s-720p|$0.08
Bytedance seedance-v1-pro-fast, image-to-video, Fast-10.0s-720p|$0.18
Bytedance seedance-v1-pro-fast, image-to-video, Fast-5.0s-1080p|$0.18
Black Forest Labs Flux 2 Flex, text-to-image, 1.0s-2K|$0.12
Black Forest Labs Flux 2 Flex, image to image, 1.0s-2K|$0.12
Black Forest Labs Flux 2 Flex, text-to-image, 1.0s-1K|$0.07
Black Forest Labs flux-2 pro, text-to-image, 1.0s-2K|$0.035
Black Forest Labs Flux 2 Flex, image to image, 1.0s-1K|$0.07
Black Forest Labs flux-2 pro, image to image, 1.0s-2K|$0.035
Black Forest Labs flux-2 pro, text-to-image, 1.0s-1K|$0.025
kling 2.6, text-to-video, with audio|$1.1
kling 2.6, text-to-video, without audio-10.0s|$0.55
kling 2.6, text-to-video, without audio-5.0s|$0.275
kling 2.6, text-to-video, with audio|$1.1
kling 2.6, image-to-video, without audio-10.0s|$0.55
kling 2.6, image-to-video, with audio|$1.1
kling 2.6, image-to-video, with audio-5.0s|$0.55
Bytedance seedream 4.5, image-edit, Basic/High-0.0s|$0.0325
Bytedance seedream 4.5, text-to-image, Basic/High-0.0s|$0.0325
wan 2.6, video-to-video, 5.0s-1080p|$0.5225
wan 2.6, video-to-video, 10.0s-1080p|$1.0475
wan 2.6, video-to-video, 10.0s-720p|$0.7
wan 2.6, video-to-video, 15.0s-720p|$1.05
wan 2.6, image-to-video, 10.0s-1080p|$1.0475
wan 2.6, image-to-video, 15.0s-1080p|$1.575
wan 2.6, video-to-video, 5.0s-720p|$0.35
wan 2.6, image-to-video, 5.0s-1080p|$0.5225
wan 2.6, image-to-video, 5.0s-720p|$0.35
wan 2.6, image-to-video, 10.0s-720p|$0.7
wan 2.6, image-to-video, 15.0s-720p|$1.05
wan 2.6, text to video, 5.0s-1080p|$0.5225
wan 2.6, text to video, 10.0s-1080p|$1.0475
wan 2.6, text to video, 15.0s-1080p|$1.575
wan 2.6, text to video, 15.0s-720p|$1.05
wan 2.6, text to video, 10.0s-720p|$0.7
wan 2.6, text to video, 5.0s-720p|$$0.35
"""

def parse_models(raw_data):
    """Парсинг моделей из упрощённого формата"""
    models = []
    seen_ids = set()
    
    for line in raw_data.strip().split('\n'):
        line = line.strip()
        if not line or '|' not in line:
            continue
        
        parts = line.split('|')
        if len(parts) != 2:
            continue
        
        name = parts[0].strip()
        price_str = parts[1].strip().replace('$', '').replace('$', '')
        
        try:
            price = float(price_str)
        except:
            print(f"⚠️ Не могу распарсить цену: {line}")
            continue
        
        # Генерация model_id
        model_id = name.lower()
        model_id = re.sub(r'[^\w\s-]', '', model_id)
        model_id = re.sub(r'\s+', '-', model_id).strip('-')
        model_id = model_id[:80]
        
        # Уникальность
        if model_id in seen_ids:
            counter = 2
            while f"{model_id}-{counter}" in seen_ids:
                counter += 1
            model_id = f"{model_id}-{counter}"
        
        seen_ids.add(model_id)
        
        # Определение категории
        name_lower = name.lower()
        if 'text-to-video' in name_lower or 'video' in name_lower and 'text' in name_lower:
            category = 'text-to-video'
        elif 'image-to-video' in name_lower or 'video' in name_lower and 'image' in name_lower:
            category = 'image-to-video'
        elif 'video-to-video' in name_lower:
            category = 'video-to-video'
        elif 'text-to-image' in name_lower or ('image' in name_lower and 'text' in name_lower):
            category = 'text-to-image'
        elif 'image-to-image' in name_lower or 'edit' in name_lower or 'upscale' in name_lower:
            category = 'image-to-image'
        elif any(k in name_lower for k in ['suno', 'elevenlabs', 'speech', 'audio', 'music']):
            category = 'audio'
        elif 'upscale' in name_lower:
            category = 'upscale'
        else:
            category = 'other'
        
        models.append({
            'model_id': model_id,
            'display_name': name,
            'category': category,
            'enabled': True,
            'verified': model_id == 'qwen-z-image-text-to-image-10s',
            'pricing': {
                'usd_per_run': price
            }
        })
    
    return models

if __name__ == '__main__':
    models = parse_models(RAW_DATA)
    
    print(f"\n✅ Распарсено моделей: {len(models)}")
    print("\nПримеры:")
    for m in models[:10]:
        print(f"  • {m['model_id']}: ${m['pricing']['usd_per_run']} ({m['category']})")
    
    # Статистика по категориям
    from collections import Counter
    cats = Counter(m['category'] for m in models)
    print(f"\nКатегории:")
    for cat, count in cats.most_common():
        print(f"  {cat}: {count}")
    
    # Сохранение
    with open('/workspaces/5656/models/manual_overrides.json', 'w', encoding='utf-8') as f:
        json.dump(models, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Сохранено в models/manual_overrides.json")
