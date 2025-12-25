#!/usr/bin/env python3
"""
Smoke tests на дешёвых моделях.

ПРАВИЛА:
1. Используются только модели из SAFE_TEST_MODE
2. Максимум MAX_TOTAL_TEST_BUDGET рублей на все тесты
3. Каждая генерация сохраняется в БД (для аудита)
4. Результаты пишутся в artifacts/smoke_test_results.json
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.api.kie_client import KieApiClient
from app.utils.safe_test_mode import (
    get_safe_test_models,
    get_test_budget_info,
    is_model_safe_for_testing
)
from app.pricing.free_models import get_model_price

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Test prompts для разных категорий
TEST_PROMPTS = {
    "text-to-image": [
        {
            "prompt": "A simple red apple on white background",
            "aspect_ratio": "1:1"
        },
        {
            "prompt": "A cute cat sitting in a garden",
            "aspect_ratio": "4:3"
        },
        {
            "prompt": "Modern minimalist logo with letter K",
            "aspect_ratio": "1:1"
        },
    ],
    "text-to-video": [
        {
            "prompt": "A bird flying in the sky",
            "duration": "5.0s",
            "resolution": "720p"
        },
    ],
}


class SmokeTestRunner:
    """Smoke test runner with budget tracking."""
    
    def __init__(self, max_runs: int = 10):
        self.max_runs = max_runs
        self.api_key = os.getenv("KIE_API_KEY")
        if not self.api_key:
            raise ValueError("KIE_API_KEY not set")
        
        self.client = KieApiClient(api_key=self.api_key)
        self.results: List[Dict[str, Any]] = []
        self.total_spent_rub = 0.0
        self.budget_info = get_test_budget_info()
    
    async def run_test(
        self,
        model_id: str,
        category: str,
        input_params: Dict[str, Any],
        run_number: int
    ) -> Dict[str, Any]:
        """Run single test generation."""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"RUN #{run_number}: {model_id}")
        logger.info(f"Category: {category}")
        logger.info(f"Input: {input_params}")
        logger.info(f"{'='*60}\n")
        
        # Get pricing
        pricing = get_model_price(model_id)
        expected_cost = pricing.get("rub_per_use", 0.0)
        
        # Check budget
        if self.total_spent_rub + expected_cost > self.budget_info["max_total_budget"]:
            logger.warning(
                f"⚠️ Budget exceeded! "
                f"Spent: {self.total_spent_rub:.2f} RUB, "
                f"Would spend: {expected_cost:.2f} RUB, "
                f"Budget: {self.budget_info['max_total_budget']:.2f} RUB"
            )
            return {
                "run": run_number,
                "model_id": model_id,
                "category": category,
                "status": "skipped",
                "reason": "budget_exceeded",
                "timestamp": datetime.now().isoformat()
            }
        
        # Run generation
        start_time = datetime.now()
        
        try:
            result = await self.client.generate(
                model_id=model_id,
                input_params=input_params,
                max_wait=120  # 2 min timeout
            )
            
            end_time = datetime.now()
            duration_sec = (end_time - start_time).total_seconds()
            
            # Update spent budget (if not free)
            if not pricing.get("is_free", False):
                self.total_spent_rub += expected_cost
            
            test_result = {
                "run": run_number,
                "model_id": model_id,
                "category": category,
                "input": input_params,
                "status": result.get("state"),
                "task_id": result.get("task_id"),
                "result_urls": result.get("result_urls", []),
                "error": result.get("error"),
                "cost_time_ms": result.get("cost_time_ms", 0),
                "duration_sec": duration_sec,
                "expected_cost_rub": expected_cost,
                "is_free": pricing.get("is_free", False),
                "timestamp": start_time.isoformat()
            }
            
            if result.get("state") == "success":
                logger.info(f"✅ SUCCESS! Duration: {duration_sec:.1f}s, Cost: {expected_cost} RUB")
                logger.info(f"   Results: {len(result.get('result_urls', []))} files")
            else:
                logger.error(f"❌ FAILED! Error: {result.get('error')}")
            
            return test_result
        
        except Exception as e:
            logger.error(f"❌ EXCEPTION: {e}", exc_info=True)
            return {
                "run": run_number,
                "model_id": model_id,
                "category": category,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def run_all_tests(self):
        """Run all smoke tests."""
        
        logger.info("="*60)
        logger.info("🚀 STARTING SMOKE TESTS")
        logger.info("="*60)
        logger.info(f"Budget: {self.budget_info['max_total_budget']} RUB")
        logger.info(f"Max runs: {self.max_runs}")
        logger.info(f"Safe models: {self.budget_info['allowed_models']}")
        logger.info("="*60)
        logger.info("")
        
        # Load models
        safe_models = get_safe_test_models()
        
        if not safe_models:
            logger.error("No safe models available for testing!")
            return
        
        # Load model registry to get categories
        from pathlib import Path
        import json
        
        registry_path = Path("models/kie_models_source_of_truth.json")
        with registry_path.open("r", encoding="utf-8") as f:
            registry = json.load(f)
        
        models_by_category = {}
        for model in registry.get("models", []):
            if model["model_id"] in safe_models:
                cat = model.get("category", "unknown")
                if cat not in models_by_category:
                    models_by_category[cat] = []
                models_by_category[cat].append(model)
        
        # Run tests
        run_number = 0
        
        for category, models in models_by_category.items():
            if category not in TEST_PROMPTS:
                logger.warning(f"No test prompts for category: {category}")
                continue
            
            for model in models:
                model_id = model["model_id"]
                
                # Test with each prompt for this category
                for prompt_data in TEST_PROMPTS[category]:
                    run_number += 1
                    
                    if run_number > self.max_runs:
                        logger.info(f"\n⚠️ Reached max runs limit: {self.max_runs}")
                        break
                    
                    result = await self.run_test(
                        model_id=model_id,
                        category=category,
                        input_params=prompt_data,
                        run_number=run_number
                    )
                    
                    self.results.append(result)
                
                if run_number >= self.max_runs:
                    break
            
            if run_number >= self.max_runs:
                break
        
        # Save results
        self.save_results()
        self.print_summary()
    
    def save_results(self):
        """Save test results to artifacts/"""
        output_dir = Path("artifacts")
        output_dir.mkdir(exist_ok=True)
        
        output_file = output_dir / "smoke_test_results.json"
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "budget": self.budget_info,
            "total_spent_rub": self.total_spent_rub,
            "total_runs": len(self.results),
            "results": self.results
        }
        
        with output_file.open("w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n💾 Results saved to: {output_file}")
    
    def print_summary(self):
        """Print test summary."""
        
        success_count = sum(1 for r in self.results if r.get("status") == "success")
        fail_count = sum(1 for r in self.results if r.get("status") == "fail")
        error_count = sum(1 for r in self.results if r.get("status") == "error")
        skipped_count = sum(1 for r in self.results if r.get("status") == "skipped")
        
        logger.info("\n" + "="*60)
        logger.info("📊 SMOKE TEST SUMMARY")
        logger.info("="*60)
        logger.info(f"Total runs: {len(self.results)}")
        logger.info(f"✅ Success: {success_count}")
        logger.info(f"❌ Failed: {fail_count}")
        logger.info(f"⚠️ Errors: {error_count}")
        logger.info(f"⏭ Skipped: {skipped_count}")
        logger.info(f"💰 Total spent: {self.total_spent_rub:.2f} RUB")
        logger.info(f"📊 Budget used: {self.total_spent_rub / self.budget_info['max_total_budget'] * 100:.1f}%")
        logger.info("="*60)
        
        if success_count > 0:
            logger.info("\n✅ At least one test passed! System is functional.")
        else:
            logger.error("\n❌ NO TESTS PASSED! System needs fixes.")


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Smoke tests for Kie.ai models")
    parser.add_argument("--runs", type=int, default=10, help="Maximum number of test runs")
    args = parser.parse_args()
    
    runner = SmokeTestRunner(max_runs=args.runs)
    await runner.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
