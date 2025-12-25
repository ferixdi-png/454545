#!/usr/bin/env python3
"""
Model Validator - проверяет модели через реальные API вызовы

Для каждой модели делает тестовый запрос чтобы проверить:
- model_id правильный
- input_schema валидный
- модель действительно работает
"""
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.api.kie_client import KieApiClient
from app.utils.safe_test_mode import is_model_safe_for_testing

logger = logging.getLogger(__name__)


class ModelValidator:
    """Валидатор моделей через реальные API вызовы."""
    
    def __init__(self, api_key: Optional[str] = None, max_cost_per_test: float = 2.0):
        self.api_key = api_key or os.getenv("KIE_API_KEY")
        if not self.api_key:
            raise ValueError("KIE_API_KEY required")
        
        self.client = KieApiClient(api_key=self.api_key)
        self.max_cost_per_test = max_cost_per_test
        self.total_spent = 0.0
        self.results = []
    
    def _get_minimal_input(self, model: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate minimal valid input for model testing.
        
        Args:
            model: Model dict with input_schema
        
        Returns:
            Minimal input params dict
        """
        schema = model.get('input_schema', {})
        properties = schema.get('properties', {})
        required = schema.get('required', [])
        
        input_params = {}
        
        # Fill required fields
        for field in required:
            prop = properties.get(field, {})
            field_type = prop.get('type', 'string')
            
            if field == 'prompt':
                input_params[field] = "test"
            elif field == 'aspect_ratio':
                # Use first enum value or default
                enum_values = prop.get('enum', ['1:1'])
                input_params[field] = enum_values[0]
            elif field == 'duration':
                enum_values = prop.get('enum', ['5.0s'])
                input_params[field] = enum_values[0]
            elif field == 'resolution':
                enum_values = prop.get('enum', ['720p'])
                input_params[field] = enum_values[0]
            elif field_type == 'string':
                input_params[field] = "test"
            elif field_type == 'number':
                input_params[field] = prop.get('default', 1)
            elif field_type == 'boolean':
                input_params[field] = prop.get('default', False)
        
        return input_params
    
    async def validate_model(self, model: Dict[str, Any], skip_if_expensive: bool = True) -> Dict[str, Any]:
        """
        Validate single model through API.
        
        Args:
            model: Model dict
            skip_if_expensive: Skip if cost > max_cost_per_test
        
        Returns:
            {
                'model_id': str,
                'verified': bool,
                'error': str or None,
                'cost_rub': float,
                'test_result': dict
            }
        """
        model_id = model['model_id']
        
        logger.info(f"\n{'='*60}")
        logger.info(f"VALIDATING: {model_id}")
        logger.info(f"{'='*60}\n")
        
        # Check cost estimate
        pricing = model.get('pricing', {})
        estimated_cost_rub = pricing.get('rub_per_use', 0.0)
        
        if skip_if_expensive and estimated_cost_rub > self.max_cost_per_test:
            logger.warning(
                f"⏭ Skipping {model_id}: "
                f"estimated cost {estimated_cost_rub:.2f} RUB > "
                f"limit {self.max_cost_per_test:.2f} RUB"
            )
            return {
                'model_id': model_id,
                'verified': False,
                'skipped': True,
                'reason': f'Too expensive: {estimated_cost_rub:.2f} RUB',
                'error': None,
                'cost_rub': 0.0
            }
        
        # Generate minimal input
        try:
            input_params = self._get_minimal_input(model)
            logger.info(f"Test input: {input_params}")
        except Exception as e:
            logger.error(f"❌ Failed to generate test input: {e}")
            return {
                'model_id': model_id,
                'verified': False,
                'error': f'Invalid schema: {e}',
                'cost_rub': 0.0
            }
        
        # Try API call
        try:
            # Create task only (don't wait for completion to save credits)
            payload = {
                "model": model_id,
                "input": input_params
            }
            
            create_resp = await self.client.create_task(payload)
            
            if create_resp.get("code") == 200:
                task_id = create_resp.get("data", {}).get("taskId")
                logger.info(f"✅ Task created: {task_id}")
                
                # Success - model accepts requests
                result = {
                    'model_id': model_id,
                    'verified': True,
                    'error': None,
                    'task_id': task_id,
                    'cost_rub': estimated_cost_rub,
                    'test_result': 'task_created'
                }
                
                self.total_spent += estimated_cost_rub
                
            else:
                error_msg = create_resp.get("msg", "Unknown error")
                logger.error(f"❌ API error: {error_msg}")
                
                result = {
                    'model_id': model_id,
                    'verified': False,
                    'error': error_msg,
                    'cost_rub': 0.0,
                    'test_result': create_resp
                }
        
        except Exception as e:
            logger.error(f"❌ Exception: {e}")
            result = {
                'model_id': model_id,
                'verified': False,
                'error': str(e),
                'cost_rub': 0.0
            }
        
        return result
    
    async def validate_all(
        self,
        models: List[Dict[str, Any]],
        max_models: int = 10,
        max_budget: float = 50.0
    ) -> List[Dict[str, Any]]:
        """
        Validate multiple models with budget limits.
        
        Args:
            models: List of model dicts
            max_models: Maximum number to test
            max_budget: Maximum RUB to spend
        
        Returns:
            List of validation results
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"VALIDATION PLAN")
        logger.info(f"{'='*60}")
        logger.info(f"Models to validate: {len(models)}")
        logger.info(f"Max models: {max_models}")
        logger.info(f"Max budget: {max_budget:.2f} RUB")
        logger.info(f"{'='*60}\n")
        
        # Sort by estimated cost (cheapest first)
        sorted_models = sorted(
            models,
            key=lambda m: m.get('pricing', {}).get('rub_per_use', float('inf'))
        )
        
        results = []
        
        for i, model in enumerate(sorted_models[:max_models]):
            if self.total_spent >= max_budget:
                logger.warning(f"\n⚠️ Budget limit reached: {self.total_spent:.2f}/{max_budget:.2f} RUB")
                break
            
            result = await self.validate_model(model, skip_if_expensive=True)
            results.append(result)
            
            logger.info(f"\nProgress: {i+1}/{min(max_models, len(sorted_models))}")
            logger.info(f"Spent so far: {self.total_spent:.2f} RUB")
        
        return results
    
    def print_summary(self):
        """Print validation summary."""
        verified = sum(1 for r in self.results if r.get('verified', False))
        skipped = sum(1 for r in self.results if r.get('skipped', False))
        failed = len(self.results) - verified - skipped
        
        logger.info(f"\n{'='*60}")
        logger.info(f"VALIDATION SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Total tested: {len(self.results)}")
        logger.info(f"✅ Verified: {verified}")
        logger.info(f"⏭ Skipped: {skipped}")
        logger.info(f"❌ Failed: {failed}")
        logger.info(f"💰 Total spent: {self.total_spent:.2f} RUB")
        logger.info(f"{'='*60}\n")


async def main():
    """Test validator."""
    logging.basicConfig(level=logging.INFO)
    
    # Test model
    test_model = {
        'model_id': 'z-image',
        'pricing': {'rub_per_use': 0.63},
        'input_schema': {
            'required': ['prompt', 'aspect_ratio'],
            'properties': {
                'prompt': {'type': 'string'},
                'aspect_ratio': {'type': 'string', 'enum': ['1:1']}
            }
        }
    }
    
    validator = ModelValidator()
    result = await validator.validate_model(test_model)
    
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    import json
    asyncio.run(main())
