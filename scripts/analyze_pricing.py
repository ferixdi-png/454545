#!/usr/bin/env python3
"""
Parse pricing_source_truth.txt and create a mapping for our models.
Formula: (kie_price_usd * 2) * USD_TO_RUB_RATE
"""
import json
import re
from pathlib import Path

# Exchange rate (можно взять из config или зафиксировать)
USD_TO_RUB = 95.0  # Примерный курс на декабрь 2024
MARKUP = 2.0  # умножить на 2 как сказал пользователь

def parse_pricing_file(filepath: str) -> list[dict]:
    """Parse pricing file and extract model names + USD prices."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Split by sections (each model family starts with a name line)
    models = []
    lines = content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Check if this looks like a model name (contains model info + commas)
        if ',' in line and any(keyword in line.lower() for keyword in ['pro', 'flux', 'wan', 'audio', 'minimax', 'qwen', 'hailuo', 'kling']):
            model_name = line
            
            # Look ahead for USD price in next ~10 lines
            usd_price = None
            for j in range(i+1, min(i+15, len(lines))):
                price_line = lines[j].strip()
                # Look for pattern like "$0.42" at start or "$0.42\t$"
                match = re.match(r'^\$(\d+\.?\d*)', price_line)
                if match:
                    usd_price = float(match.group(1))
                    break
            
            if usd_price is not None:
                rub_price = usd_price * MARKUP * USD_TO_RUB
                models.append({
                    'name': model_name,
                    'usd_price_kie': usd_price,
                    'usd_price_our': usd_price * MARKUP,
                    'rub_price': round(rub_price, 2)
                })
        
        i += 1
    
    return models

def load_our_models() -> dict:
    """Load our models from KIE_SOURCE_OF_TRUTH.json"""
    sot_path = Path("models/KIE_SOURCE_OF_TRUTH.json")
    if not sot_path.exists():
        return {}
    
    with open(sot_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    if "models" in data:
        return data["models"]
    return data

def fuzzy_match(our_model_id: str, pricing_models: list[dict]) -> dict | None:
    """Try to match our model ID with pricing file model names."""
    our_lower = our_model_id.lower()
    
    # Direct keyword extraction from model_id
    keywords = []
    
    # Extract key parts (provider/model name)
    if '/' in our_model_id:
        parts = our_model_id.split('/')
        keywords.extend([p.lower() for p in parts])
    
    # Add full id
    keywords.append(our_lower)
    
    # Try to find best match
    best_match = None
    best_score = 0
    
    for pricing_model in pricing_models:
        name_lower = pricing_model['name'].lower()
        score = 0
        
        for keyword in keywords:
            if keyword in name_lower:
                score += len(keyword)
        
        if score > best_score:
            best_score = score
            best_match = pricing_model
    
    return best_match if best_score > 3 else None

def main():
    print("🔍 Parsing pricing source of truth...")
    pricing_models = parse_pricing_file("pricing_source_truth.txt")
    print(f"✅ Found {len(pricing_models)} models in pricing file\n")
    
    print("📋 Loading our models from KIE_SOURCE_OF_TRUTH.json...")
    our_models = load_our_models()
    print(f"✅ Found {len(our_models)} models in our SOT\n")
    
    print("🔗 Matching models...\n")
    
    matched = []
    unmatched = []
    
    for model_id, model_data in our_models.items():
        pricing_match = fuzzy_match(model_id, pricing_models)
        
        if pricing_match:
            matched.append({
                'model_id': model_id,
                'display_name': model_data.get('name', model_id),
                'pricing_name': pricing_match['name'],
                'usd_kie': pricing_match['usd_price_kie'],
                'rub_our': pricing_match['rub_price'],
                'current_rub': model_data.get('pricing', {}).get('rub_per_use', 0)
            })
        else:
            unmatched.append({
                'model_id': model_id,
                'display_name': model_data.get('name', model_id),
                'current_rub': model_data.get('pricing', {}).get('rub_per_use', 0)
            })
    
    print("=" * 100)
    print(f"MATCHED: {len(matched)} models")
    print("=" * 100)
    for m in matched[:20]:  # Show first 20
        diff = m['rub_our'] - m['current_rub']
        status = "✅" if abs(diff) < 1 else "⚠️" if diff > 0 else "❌"
        print(f"{status} {m['model_id']:50} Current: {m['current_rub']:6.2f}₽ → New: {m['rub_our']:6.2f}₽")
    
    if len(matched) > 20:
        print(f"... and {len(matched) - 20} more")
    
    print("\n" + "=" * 100)
    print(f"UNMATCHED: {len(unmatched)} models")
    print("=" * 100)
    for m in unmatched[:10]:
        print(f"❌ {m['model_id']:50} Current: {m['current_rub']:6.2f}₽")
    
    if len(unmatched) > 10:
        print(f"... and {len(unmatched) - 10} more")
    
    # Save detailed report
    report = {
        'matched': matched,
        'unmatched': unmatched,
        'summary': {
            'total_our_models': len(our_models),
            'total_pricing_models': len(pricing_models),
            'matched_count': len(matched),
            'unmatched_count': len(unmatched),
            'markup': MARKUP,
            'usd_to_rub': USD_TO_RUB
        }
    }
    
    with open("artifacts/pricing_analysis.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📝 Detailed report saved to artifacts/pricing_analysis.json")

if __name__ == "__main__":
    main()
