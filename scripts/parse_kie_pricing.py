#!/usr/bin/env python3
"""
Parse kie_pricing_raw.txt and generate complete model database
"""

import json
import re
from pathlib import Path

# Load pricing data
pricing_file = Path("/workspaces/5656/kie_pricing_raw.txt")
output_file = Path("/workspaces/5656/models/kie_parsed_models.json")

def parse_model_line(line: str) -> dict:
    """Parse single line: 'Model Name, category, variant|price'"""
    line = line.strip()
    if not line or '|' not in line:
        return None
    
    # Split by pipe to get price
    parts, price_str = line.rsplit('|', 1)
    price_usd = float(price_str)
    
    # Split parts by comma
    segments = [s.strip() for s in parts.split(',')]
    
    if len(segments) < 2:
        return None
    
    model_name = segments[0]
    category = segments[1] if len(segments) > 1 else "unknown"
    variant = segments[2] if len(segments) > 2 else "default"
    
    return {
        "raw_name": model_name,
        "category": category,
        "variant": variant,
        "price_usd": price_usd,
        "credits": price_usd / 0.005,  # 1 credit = $0.005
        "price_rub": price_usd * 1.5 * 95,  # 50% markup, 95 RUB/USD
    }

def normalize_model_id(raw_name: str, category: str, variant: str) -> str:
    """Convert human-readable name to API model_id"""
    
    # Known mappings from existing working models
    name_lower = raw_name.lower()
    
    # Create unique suffix from variant if needed
    variant_suffix = ""
    if variant and variant != "default":
        # Extract key parts from variant
        variant_clean = re.sub(r'[^a-z0-9-]', '-', variant.lower())
        variant_clean = re.sub(r'-+', '-', variant_clean).strip('-')
        
        # Only add suffix if variant has meaningful info
        if variant_clean and variant_clean not in ['default', '0-0s']:
            variant_suffix = f":{variant_clean}"
    
    # Grok Imagine
    if "grok" in name_lower:
        if "text-to-image" in category:
            return "grok-imagine/text-to-image"
        elif "image-to-video" in category:
            return "grok-imagine/image-to-video"
        elif "text-to-video" in category:
            return "grok-imagine/text-to-video"
        elif "upscale" in category:
            return "grok-imagine/upscale"
    
    # Wan models
    if "wan" in name_lower:
        version = None
        if "2.6" in raw_name:
            version = "2-6"
        elif "2.5" in raw_name:
            version = "2-5"
        elif "2.2" in raw_name:
            version = "2-2"
        
        if version:
            if "text-to-video" in category or "text to video" in category:
                return f"wan/{version}-text-to-video"
            elif "image-to-video" in category:
                return f"wan/{version}-image-to-video"
            elif "video-to-video" in category:
                return f"wan/{version}-video-to-video"
    
    # Seedream
    if "seedream" in name_lower:
        if "4.5" in raw_name:
            return "seedream/4.5-text-to-image"
        elif "4.0" in raw_name:
            if "text-to-image" in category:
                return "seedream/4.0-text-to-image"
            elif "image-to-video" in category:
                return "seedream/4.0-image-to-video"
    
    # Nano Banana
    if "nano banana" in name_lower:
        if "pro" in name_lower:
            return "nano-banana-pro"
        return "nano-banana"
    
    # Veo 3.1
    if "veo" in name_lower and "3.1" in raw_name:
        if "text-to-video" in category:
            if "fast" in variant.lower():
                return "veo3.1/text-to-video-fast"
            elif "quality" in variant.lower():
                return "veo3.1/text-to-video-quality"
        elif "image-to-video" in category:
            if "fast" in variant.lower():
                return "veo3.1/image-to-video-fast"
            elif "quality" in variant.lower():
                return "veo3.1/image-to-video-quality"
    
    # Kling
    if "kling" in name_lower:
        version = "2.6" if "2.6" in raw_name else "2.1" if "2.1" in raw_name else "1.0"
        version_id = version.replace(".", "-")
        
        if "text-to-video" in category:
            return f"kling/{version_id}-text-to-video"
        elif "image-to-video" in category:
            return f"kling/{version_id}-image-to-video"
        elif "video-generation" in category:
            return f"kling/{version_id}-video-generation"
    
    # Midjourney
    if "midjourney" in name_lower:
        if "text-to-image" in category:
            return "midjourney/text-to-image"
        elif "image-to-image" in category:
            return "midjourney/image-to-image"
        elif "image-to-video" in category:
            return "midjourney/image-to-video"
    
    # Flux
    if "flux" in name_lower:
        if "kontext" in name_lower:
            return "flux/kontext-pro"
        elif "2 pro" in name_lower or "2-pro" in name_lower:
            if "image to image" in category or "image-to-image" in category:
                return "flux/2-pro-image-to-image"
            return "flux/2-pro-text-to-image"
        elif "2 flex" in name_lower:
            return "flux/2-flex"
    
    # Imagen
    if "imagen" in name_lower:
        return "google/imagen4"
    
    # Runway
    if "runway" in name_lower and "aleph" in name_lower:
        return "runway/aleph"
    
    # Hailuo
    if "hailuo" in name_lower:
        version = "2.3" if "2.3" in raw_name else "02"
        if "text-to-video" in category:
            return f"hailuo/{version}-text-to-video"
        elif "image-to-video" in category:
            return f"hailuo/{version}-image-to-video"
    
    # Suno
    if "suno" in name_lower:
        return "suno/music-generation"
    
    # OpenAI
    if "openai" in name_lower or "4o image" in name_lower:
        return "openai/4o-image"
    
    # Ideogram
    if "ideogram" in name_lower:
        version = "v3"
        if "remix" in name_lower:
            return f"ideogram/{version}-remix"
        elif "edit" in name_lower:
            return f"ideogram/{version}-edit"
        return f"ideogram/{version}"
    
    # Qwen
    if "qwen" in name_lower:
        return "qwen/z-image"
    
    # Elevenlabs
    if "elevenlabs" in name_lower:
        if "text to speech" in name_lower:
            if "turbo" in variant.lower():
                return "elevenlabs/tts-turbo"
            return "elevenlabs/tts-multilingual"
        elif "sound effect" in name_lower:
            return "elevenlabs/sound-effect-v2"
        elif "speech to text" in name_lower:
            return "elevenlabs/stt"
        elif "audio isolation" in name_lower:
            return "elevenlabs/audio-isolation"
    
    # Recraft
    if "recraft" in name_lower:
        if "upscale" in name_lower:
            return "recraft/crisp-upscale"
        elif "background" in name_lower:
            return "recraft/remove-background"
    
    # Topaz
    if "topaz" in name_lower:
        if "video" in name_lower:
            return "topaz/video-upscaler"
        return "topaz/image-upscaler"
    
    # Fallback: create ID from name
    clean_name = re.sub(r'[^a-z0-9]+', '-', name_lower)
    clean_name = clean_name.strip('-')
    
    # Add variant suffix to make unique
    return clean_name + variant_suffix

