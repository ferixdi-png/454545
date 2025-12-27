#!/usr/bin/env python3
"""
Update KIE_SOURCE_OF_TRUTH.json with correct prices from pricing_source_truth.txt
Formula: (kie_usd_price * 2) * USD_TO_RUB
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

USD_TO_RUB = 95.0  # Fixed rate
MARKUP = 2.0  # User requested: multiply by 2
KIE_CREDITS_TO_USD = 0.005  # $0.005 per credit

def parse_pricing_file_detailed(filepath: str) -> Dict[str, Dict]:
    """Parse pricing file and return detailed pricing data."""
    print(f"  Reading {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    print(f"  Processing {len(lines)} lines...")
    models = {}
    current_model = None
    current_modality = None
    current_credits = None
    
    for i, line in enumerate(lines):
        if i % 500 == 0:
            print(f"    Line {i}/{len(lines)}...")
        
        line_stripped = line.strip()
        
        # Detect model name (lines with commas and specific patterns)
        if ',' in line_stripped and any(kw in line_stripped.lower() for kw in [
            'pro', 'flex', 'fast', 'turbo', '720p', '480p', '1080p', 'audio', 'video', 'image', 's-', 's '
        ]):
            current_model = line_stripped
            current_credits = None
            current_modality = None
        
        # Detect modality
        if line_stripped in ('video', 'image', 'audio', 'text'):
            current_modality = line_stripped
        
        # Detect credits (number like "84.0" on its own line)
        if re.match(r'^\d+\.?\d*$', line_stripped):
            try:
                credits = float(line_stripped)
                if credits > 0 and credits < 10000:  # Reasonable credit range
                    current_credits = credits
            except:
                pass
        
        # Detect USD price (line starting with $)
        if line_stripped.startswith('$') and current_model and current_credits:
            match = re.match(r'^\$(\d+\.?\d*)', line_stripped)
            if match:
                usd_price = float(match.group(1))
                
                # Calculate our price
                rub_price = usd_price * MARKUP * USD_TO_RUB
                
                models[current_model] = {
                    'usd_kie': usd_price,
                    'credits': current_credits,
                    'rub_our': round(rub_price, 2),
                    'modality': current_modality
                }
                
                # Reset
                current_model = None
                current_credits = None
                current_modality = None
    
    print(f"  Parsed {len(models)} pricing entries")
    return models

def create_manual_mapping() -> Dict[str, List[str]]:
    """Manual mapping of our model_ids to pricing file patterns."""
    return {
        # Sora models
        'sora-2-text-to-video': ['sora 2 pro', 'text-to-video'],
        'sora-2-image-to-video': ['sora 2 pro', 'image-to-video'],
        'sora-watermark-remover': ['sora 2-watermark-remover'],
        
        # Grok-imagine (Wan-based)
        'grok-imagine/image-to-video': ['grok-imagine', 'image-to-video', '6.0s'],
        'grok-imagine/text-to-video': ['grok-imagine', 'text-to-video', '6.0s'],
        'grok-imagine/text-to-image': ['grok-imagine', 'text-to-image'],
        'grok-imagine/upscale': ['grok-imagine', 'upscale'],
        
        # Kling 2.6
        'kling-2.6/image-to-video': ['kling 2.6', 'image-to-video', 'without audio'],
        'kling-2.6/text-to-video': ['kling 2.6', 'text-to-video', 'with audio'],
        
        # Wan 2.6
        'wan/2-6-text-to-video': ['wan 2.5', 'text-to-video', '10.0s-720p'],  # Use 2.5 as proxy
        'wan/2-6-image-to-video': ['wan 2.6', 'image-to-video', '10.0s-1080p'],
        'wan/2-6-video-to-video': ['wan 2.6', 'video-to-video', '15.0s-1080p'],
        
        # Wan 2.5
        'wan/2-5-image-to-video': ['wan 2.5', 'image-to-video', '10.0s-1080p'],
        'wan/2-5-text-to-video': ['wan 2.5', 'text-to-video', '10.0s-720p'],
        
        # Wan 2.2 speech-to-video
        'wan/2-2-a14b-speech-to-video-turbo': ['wan 2.2 a14b turbo api speech to video', '720p'],
        
        # Bytedance/Seedance
        'bytedance/seedance-1.5-pro': ['seedance 1.5 pro', '12s', '720p', 'with audio'],
        
        # Hailuo
        'hailuo/2-3-image-to-video-pro': ['hailuo 2.3', 'pro', '10.0s'],
        'hailuo/2-3-image-to-video-standard': ['hailuo 2.3', 'standard', '6.0s'],
        
        # Kling v2-5 turbo
        'kling/v2-5-turbo-text-to-video-pro': ['kling 2.5 turbo', 'text-to-video', 'turbo p'],
        'kling/v2-5-turbo-image-to-video-pro': ['kling 2.5 turbo', 'image-to-video', 'turbo'],
        
        # Kling avatar
        'kling/v1-avatar-standard': ['kling ai avtar', 'standard'],
        'kling/ai-avatar-v1-pro': ['kling ai avtar', 'pro'],
        
        # Qwen z-image
        'z-image': ['qwen z-image', '1.0s'],
        
        # Flux models
        'flux-2/pro-image-to-image': ['flux-2 pro', 'text-to-image'],  # No i2i in price file, use t2i
        'flux-2/pro-text-to-image': ['flux-2 pro', 'text-to-image'],
        'flux-2/flex-image-to-image': ['flux-2 pro', 'text-to-image'],  # Same
        'flux-2/flex-text-to-image': ['flux 2 flex', 'text-to-image'],
        
        # Google models
        'google/nano-banana': ['google nano banana,', 'text-to-image'],
        'google/nano-banana-edit': ['google nano banana edit'],
        'google/imagen4-fast': ['google imagen4', 'fast'],
        'google/imagen4': ['google imagen4', 'fast'],  # Same as fast
        'google/imagen4-ultra': ['google nano banana pro', '1/2k'],
        'google/veo': ['google veo 3.1'],
        'nano-banana-pro': ['google nano banana pro', '1/2k'],
        
        # Midjourney
        'midjourney': ['midjourney'],
        
        # Ideogram
        'ideogram/v3-upscale': ['ideogram v3', 'upscale'],
        'ideogram/character-to-image': ['ideogram character,', 'text-to-image'],
        
        # Elevenlabs
        'elevenlabs/audio-isolation': ['elevenlabs', 'turbo 2.5'],
        'elevenlabs/text-to-speech-turbo-2-5': ['elevenlabs', 'turbo 2.5'],
        'elevenlabs/text-to-speech-multilingual-v2': ['elevenlabs', 'turbo 2.5'],
        'elevenlabs/sound-effect-v2': ['elevenlabs', 'turbo 2.5'],
        
        # InfiniteTalk
        'infinitalk/from-audio': ['infinitetalk'],
        
        # Runway
        'runway/gen-4': ['runway'],
        
        # Bytedance Seedream
        'seedream/4.5-text-to-image': ['bytedance seedream 4.5', 'image-edit'],
        'seedream/4.5-edit': ['bytedance seedream 4.5', 'image-edit'],
        
        # Topaz
        'topaz/image-upscale': ['topaz image upscaler'],
        
        # Recraft
        'recraft/remove-background': ['recraft remove background'],
    }

def find_best_match(model_id: str, pricing_data: Dict[str, Dict], manual_map: Dict[str, List[str]]) -> Tuple[str, Dict] | None:
    """Find best matching pricing entry for our model_id."""
    # Try manual mapping first
    if model_id in manual_map:
        keywords = manual_map[model_id]
        
        for pricing_name, pricing in pricing_data.items():
            name_lower = pricing_name.lower()
            
            # Check if ALL keywords match
            if all(kw.lower() in name_lower for kw in keywords):
                return (pricing_name, pricing)
    
    # Fallback: fuzzy match by extracting key parts from model_id
    keywords = []
    if '/' in model_id:
        parts = model_id.split('/')
        keywords.extend(parts)
    else:
        keywords.append(model_id)
    
    best_match = None
    best_score = 0
    
    for pricing_name, pricing in pricing_data.items():
        name_lower = pricing_name.lower()
        score = sum(len(kw) for kw in keywords if kw.lower() in name_lower)
        
        if score > best_score:
            best_score = score
            best_match = (pricing_name, pricing)
    
    return best_match if best_score > 5 else None

def main():
    print("🔍 Parsing pricing source of truth...")
    pricing_data = parse_pricing_file_detailed("pricing_source_truth.txt")
    print(f"✅ Found {len(pricing_data)} pricing entries\n")
    
    print("📋 Loading KIE_SOURCE_OF_TRUTH.json...")
    sot_path = Path("models/KIE_SOURCE_OF_TRUTH.json")
    with open(sot_path, "r", encoding="utf-8") as f:
        sot = json.load(f)
    
    models = sot.get("models", sot)
    print(f"✅ Found {len(models)} models in SOT\n")
    
    manual_map = create_manual_mapping()
    
    print("🔗 Matching and updating prices...\n")
    print("=" * 120)
    
    updated = 0
    no_match = []
    
    for model_id, model_data in models.items():
        match = find_best_match(model_id, pricing_data, manual_map)
        
        if match:
            pricing_name, pricing = match
            old_rub = model_data.get('pricing', {}).get('rub_per_use', 0)
            new_rub = pricing['rub_our']
            
            # Update pricing in model data
            if 'pricing' not in model_data:
                model_data['pricing'] = {}
            
            model_data['pricing']['rub_per_use'] = new_rub
            model_data['pricing']['usd_per_use'] = pricing['usd_kie'] * MARKUP
            model_data['pricing']['credits_per_use'] = pricing['credits']
            
            diff = new_rub - old_rub
            status = "✅" if abs(diff) < 1 else "📈" if diff > 0 else "📉"
            
            print(f"{status} {model_id:50} {old_rub:7.2f}₽ → {new_rub:7.2f}₽  ({pricing_name[:40]})")
            updated += 1
        else:
            no_match.append(model_id)
    
    print("=" * 120)
    print(f"\n✅ Updated {updated} models")
    
    if no_match:
        print(f"\n⚠️  No pricing match for {len(no_match)} models:")
        for m in no_match:
            print(f"   - {m}")
    
    # Save updated SOT
    backup_path = Path("models/KIE_SOURCE_OF_TRUTH.json.backup")
    print(f"\n💾 Creating backup: {backup_path}")
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(sot, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Saving updated SOT: {sot_path}")
    with open(sot_path, "w", encoding="utf-8") as f:
        json.dump(sot, f, indent=2, ensure_ascii=False)
    
    print("\n✅ Pricing update complete!")

if __name__ == "__main__":
    main()
