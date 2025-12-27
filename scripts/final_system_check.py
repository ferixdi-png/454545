#!/usr/bin/env python3
"""
Final comprehensive system check.
Verifies all critical paths and invariants.
"""
import sys
import os
import importlib.util
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def check_imports():
    """Check all critical imports."""
    errors = []
    
    critical_modules = [
        'app.utils.singleton_lock',
        'app.storage.pg_storage',
        'app.kie.builder',
        'app.kie.parser',
        'app.kie.generator',
        'app.kie.validator',
        'app.payments.charges',
        'app.payments.integration',
        'app.ocr.tesseract_processor',
        'bot.handlers.zero_silence',
        'bot.handlers.error_handler',
    ]
    
    for module_name in critical_modules:
        try:
            spec = importlib.util.find_spec(module_name)
            if spec is None:
                errors.append(f"Module not found: {module_name}")
            else:
                logger.info(f"[OK] {module_name}")
        except Exception as e:
            errors.append(f"Import error for {module_name}: {e}")
    
    return errors

def check_entrypoint():
    """Check main entrypoint."""
    entrypoint = Path("main_render.py")
    if not entrypoint.exists():
        return ["main_render.py not found"]
    
    try:
        with open(entrypoint, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'create_bot_application' not in content:
                return ["create_bot_application not found in main_render.py"]
            if 'SingletonLock' not in content or 'singleton_lock.acquire' not in content:
                return ["SingletonLock not properly used in main_render.py"]
    except Exception as e:
        return [f"Error reading main_render.py: {e}"]
    
    logger.info("[OK] main_render.py structure")
    return []

def check_source_of_truth():
    """Check source of truth file."""
    sot_file = Path("models/kie_models_source_of_truth.json")
    if not sot_file.exists():
        return ["Source of truth file not found"]
    
    try:
        import json
        with open(sot_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not data.get('models'):
                return ["Source of truth is empty"]
            logger.info(f"[OK] Source of truth: {len(data.get('models', []))} models")
    except Exception as e:
        return [f"Error reading source of truth: {e}"]
    
    return []

def check_payment_invariants():
    """Check payment code for invariants."""
    errors = []
    
    charges_file = Path("app/payments/charges.py")
    if charges_file.exists():
        with open(charges_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'commit_charge' in content and 'release_charge' in content:
                logger.info("[OK] Payment invariants code present")
            else:
                errors.append("Payment methods missing")
    
    return errors

def check_model_contract():
    """Check model contract enforcement."""
    errors = []
    
    validator_file = Path("app/kie/validator.py")
    if not validator_file.exists():
        errors.append("Model validator not found")
    else:
        with open(validator_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'ModelContractError' in content and 'validate_model_inputs' in content:
                logger.info("[OK] Model contract validator present")
            else:
                errors.append("Model validator incomplete")
    
    return errors

def main():
    """Run all checks."""
    logger.info("=" * 60)
    logger.info("FINAL SYSTEM CHECK")
    logger.info("=" * 60)
    
    all_errors = []
    
    # Check imports
    logger.info("\n1. Checking imports...")
    all_errors.extend(check_imports())
    
    # Check entrypoint
    logger.info("\n2. Checking entrypoint...")
    all_errors.extend(check_entrypoint())
    
    # Check source of truth
    logger.info("\n3. Checking source of truth...")
    all_errors.extend(check_source_of_truth())
    
    # Check payment invariants
    logger.info("\n4. Checking payment invariants...")
    all_errors.extend(check_payment_invariants())
    
    # Check model contract
    logger.info("\n5. Checking model contract...")
    all_errors.extend(check_model_contract())
    
    # Summary
    logger.info("\n" + "=" * 60)
    if all_errors:
        logger.error(f"FOUND {len(all_errors)} ERRORS:")
        for error in all_errors:
            logger.error(f"  - {error}")
        return 1
    else:
        logger.info("ALL CHECKS PASSED")
        return 0

if __name__ == "__main__":
    sys.exit(main())

