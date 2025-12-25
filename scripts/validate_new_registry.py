#!/usr/bin/env python3
"""
Валидатор KIE_SOURCE_OF_TRUTH.json - новая версия

Проверяет:
1. Все модели имеют валидные поля
2. endpoint существует
3. input_schema валидна
4. pricing корректен
5. Нет дубликатов
"""

import json
from pathlib import Path
from typing import Dict, List


class NewRegistryValidator:
    """Валидатор registry моделей"""
    
    REQUIRED_FIELDS = ['model_id', 'provider', 'category', 'slug', 'endpoint', 'method', 'input_schema']
    VALID_CATEGORIES = ['image', 'video', 'audio', 'enhance', 'other']
    VALID_METHODS = ['POST', 'GET']
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        
    def validate_registry(self, registry_path: Path) -> bool:
        """Валидация всего registry"""
        
        print("=" * 80)
        print("🔍 VALIDATING REGISTRY")
        print("=" * 80)
        
        # Загрузка
        with open(registry_path, 'r', encoding='utf-8') as f:
            registry = json.load(f)
        
        models = registry.get('models', {})
        print(f"\n📦 Total models: {len(models)}")
        
        # Валидация каждой модели
        for model_id, model_data in models.items():
            self._validate_model(model_id, model_data)
        
        # Проверка дубликатов
        self._check_duplicates(models)
        
        # Отчет
        self._print_report(models)
        
        return len(self.errors) == 0
    
    def _validate_model(self, model_id: str, model_data: Dict):
        """Валидация одной модели"""
        
        # 1. Required fields
        for field in self.REQUIRED_FIELDS:
            if field not in model_data:
                self.errors.append(f"[{model_id}] Missing required field: {field}")
        
        # 2. Category validation
        category = model_data.get('category')
        if category and category not in self.VALID_CATEGORIES:
            self.warnings.append(f"[{model_id}] Unknown category: {category}")
        
        # 3. Method validation
        method = model_data.get('method', 'POST')
        if method not in self.VALID_METHODS:
            self.errors.append(f"[{model_id}] Invalid method: {method}")
        
        # 4. Endpoint validation
        endpoint = model_data.get('endpoint')
        if endpoint:
            if not endpoint.startswith('/'):
                self.errors.append(f"[{model_id}] Endpoint must start with '/': {endpoint}")
        
        # 5. Input schema validation
        input_schema = model_data.get('input_schema', {})
        if not input_schema:
            self.warnings.append(f"[{model_id}] No input_schema defined")
        else:
            for param, param_data in input_schema.items():
                if not isinstance(param_data, dict):
                    self.errors.append(f"[{model_id}] Invalid schema for param '{param}'")
                elif 'type' not in param_data:
                    self.warnings.append(f"[{model_id}] No type for param '{param}'")
        
        # 6. Pricing validation
        pricing = model_data.get('pricing', {})
        if pricing:
            if 'usd_per_gen' not in pricing and 'credits_per_gen' not in pricing:
                self.warnings.append(f"[{model_id}] Pricing exists but no usd_per_gen or credits_per_gen")
            
            # Проверка корректности значений
            for price_key in ['usd_per_gen', 'rub_per_gen', 'credits_per_gen']:
                if price_key in pricing:
                    try:
                        price = float(pricing[price_key])
                        if price < 0:
                            self.errors.append(f"[{model_id}] Negative price: {price_key}={price}")
                    except (ValueError, TypeError):
                        self.errors.append(f"[{model_id}] Invalid price type: {price_key}")
    
    def _check_duplicates(self, models: Dict):
        """Проверка дубликатов"""
        
        # Проверка дубликатов по endpoint + provider
        endpoint_map = {}
        
        for model_id, model_data in models.items():
            endpoint = model_data.get('endpoint')
            provider = model_data.get('provider')
            
            if endpoint and provider:
                key = f"{provider}:{endpoint}"
                if key in endpoint_map:
                    self.warnings.append(
                        f"Duplicate endpoint: {model_id} and {endpoint_map[key]} share {endpoint}"
                    )
                else:
                    endpoint_map[key] = model_id
    
    def _print_report(self, models: Dict):
        """Печать отчета"""
        
        print("\n" + "=" * 80)
        print("📊 VALIDATION REPORT")
        print("=" * 80)
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for err in self.errors[:20]:  # Первые 20
                print(f"   {err}")
            
            if len(self.errors) > 20:
                print(f"   ... and {len(self.errors) - 20} more errors")
        else:
            print("\n✅ No errors found!")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warn in self.warnings[:20]:  # Первые 20
                print(f"   {warn}")
            
            if len(self.warnings) > 20:
                print(f"   ... and {len(self.warnings) - 20} more warnings")
        else:
            print("\n✅ No warnings!")
        
        # Статистика
        with_pricing = sum(1 for m in models.values() if m.get('pricing'))
        with_schema = sum(1 for m in models.values() if m.get('input_schema'))
        categories = {}
        for m in models.values():
            cat = m.get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1
        
        print(f"\n📊 Stats:")
        print(f"   - With pricing: {with_pricing}/{len(models)}")
        print(f"   - With schema: {with_schema}/{len(models)}")
        print(f"   - Categories: {categories}")
        
        # Итоговый статус
        print("\n" + "=" * 80)
        if len(self.errors) == 0:
            print("✅ VALIDATION PASSED")
        else:
            print("❌ VALIDATION FAILED")
        print("=" * 80)


def main():
    """Main function"""
    
    registry_file = Path("models/KIE_SOURCE_OF_TRUTH.json")
    
    if not registry_file.exists():
        print(f"❌ Registry not found: {registry_file}")
        return
    
    validator = NewRegistryValidator()
    success = validator.validate_registry(registry_file)
    
    if success:
        print("\n✅ Registry is valid and ready for production!")
    else:
        print("\n❌ Registry has errors, please fix them before using")


if __name__ == "__main__":
    main()
