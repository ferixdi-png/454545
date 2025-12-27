#!/usr/bin/env python3
"""
Smoke test for cheapest Kie.ai models.

SAFETY FEATURES:
1. SAFE_TEST_MODE enforced by default
2. Only tests TOP-10 cheapest models
3. Budget limit: MAX_TEST_CREDITS_PER_RUN
4. Total budget tracking across runs
5. Blocks expensive models automatically

Usage:
    python scripts/smoke_generate_cheapest.py [--runs N] [--budget CREDITS]
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pricing.free_models import get_free_models, get_model_price
from app.api.kie_client import KieApiClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Safety constants
SAFE_TEST_MODE = os.getenv("SAFE_TEST_MODE", "1") == "1"
MAX_TEST_CREDITS_PER_RUN = float(os.getenv("MAX_TEST_CREDITS_PER_RUN", "2.0"))
MAX_TOTAL_BUDGET = float(os.getenv("MAX_TOTAL_TEST_BUDGET", "50.0"))

# Results file
RESULTS_FILE = Path("artifacts/smoke_test_results.json")


class SmokeTester:
    """Smoke tester for cheap models."""
    
    def __init__(self):
        self.api_client = None
        self.results: List[Dict[str, Any]] = []
        self.total_credits_spent = 0.0
    
    def load_cheapest_models(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Load cheapest models for testing.
        
        Args:
            limit: Max number of models to load
        
        Returns:
            List of model dicts with pricing
        """
        try:
            source_file = Path("models/kie_models_source_of_truth.json")
            
            if not source_file.exists():
                logger.error(f"Source of truth not found: {source_file}")
                return []
            
            with open(source_file, 'r') as f:
                data = json.load(f)
            
            models = data.get("models", [])
            
            # Filter enabled models only
            enabled = [m for m in models if m.get("enabled", True)]
            
            # Sort by credits cost
            sorted_models = sorted(
                enabled,
                key=lambda m: m.get("pricing", {}).get("credits_per_use", float('inf'))
            )
            
            # Take top N
            cheapest = sorted_models[:limit]
            
            logger.info(f"Loaded {len(cheapest)} cheapest models")
            for m in cheapest:
                credits = m.get("pricing", {}).get("credits_per_use", 0)
                logger.info(f"  - {m['model_id']}: {credits} credits")
            
            return cheapest
        
        except Exception as e:
            logger.error(f"Failed to load models: {e}", exc_info=True)
            return []
    
    def is_model_safe(self, model: Dict[str, Any]) -> tuple[bool, str]:
        """
        Check if model is safe to test.
        
        Args:
            model: Model dict
        
        Returns:
            (is_safe, reason)
        """
        if not SAFE_TEST_MODE:
            return True, "SAFE_TEST_MODE disabled"
        
        credits = model.get("pricing", {}).get("credits_per_use", 0)
        
        if credits > MAX_TEST_CREDITS_PER_RUN:
            return False, f"Too expensive: {credits} > {MAX_TEST_CREDITS_PER_RUN} credits"
        
        if self.total_credits_spent + credits > MAX_TOTAL_BUDGET:
            return False, f"Budget exceeded: {self.total_credits_spent + credits} > {MAX_TOTAL_BUDGET}"
        
        return True, "OK"
    
    def get_test_payload(self, model: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate test payload for model.
        
        Args:
            model: Model dict
        
        Returns:
            Test payload for createTask
        """
        model_id = model["model_id"]
        category = model.get("category", "")
        
        # Build minimal test payload based on category
        if "text-to-image" in category:
            return {
                "model": model_id,
                "prompt": "A simple test image",
                "width": 512,
                "height": 512
            }
        
        elif "text-to-video" in category:
            return {
                "model": model_id,
                "prompt": "Test video",
                "duration": 2,
                "resolution": "480p"
            }
        
        elif "image-to-image" in category:
            # Need test image URL
            return {
                "model": model_id,
                "image": "https://via.placeholder.com/512",
                "prompt": "Transform this"
            }
        
        elif "upscale" in category:
            return {
                "model": model_id,
                "image": "https://via.placeholder.com/256",
                "scale": 2
            }
        
        elif "text-to-speech" in category or "tts" in category:
            return {
                "model": model_id,
                "text": "Test audio generation",
                "voice": "default"
            }
        
        else:
            # Generic payload
            return {
                "model": model_id,
                "prompt": "Test generation"
            }
    
    async def test_model(self, model: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test single model.
        
        Args:
            model: Model dict
        
        Returns:
            Test result dict
        """
        model_id = model["model_id"]
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing: {model_id}")
        logger.info(f"{'='*60}")
        
        # Safety check
        is_safe, reason = self.is_model_safe(model)
        
        if not is_safe:
            logger.warning(f"⚠️  BLOCKED: {reason}")
            return {
                "model_id": model_id,
                "status": "blocked",
                "reason": reason,
                "credits_spent": 0,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Get API client
        if not self.api_client:
            try:
                self.api_client = KieApiClient()
            except ValueError as e:
                logger.error(f"Cannot create API client: {e}")
                return {
                    "model_id": model_id,
                    "status": "error",
                    "error": str(e),
                    "credits_spent": 0,
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        # Build payload
        payload = self.get_test_payload(model)
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")
        
        # Run test
        start_time = datetime.utcnow()
        
        try:
            # Create task
            create_response = await self.api_client.create_task(payload)
            
            if "error" in create_response or create_response.get("state") == "fail":
                error_msg = create_response.get("error", "Unknown error")
                logger.error(f"❌ Create task failed: {error_msg}")
                
                return {
                    "model_id": model_id,
                    "status": "error",
                    "error": error_msg,
                    "credits_spent": 0,
                    "timestamp": start_time.isoformat()
                }
            
            task_id = create_response.get("taskId")
            
            if not task_id:
                logger.error(f"❌ No taskId in response: {create_response}")
                return {
                    "model_id": model_id,
                    "status": "error",
                    "error": "No taskId returned",
                    "credits_spent": 0,
                    "timestamp": start_time.isoformat()
                }
            
            logger.info(f"✅ Task created: {task_id}")
            
            # Poll for result (simplified - just check once)
            await asyncio.sleep(5)
            
            record_info = await self.api_client.get_record_info(task_id)
            state = record_info.get("state", "unknown")
            
            logger.info(f"Task state: {state}")
            
            # Calculate credits spent
            credits = model.get("pricing", {}).get("credits_per_use", 0)
            self.total_credits_spent += credits
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            result = {
                "model_id": model_id,
                "status": "success" if state == "success" else "waiting",
                "task_id": task_id,
                "state": state,
                "credits_spent": credits,
                "duration_seconds": duration,
                "timestamp": start_time.isoformat()
            }
            
            logger.info(f"✅ Test complete: {state} ({credits} credits, {duration:.1f}s)")
            
            return result
        
        except Exception as e:
            logger.error(f"❌ Test failed: {e}", exc_info=True)
            
            return {
                "model_id": model_id,
                "status": "error",
                "error": str(e),
                "credits_spent": 0,
                "timestamp": start_time.isoformat()
            }
    
    async def run_tests(self, num_models: int = 10, runs_per_model: int = 1):
        """
        Run smoke tests.
        
        Args:
            num_models: Number of models to test
            runs_per_model: Number of runs per model
        """
        logger.info(f"\n{'='*60}")
        logger.info("SMOKE TEST START")
        logger.info(f"{'='*60}")
        logger.info(f"SAFE_TEST_MODE: {SAFE_TEST_MODE}")
        logger.info(f"MAX_TEST_CREDITS_PER_RUN: {MAX_TEST_CREDITS_PER_RUN}")
        logger.info(f"MAX_TOTAL_BUDGET: {MAX_TOTAL_BUDGET}")
        logger.info(f"Models to test: {num_models}")
        logger.info(f"Runs per model: {runs_per_model}")
        logger.info(f"{'='*60}\n")
        
        # Load models
        models = self.load_cheapest_models(limit=num_models)
        
        if not models:
            logger.error("No models to test")
            return
        
        # Run tests
        for model in models:
            for run in range(runs_per_model):
                if runs_per_model > 1:
                    logger.info(f"\nRun {run + 1}/{runs_per_model} for {model['model_id']}")
                
                result = await self.test_model(model)
                self.results.append(result)
                
                # Check budget
                if self.total_credits_spent >= MAX_TOTAL_BUDGET:
                    logger.warning(f"⚠️  Budget limit reached: {self.total_credits_spent}/{MAX_TOTAL_BUDGET}")
                    break
            
            if self.total_credits_spent >= MAX_TOTAL_BUDGET:
                break
        
        # Summary
        self.print_summary()
        self.save_results()
    
    def print_summary(self):
        """Print test summary."""
        logger.info(f"\n{'='*60}")
        logger.info("SMOKE TEST SUMMARY")
        logger.info(f"{'='*60}")
        
        total_tests = len(self.results)
        success = sum(1 for r in self.results if r["status"] == "success")
        blocked = sum(1 for r in self.results if r["status"] == "blocked")
        errors = sum(1 for r in self.results if r["status"] == "error")
        
        logger.info(f"Total tests: {total_tests}")
        logger.info(f"Success: {success}")
        logger.info(f"Blocked: {blocked}")
        logger.info(f"Errors: {errors}")
        logger.info(f"Total credits spent: {self.total_credits_spent:.2f}")
        logger.info(f"{'='*60}\n")
    
    def save_results(self):
        """Save results to file."""
        RESULTS_FILE.parent.mkdir(exist_ok=True)
        
        output = {
            "timestamp": datetime.utcnow().isoformat(),
            "safe_mode": SAFE_TEST_MODE,
            "total_credits_spent": self.total_credits_spent,
            "results": self.results
        }
        
        with open(RESULTS_FILE, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"✅ Results saved to {RESULTS_FILE}")


async def main():
    parser = argparse.ArgumentParser(description="Smoke test cheapest models")
    parser.add_argument("--runs", type=int, default=10, help="Number of models to test")
    parser.add_argument("--runs-per-model", type=int, default=1, help="Runs per model")
    args = parser.parse_args()
    
    tester = SmokeTester()
    await tester.run_tests(num_models=args.runs, runs_per_model=args.runs_per_model)


if __name__ == "__main__":
    asyncio.run(main())