def generate_input_schema(model_id: str, category: str, variant: str) -> dict:
    """Generate input schema based on model type"""
    
    schema = {
        "required": [],
        "optional": [],
        "properties": {}
    }
    
    # Common parameters
    if "text-to" in category or "text to" in category:
        schema["required"].append("prompt")
        schema["properties"]["prompt"] = {
            "type": "string",
            "description": "Text description of what to generate"
        }
    
    if "image-to" in category:
        schema["required"].append("image")
        schema["properties"]["image"] = {
            "type": "string",
            "format": "url",
            "description": "Input image URL"
        }
        schema["optional"].append("prompt")
        schema["properties"]["prompt"] = {
            "type": "string",
            "description": "Additional prompt for transformation"
        }
    
    if "video-to-video" in category:
        schema["required"].append("video")
        schema["properties"]["video"] = {
            "type": "string",
            "format": "url",
            "description": "Input video URL"
        }
    
    # Video models
    if "video" in category:
        schema["optional"].append("duration")
        schema["properties"]["duration"] = {
            "type": "string",
            "enum": ["5", "10", "15"],
            "description": "Video duration in seconds"
        }
        
        schema["optional"].append("resolution")
        schema["properties"]["resolution"] = {
            "type": "string",
            "enum": ["480p", "720p", "1080p"],
            "description": "Video resolution"
        }
    
    # Image models
    if "image" in category and "video" not in category:
        schema["optional"].append("aspect_ratio")
        schema["properties"]["aspect_ratio"] = {
            "type": "string",
            "enum": ["1:1", "16:9", "9:16", "4:3", "3:4"],
            "description": "Image aspect ratio"
        }
        
        schema["optional"].append("num_outputs")
        schema["properties"]["num_outputs"] = {
            "type": "integer",
            "minimum": 1,
            "maximum": 4,
            "description": "Number of images to generate"
        }
    
    # Quality options
    if "quality" in variant.lower() or "master" in variant.lower():
        schema["optional"].append("quality")
        schema["properties"]["quality"] = {
            "type": "string",
            "enum": ["standard", "high", "ultra"],
            "description": "Generation quality"
        }
    
    return schema

