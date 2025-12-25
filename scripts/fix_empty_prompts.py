#!/usr/bin/env python3
"""
Исправить пустые промпты в examples моделей
Заполнить реальными примерами из Copy page
"""
import json
import os

# Реальные примеры из kie.ai Copy page
FIXED_EXAMPLES = {
    "qwen/text-to-image": {
        "prompt": "A futuristic cityscape at sunset with flying cars and neon lights",
        "image_size": "square_hd",
        "num_inference_steps": 30,
        "guidance_scale": 2.5,
        "enable_safety_checker": True
    },
    "qwen/image-to-image": {
        "prompt": "Transform this image into a watercolor painting style",
        "image_url": "https://file.aiquickdraw.com/custom-page/akr/section-images/example.jpg",
        "strength": 0.8,
        "output_format": "png",
        "acceleration": "none",
        "negative_prompt": ""
    },
    "qwen/image-edit": {
        "prompt": "Add colorful flowers in the foreground",
        "image_url": "https://file.aiquickdraw.com/custom-page/akr/section-images/1755603225969i6j87r8.png",
        "mask_url": "https://file.aiquickdraw.com/custom-page/akr/section-images/1755603258264m2kygqf1.png",
        "output_format": "png",
        "negative_prompt": ""
    },
    "elevenlabs/sound-effect-v2": {
        "text": "Ocean waves crashing on a rocky shore with seagulls in the distance",
        "loop": False,
        "prompt_influence": 0.3,
        "output_format": "mp3_44100_128"
    }
}

def main():
    registry_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'KIE_SOURCE_OF_TRUTH.json')
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    fixed_count = 0
    
    for model_id, fixed_input in FIXED_EXAMPLES.items():
        if model_id in data['models']:
            model = data['models'][model_id]
            
            # Обновляем первый example
            if 'examples' in model and model['examples']:
                old_input = model['examples'][0].get('input', {})
                
                # Сохраняем структуру, обновляем только пустые поля
                for key, value in fixed_input.items():
                    if key in old_input and old_input[key] == "":
                        old_input[key] = value
                    elif key not in old_input:
                        old_input[key] = value
                
                model['examples'][0]['input'] = old_input
                fixed_count += 1
                
                print(f"✅ Исправлен {model_id}")
                print(f"   Новый prompt/text: {old_input.get('prompt') or old_input.get('text')}")
    
    # Сохраняем обновленный registry
    with open(registry_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Исправлено {fixed_count} моделей")
    print(f"💾 Сохранено в {registry_path}")

if __name__ == "__main__":
    main()
