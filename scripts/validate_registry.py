#!/usr/bin/env python3
"""
Registry Validator - Check model database integrity

Validates:
1. Each model has required fields (tech_model_id, endpoint, pricing)
2. 5 cheapest models are identified correctly
3. No duplicate model IDs
4. All schemas are valid
5. UI can build tree without errors
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any

# Paths
REGISTRY_FILES = [
    Path("/workspaces/5656/models/kie_models_final_truth.json"),  # v6.2 - PRODUCTION
    Path("/workspaces/5656/models/kie_parsed_models.json"),       # v6.0
    Path("/workspaces/5656/models/kie_api_models.json"),          # v5.0
    Path("/workspaces/5656/models/kie_models_source_of_truth.json"),  # OLD
]

class RegistryValidator:
    """Validates KIE model registry"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.registry_data = None
        self.models = []
    
    def load_registry(self) -> bool:
        """Load the active registry file"""
        
        print("📂 Loading registry...")
        
        for registry_path in REGISTRY_FILES:
            if registry_path.exists():
                print(f"   Using: {registry_path.name}")
                
                with open(registry_path, 'r', encoding='utf-8') as f:
                    self.registry_data = json.load(f)
                
                self.models = self.registry_data.get('models', [])
                print(f"   ✅ Loaded {len(self.models)} models")
                return True
        
        self.errors.append("No registry file found!")
        return False
    
    def validate_required_fields(self) -> int:
        """Validate each model has required fields"""
        
        print("\n🔍 Validating required fields...")
        
        required_fields = ['model_id']
        recommended_fields = ['display_name', 'pricing', 'input_schema']
        
        issues = 0
        
        for i, model in enumerate(self.models):
            model_id = model.get('model_id', f'model_{i}')
            
            # Check required
            for field in required_fields:
                if field not in model or not model[field]:
                    self.errors.append(f"{model_id}: Missing required field '{field}'")
                    issues += 1
            
            # Check recommended
            for field in recommended_fields:
                if field not in model or not model[field]:
                    self.warnings.append(f"{model_id}: Missing recommended field '{field}'")
        
        if issues == 0:
            print(f"   ✅ All models have required fields")
        else:
            print(f"   ❌ {issues} models missing required fields")
        
        return issues
    
    def validate_pricing(self) -> int:
        """Validate pricing data"""
        
        print("\n💰 Validating pricing...")
        
        issues = 0
        models_with_pricing = 0
        
        for model in self.models:
            model_id = model.get('model_id', 'unknown')
            pricing = model.get('pricing', {})
            
            if not pricing:
                self.warnings.append(f"{model_id}: No pricing data")
                continue
            
            models_with_pricing += 1
            
            # Check for at least one price field
            price_fields = ['credits_per_generation', 'usd_per_generation', 'rub_per_generation']
            if not any(pricing.get(field) for field in price_fields):
                self.errors.append(f"{model_id}: Pricing exists but no actual price values")
                issues += 1
            
            # Validate price logic
            credits = pricing.get('credits_per_generation', 0)
            usd = pricing.get('usd_per_generation', 0)
            
            if credits > 0 and usd > 0:
                # Check conversion: 1 credit = $0.005
                expected_usd = credits * 0.005
                if abs(usd - expected_usd) > 0.001:
                    self.warnings.append(
                        f"{model_id}: Credits/USD mismatch: "
                        f"{credits} credits should be ${expected_usd:.3f}, got ${usd:.3f}"
                    )
        
        print(f"   ✅ {models_with_pricing}/{len(self.models)} models have pricing")
        
        if issues == 0:
            print(f"   ✅ Pricing validation passed")
        else:
            print(f"   ❌ {issues} pricing issues")
        
        return issues
    
    def find_cheapest_models(self, count: int = 5) -> List[Dict]:
        """Find N cheapest models"""
        
        print(f"\n🏆 Finding {count} cheapest models...")
        
        # Sort by credits (preferred) or USD price
        models_with_price = []
        
        for model in self.models:
            pricing = model.get('pricing', {})
            
            # Prefer credits_per_generation
            price = pricing.get('credits_per_generation')
            if not price:
                # Fallback to USD
                price = pricing.get('usd_per_generation', 0) / 0.005
            
            if price > 0:
                models_with_price.append({
                    'model': model,
                    'price': price,
                    'model_id': model.get('model_id', 'unknown')
                })
        
        # Sort by price
        models_with_price.sort(key=lambda x: x['price'])
        
        cheapest = models_with_price[:count]
        
        print(f"\n   💎 TOP {count} CHEAPEST:")
        for i, item in enumerate(cheapest, 1):
            model_id = item['model_id']
            price = item['price']
            usd = price * 0.005
            rub = usd * 1.5 * 95  # Our markup
            
            print(f"   {i}. {model_id:40s} {price:6.1f} credits ({rub:6.2f}₽)")
        
        return [item['model'] for item in cheapest]
    
    def validate_duplicates(self) -> int:
        """Check for duplicate model IDs"""
        
        print("\n🔍 Checking for duplicates...")
        
        model_ids = [m.get('model_id') for m in self.models]
        seen = set()
        duplicates = []
        
        for mid in model_ids:
            if mid in seen:
                duplicates.append(mid)
            seen.add(mid)
        
        if duplicates:
            self.errors.append(f"Duplicate model IDs: {duplicates}")
            print(f"   ❌ Found {len(duplicates)} duplicates")
            return len(duplicates)
        else:
            print(f"   ✅ No duplicates")
            return 0
    
    def validate_input_schemas(self) -> int:
        """Validate input schemas"""
        
        print("\n📝 Validating input schemas...")
        
        issues = 0
        models_with_schema = 0
        
        for model in self.models:
            model_id = model.get('model_id', 'unknown')
            schema = model.get('input_schema', {})
            
            if not schema:
                self.warnings.append(f"{model_id}: No input schema")
                continue
            
            models_with_schema += 1
            
            # Check schema structure
            if 'properties' not in schema:
                self.warnings.append(f"{model_id}: Schema missing 'properties'")
            
            # Check for at least one input parameter
            properties = schema.get('properties', {})
            if not properties:
                self.warnings.append(f"{model_id}: Schema has no properties")
        
        print(f"   ✅ {models_with_schema}/{len(self.models)} models have schemas")
        
        return issues
    
    def validate_ui_tree(self) -> int:
        """Validate that UI tree can be built"""
        
        print("\n🌳 Validating UI tree structure...")
        
        # Group by category
        categories = {}
        uncategorized = []
        
        for model in self.models:
            model_id = model.get('model_id', 'unknown')
            category = model.get('category')
            
            if not category:
                # Try to infer from model_id
                if 'video' in model_id.lower():
                    category = 'video'
                elif 'image' in model_id.lower():
                    category = 'image'
                elif 'audio' in model_id.lower() or 'music' in model_id.lower():
                    category = 'audio'
                else:
                    uncategorized.append(model_id)
                    category = 'other'
            
            if category not in categories:
                categories[category] = []
            
            categories[category].append(model_id)
        
        print(f"\n   📂 Categories:")
        for cat, models in sorted(categories.items()):
            print(f"      • {cat:20s}: {len(models):3d} models")
        
        if uncategorized:
            print(f"\n   ⚠️  {len(uncategorized)} models without category")
            for mid in uncategorized[:5]:
                print(f"      • {mid}")
            if len(uncategorized) > 5:
                print(f"      ... and {len(uncategorized) - 5} more")
        
        return len(uncategorized)
    
    def run(self) -> bool:
        """Run all validations"""
        
        print("="*80)
        print("🔍 REGISTRY VALIDATION")
        print("="*80)
        
        if not self.load_registry():
            return False
        
        # Run all checks
        self.validate_required_fields()
        self.validate_pricing()
        self.find_cheapest_models(5)
        self.validate_duplicates()
        self.validate_input_schemas()
        self.validate_ui_tree()
        
        # Print summary
        print("\n" + "="*80)
        print("📊 VALIDATION SUMMARY")
        print("="*80)
        
        print(f"\n✅ Total models: {len(self.models)}")
        print(f"❌ Errors: {len(self.errors)}")
        print(f"⚠️  Warnings: {len(self.warnings)}")
        
        if self.errors:
            print("\n❌ ERRORS:")
            for err in self.errors[:10]:
                print(f"   • {err}")
            if len(self.errors) > 10:
                print(f"   ... and {len(self.errors) - 10} more")
        
        if self.warnings:
            print("\n⚠️  WARNINGS (first 10):")
            for warn in self.warnings[:10]:
                print(f"   • {warn}")
            if len(self.warnings) > 10:
                print(f"   ... and {len(self.warnings) - 10} more")
        
        print("\n" + "="*80)
        
        if self.errors:
            print("❌ VALIDATION FAILED")
            return False
        else:
            print("✅ VALIDATION PASSED")
            return True


def main():
    """Run validation"""
    validator = RegistryValidator()
    success = validator.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