def main():
    print("🔍 Parsing KIE.AI pricing data...")
    print(f"📁 Reading: {pricing_file}")
    
    models = []
    skipped = 0
    
    with open(pricing_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            parsed = parse_model_line(line)
            if not parsed:
                skipped += 1
                continue
            
            model_id = normalize_model_id(
                parsed["raw_name"],
                parsed["category"],
                parsed["variant"]
            )
            
            input_schema = generate_input_schema(
                model_id,
                parsed["category"],
                parsed["variant"]
            )
            
            model = {
                "model_id": model_id,
                "display_name": parsed["raw_name"],
                "category": parsed["category"],
                "variant": parsed["variant"],
                "pricing": {
                    "credits_per_generation": parsed["credits"],
                    "usd_per_generation": parsed["price_usd"],
                    "rub_per_generation": round(parsed["price_rub"], 2)
                },
                "input_schema": input_schema,
                "enabled": True,
                "source": "kie_pricing_raw.txt"
            }
            
            models.append(model)
            print(f"  ✓ {line_num:3d}. {model_id:40s} | {parsed['price_rub']:7.2f}₽ | {parsed['credits']:8.1f} credits")
    
    # Deduplicate model IDs by adding suffix
    seen_ids = {}
    for model in models:
        original_id = model['model_id']
        
        if original_id in seen_ids:
            # Add counter suffix
            seen_ids[original_id] += 1
            counter = seen_ids[original_id]
            model['model_id'] = f"{original_id}:{model['variant'].replace(' ', '-').lower()}-v{counter}"
            print(f"  🔄 Renamed duplicate: {original_id} → {model['model_id']}")
        else:
            seen_ids[original_id] = 1
    
    print(f"\n📊 Summary:")
    print(f"  ✅ Parsed: {len(models)} models")
    print(f"  ⏭️  Skipped: {skipped} lines")
    
    # Save to JSON
    output_data = {
        "version": "6.0.0",
        "source": "kie_pricing_raw.txt",
        "generated_at": "2025-12-24",
        "total_models": len(models),
        "api_endpoint": "/api/v1/jobs/createTask",
        "models": models
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Saved to: {output_file}")
    print(f"📦 Size: {output_file.stat().st_size / 1024:.1f} KB")
    
    # Print price ranges
    prices = [m["pricing"]["rub_per_generation"] for m in models]
    print(f"\n💰 Price range:")
    print(f"  Cheapest: {min(prices):.2f}₽")
    print(f"  Most expensive: {max(prices):.2f}₽")
    print(f"  Average: {sum(prices) / len(prices):.2f}₽")
    
    # Group by category
    categories = {}
    for m in models:
        cat = m["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(m)
    
    print(f"\n📂 Categories ({len(categories)}):")
    for cat, items in sorted(categories.items(), key=lambda x: -len(x[1])):
        print(f"  • {cat:30s}: {len(items):3d} models")
    
    print("\n✅ DONE!")

if __name__ == "__main__":
    main()
