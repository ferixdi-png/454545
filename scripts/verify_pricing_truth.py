#!/usr/bin/env python3
"""
Verify pricing accuracy against source of truth.

Checks that all 42 models in KIE_SOURCE_OF_TRUTH.json have correct prices
matching the formula: (kie_usd × 2) × 95 RUB/USD = final RUB price

Expected workflow:
1. Download pricing_source_truth.txt from https://drive.google.com/file/d/1mJDM-tIp7DPmJz-3gZpIKnH3Y_J0j2BU/view
2. Run: python scripts/verify_pricing_truth.py
3. If errors found → update models/KIE_SOURCE_OF_TRUTH.json manually
4. Re-run until all pass
"""
import json
import sys
import os
from pathlib import Path
from decimal import Decimal


# Pricing constants (must match app/payments/pricing.py)
USD_TO_RUB_RATE = 95.0  # Conservative rate for user protection
PRICING_MARKUP = 2.0    # 2x markup over KIE USD price


def load_source_truth(path: str = "models/pricing_source_truth.txt") -> dict:
    """
    Load pricing source truth from text file.
    
    Format:
        model_id: X.XX USD
    
    Returns:
        Dict mapping model_id -> usd_price
    """
    if not os.path.exists(path):
        print(f"❌ ERROR: {path} not found!")
        print("Download from: https://drive.google.com/file/d/1mJDM-tIp7DPmJz-3gZpIKnH3Y_J0j2BU/view")
        sys.exit(1)
    
    pricing = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Parse: "model_id: X.XX USD"
            if ':' in line:
                model_id, price_str = line.split(':', 1)
                model_id = model_id.strip()
                price_str = price_str.strip().replace('USD', '').strip()
                
                try:
                    usd_price = float(price_str)
                    pricing[model_id] = usd_price
                except ValueError:
                    print(f"⚠️ Warning: Could not parse price for {model_id}: {price_str}")
    
    return pricing


def load_registry(path: str = "models/KIE_SOURCE_OF_TRUTH.json") -> dict:
    """Load model registry JSON."""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('models', {})


def calculate_expected_price(usd_price: float) -> float:
    """
    Calculate expected RUB price using formula.
    
    Formula: (kie_usd × markup) × rate = final_rub
    """
    return usd_price * PRICING_MARKUP * USD_TO_RUB_RATE


def verify_pricing() -> bool:
    """
    Verify all pricing against source of truth.
    
    Returns:
        True if all prices correct, False otherwise
    """
    print("📊 Pricing Truth Verification")
    print("=" * 50)
    
    # Load data
    source_truth = load_source_truth()
    registry = load_registry()
    
    print(f"✅ Loaded source truth: {len(source_truth)} models")
    print(f"✅ Loaded registry: {len(registry)} models")
    print()
    
    # Expected: 42 models in registry
    if len(registry) != 42:
        print(f"❌ ERROR: Registry should have exactly 42 models, found {len(registry)}")
        return False
    
    # Verify each model
    errors = []
    correct = 0
    
    for model_id, model_data in registry.items():
        # Get source truth price
        if model_id not in source_truth:
            errors.append(f"❌ {model_id}: NOT FOUND in source truth")
            continue
        
        source_usd = source_truth[model_id]
        expected_rub = calculate_expected_price(source_usd)
        
        # Get registry price
        pricing = model_data.get('pricing', {})
        if 'rub_per_use' not in pricing:
            errors.append(f"❌ {model_id}: Missing rub_per_use in registry")
            continue
        
        actual_rub = float(pricing['rub_per_use'])
        
        # Allow 0.01 RUB tolerance for rounding
        diff = abs(expected_rub - actual_rub)
        if diff > 0.01:
            errors.append(
                f"❌ {model_id}: Price mismatch\n"
                f"   Source: {source_usd} USD → Expected: {expected_rub:.2f} RUB\n"
                f"   Registry: {actual_rub:.2f} RUB (diff: {diff:.2f} RUB)"
            )
        else:
            correct += 1
    
    # Report results
    print(f"✅ Correct: {correct}/42")
    if errors:
        print(f"❌ Errors: {len(errors)}")
        print()
        for error in errors:
            print(error)
        print()
        print("FIX: Update models/KIE_SOURCE_OF_TRUTH.json with correct prices")
        return False
    else:
        print()
        print("🎉 ALL PRICES VERIFIED - 100% match with source truth!")
        return True


if __name__ == "__main__":
    success = verify_pricing()
    sys.exit(0 if success else 1)
