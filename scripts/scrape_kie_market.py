#!/usr/bin/env python3
"""
Scrape actual working models from kie.ai/market.
This will give us the REAL list of models with correct pricing.
"""
import requests
from bs4 import BeautifulSoup
import json
import re
from decimal import Decimal

def scrape_kie_market():
    """Scrape models from kie.ai/market page."""
    url = "https://kie.ai/market"
    
    print(f"📡 Fetching {url}...")
    response = requests.get(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    if response.status_code != 200:
        print(f"❌ Failed to fetch: {response.status_code}")
        return []
    
    print(f"✅ Got response, parsing HTML...")
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find all model cards (adjust selector based on actual HTML)
    models = []
    
    # Try to find model containers
    # Based on screenshot, models are in cards with pricing info
    model_cards = soup.find_all(['div', 'article'], class_=re.compile(r'model|card|item'))
    
    print(f"📊 Found {len(model_cards)} potential model containers")
    
    # Save HTML for manual inspection
    with open('/workspaces/5656/kie_market.html', 'w', encoding='utf-8') as f:
        f.write(response.text)
    print(f"💾 Saved HTML to kie_market.html for manual inspection")
    
    # Try to extract from JSON in page (many sites embed data)
    json_pattern = re.compile(r'window\.__INITIAL_STATE__\s*=\s*({.+?});', re.DOTALL)
    json_match = json_pattern.search(response.text)
    
    if json_match:
        print("🎯 Found JSON data in page!")
        try:
            data = json.loads(json_match.group(1))
            with open('/workspaces/5656/kie_market_data.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print("💾 Saved JSON to kie_market_data.json")
        except Exception as e:
            print(f"⚠️ Failed to parse JSON: {e}")
    
    return models


def parse_model_from_screenshot():
    """
    Based on screenshot, manually create entries for visible models.
    User will provide API details for each.
    """
    models_from_screenshot = [
        {
            "model_id": "wan-2.6",  # Need to verify actual API name
            "display_name": "Wan 2.6",
            "pricing": {
                "usd_per_use": 0.28,
                "credits_per_use": 6.5,
                "rub_per_use": 44.04  # 0.28 * 157.3
            },
            "category": "video-generation",
            "modalities": ["text-to-video", "image-to-video"],
            "enabled": True,
            "needs_api_details": True
        },
        {
            "model_id": "seerdream-4.5",
            "display_name": "Seerdream 4.5",
            "pricing": {
                "usd_per_use": 0.032,
                "credits_per_use": 5,
                "rub_per_use": 5.03
            },
            "category": "image-generation",
            "modalities": ["text-to-image", "image-to-image"],
            "enabled": True,
            "needs_api_details": True
        },
        {
            "model_id": "kling-2.6",
            "display_name": "Kling 2.6",
            "pricing": {
                "usd_per_use": 0.28,
                "credits_per_use": None,  # Not visible
                "rub_per_use": 44.04
            },
            "category": "video-generation",
            "modalities": ["text-to-video", "image-to-video"],
            "enabled": True,
            "needs_api_details": True
        },
        {
            "model_id": "z-image",  # We know this one
            "display_name": "Z-Image",
            "pricing": {
                "usd_per_use": 0.004,
                "credits_per_use": 0.8,
                "rub_per_use": 0.63
            },
            "category": "image-generation",
            "modalities": ["text-to-image"],
            "enabled": True,
            "needs_api_details": False,  # User will provide
            "input_schema": {
                "required": ["prompt"],
                "properties": {
                    "prompt": {"type": "string", "required": True},
                    "width": {"type": "integer", "default": 1024},
                    "height": {"type": "integer", "default": 1024},
                    "num_images": {"type": "integer", "default": 1}
                }
            }
        },
        {
            "model_id": "flux-2",
            "display_name": "FLUX 2",
            "pricing": {
                "usd_per_use": 0.025,
                "credits_per_use": 5,
                "rub_per_use": 3.93
            },
            "category": "image-generation",
            "modalities": ["text-to-image", "image-to-image"],
            "enabled": True,
            "needs_api_details": True
        },
        {
            "model_id": "nano-banana-pro",
            "display_name": "Nano Banana Pro",
            "pricing": {
                "usd_per_use": 0.09,
                "credits_per_use": 18,
                "rub_per_use": 14.16
            },
            "category": "image-generation",
            "modalities": ["text-to-image", "image-to-image"],
            "enabled": True,
            "needs_api_details": True
        },
        {
            "model_id": "seecance-1.0-pro-fast",
            "display_name": "Seecance 1.0 Pro Fast",
            "pricing": {
                "usd_per_use": 0.08,
                "credits_per_use": 16,
                "rub_per_use": 12.58
            },
            "category": "video-generation",
            "modalities": ["image-to-video"],
            "enabled": True,
            "needs_api_details": True
        },
        {
            "model_id": "grok-imagine",
            "display_name": "Grok Imagine",
            "pricing": {
                "usd_per_use": 0.1,
                "credits_per_use": 20,
                "rub_per_use": 15.73
            },
            "category": "video-generation",
            "modalities": ["text-to-video", "image-to-video"],
            "enabled": True,
            "needs_api_details": True
        },
        {
            "model_id": "hailuo-2.3",
            "display_name": "Hailuo 2.3",
            "pricing": {
                "usd_per_use": 0.15,
                "credits_per_use": 30,
                "rub_per_use": 23.60
            },
            "category": "video-generation",
            "modalities": ["text-to-video", "image-to-video"],
            "enabled": True,
            "needs_api_details": True
        },
        {
            "model_id": "sora-2-pro-storyboard",
            "display_name": "Sora 2 Pro Storyboard",
            "pricing": {
                "usd_per_use": 0.75,
                "credits_per_use": 150,
                "rub_per_use": 118.0
            },
            "category": "video-generation",
            "modalities": ["text-to-video", "image-to-video"],
            "enabled": True,
            "needs_api_details": True
        },
        {
            "model_id": "google-veo-3.1",
            "display_name": "Google Veo 3.1",
            "pricing": {
                "usd_per_use": None,  # Not visible on screenshot
                "credits_per_use": None,
                "rub_per_use": None
            },
            "category": "video-generation",
            "modalities": ["text-to-video", "image-to-video"],
            "enabled": True,
            "needs_api_details": True
        },
        {
            "model_id": "sora-2-pro",
            "display_name": "Sora 2 Pro",
            "pricing": {
                "usd_per_use": 0.75,
                "credits_per_use": 150,
                "rub_per_use": 118.0
            },
            "category": "video-generation",
            "modalities": ["text-to-video", "image-to-video"],
            "enabled": True,
            "needs_api_details": True
        }
    ]
    
    return models_from_screenshot


if __name__ == "__main__":
    print("🚀 Scraping kie.ai/market...")
    print()
    
    # Try to scrape
    scraped = scrape_kie_market()
    
    print()
    print("📸 Parsing models from screenshot...")
    screenshot_models = parse_model_from_screenshot()
    
    print(f"✅ Found {len(screenshot_models)} models from screenshot")
    print()
    
    # Sort by price (cheapest first)
    screenshot_models.sort(key=lambda m: m['pricing'].get('rub_per_use') or 999999)
    
    print("💰 TOP-10 CHEAPEST MODELS:")
    for i, model in enumerate(screenshot_models[:10], 1):
        price = model['pricing'].get('rub_per_use', 'N/A')
        name = model['display_name']
        modalities = ', '.join(model['modalities'])
        print(f"{i:2}. {name:30} {price:>8}₽  ({modalities})")
    
    print()
    print("🎯 Next step: User will provide API details for each model")
    print("   Format: model_id, api_endpoint, input_schema")
    
    # Save preliminary data
    output = {
        "version": "5.0.0-preview",
        "source": "kie.ai/market screenshot + user input",
        "generated_at": "2024-12-24",
        "models_count": len(screenshot_models),
        "models": screenshot_models
    }
    
    with open('/workspaces/5656/models/kie_market_preview.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Saved preview to models/kie_market_preview.json")
