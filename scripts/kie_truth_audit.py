"""
Kie.ai Truth Audit - validates source of truth integrity.

Checks:
1. All models have model_id, category, pricing, input_schema
2. Pricing is valid (USD, credits, RUB all populated)
3. TOP-5 cheapest models are correctly identified
4. No missing schemas or broken references
5. Categories are valid

CRITICAL:
- Source must be from Kie API, not manual/scraped
- Prices must be in sync with Kie.ai official pricing
- Free models = TOP-5 cheapest by cost
"""
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Set

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pricing.free_models import get_free_models

# Known valid categories from Kie.ai
VALID_CATEGORIES = {
    "text-to-image", "image-to-image", "text-to-video", "image-to-video", "video-to-video",
    "text-to-speech", "speech-to-text", "audio-generation",
    "upscale", "ocr", "lip-sync", "background-removal",
    "watermark-removal", "music-generation", "sound-effects",
    "general", "other"
}

# Known model types to skip (not AI models)
SKIP_PATTERNS = [
    "_processor",
    "ARCHITECTURE",
    "AI_INTEGRATION",
    "test_results"
]


def should_skip_model(model_id: str) -> bool:
    """Check if model should be skipped (not a real AI model)."""
    model_lower = model_id.lower()
    
    # Skip processors
    if any(pattern.lower() in model_lower for pattern in SKIP_PATTERNS):
        return True
    
    # Skip all-caps constants
    if model_id.isupper():
        return True
    
    return False



def audit_model(model: Dict[str, Any]) -> List[str]:
    """
    Audit single model for completeness.
    
    Returns:
        List of issues (empty if OK)
    """
    issues = []
    model_id = model.get("model_id")
    
    if not model_id:
        issues.append("Model missing 'model_id'")
        return issues
    
    # Check required fields
    if "category" not in model:
        issues.append(f"{model_id}: missing 'category'")
    elif model["category"] not in VALID_CATEGORIES:
        issues.append(f"{model_id}: unknown category '{model['category']}'")
    
    # Check pricing
    if "pricing" not in model:
        issues.append(f"{model_id}: missing 'pricing'")
    else:
        pricing = model["pricing"]
        
        if not isinstance(pricing, dict):
            issues.append(f"{model_id}: pricing must be dict, got {type(pricing)}")
        else:
            # Check all price fields present
            required_price_fields = ["usd_per_use", "credits_per_use", "rub_per_use"]
            for field in required_price_fields:
                if field not in pricing:
                    issues.append(f"{model_id}: pricing missing '{field}'")
                else:
                    try:
                        val = float(pricing[field])
                        if val < 0:
                            issues.append(f"{model_id}: pricing.{field} cannot be negative")
                    except (ValueError, TypeError):
                        issues.append(f"{model_id}: pricing.{field} must be numeric")
    
    # Check input_schema
    if "input_schema" not in model:
        issues.append(f"{model_id}: missing 'input_schema'")
    else:
        schema = model["input_schema"]
        
        if not isinstance(schema, dict):
            issues.append(f"{model_id}: input_schema must be dict")
    
    if "output_type" not in model:
        issues.append(f"{model_id}: missing 'output_type'")
    
    if "enabled" not in model:
        issues.append(f"{model_id}: missing 'enabled' flag")
    
    return issues


def load_source_of_truth(registry_path: Path) -> Dict[str, Any]:
    """Load source of truth file."""
    if not registry_path.exists():
        return {"models": []}
    
    with open(registry_path, 'r') as f:
        return json.load(f)


def generate_report(registry_path: Path) -> Dict[str, Any]:
    """Generate full audit report."""
    data = load_source_of_truth(registry_path)
    
    models = data.get("models", [])
    
    if not models:
        return {
            "total_models": 0,
            "enabled_models": 0,
            "categories": {},
            "models_with_issues": 0,
            "total_issues": 0,
            "issues": ["No models found in source of truth"],
            "status": "EMPTY",
            "top_10_cheapest": []
        }
    
    total = len(models)
    enabled = [m for m in models if m.get("enabled", True)]
    total_enabled = len(enabled)
    
    all_issues = []
    models_with_issues = []
    
    for model in models:
        issues = audit_model(model)
        if issues:
            models_with_issues.append(model.get("model_id", "UNKNOWN"))
            all_issues.extend(issues)
    
    # Category breakdown
    categories = {}
    for model in enabled:
        cat = model.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1
    
    # Top 10 cheapest models
    sorted_models = sorted(
        enabled,
        key=lambda m: m.get("pricing", {}).get("rub_per_use", float('inf'))
    )
    top_10 = sorted_models[:10]
    
    top_10_info = []
    for m in top_10:
        top_10_info.append({
            "model_id": m.get("model_id"),
            "category": m.get("category"),
            "price_rub": m.get("pricing", {}).get("rub_per_use", 0),
            "price_usd": m.get("pricing", {}).get("usd_per_use", 0),
            "credits": m.get("pricing", {}).get("credits_per_use", 0)
        })
    
    # Check free models consistency
    try:
        free_model_ids = get_free_models()
        top_5 = [m["model_id"] for m in top_10[:5]]
        
        if set(free_model_ids) != set(top_5):
            all_issues.append(
                f"Free models mismatch: expected {top_5}, got {free_model_ids}"
            )
    except Exception as e:
        all_issues.append(f"Failed to check free models: {e}")
    
    return {
        "total_models": total,
        "enabled_models": total_enabled,
        "categories": categories,
        "models_with_issues": len(models_with_issues),
        "total_issues": len(all_issues),
        "issues": all_issues,
        "status": "OK" if not all_issues else "ISSUES_FOUND",
        "top_10_cheapest": top_10_info,
        "source": data.get("source", "unknown"),
        "version": data.get("version", "unknown"),
        "timestamp": data.get("timestamp", "unknown")
    }


def print_report(report: Dict[str, Any]):
    """Print formatted report."""
    print("=" * 60)
    print("KIE.AI SOURCE OF TRUTH AUDIT")
    print("=" * 60)
    print(f"Source: {report.get('source', 'unknown')}")
    print(f"Version: {report.get('version', 'unknown')}")
    print(f"Timestamp: {report.get('timestamp', 'unknown')}")
    print()
    
    print(f"📊 Total models: {report['total_models']}")
    print(f"✅ Enabled models: {report['enabled_models']}")
    print()
    
    if report['categories']:
        print("📂 Categories:")
        for cat, count in sorted(report['categories'].items(), key=lambda x: -x[1]):
            print(f"   {cat:25s}: {count:3d} models")
        print()
    
    if report['top_10_cheapest']:
        print("💰 TOP-10 Cheapest Models:")
        for i, m in enumerate(report['top_10_cheapest'], 1):
            free_mark = "🆓" if i <= 5 else "  "
            print(
                f"   {free_mark} {i:2d}. {m['model_id']:40s} "
                f"{m['price_rub']:8.2f} RUB ({m['price_usd']:.4f} USD, {m['credits']:.2f} credits)"
            )
        print()
    
    if report['total_issues'] == 0:
        print("✅ ALL CHECKS PASSED")
        print()
        print("🎉 Registry is production-ready!")
        return 0
    else:
        print(f"❌ FOUND {report['total_issues']} ISSUES")
        print(f"   Models with issues: {report['models_with_issues']}")
        print()
        
        print("Issues:")
        for issue in report['issues'][:20]:  # Show first 20
            print(f"   - {issue}")
        
        if len(report['issues']) > 20:
            print(f"   ... and {len(report['issues']) - 20} more")
        
        print()
        print("❌ Registry has issues - run sync to fix")
        return 1


def main():
    """Run audit and print report."""
    repo_root = Path(__file__).parent.parent
    registry_path = repo_root / "models" / "kie_models_source_of_truth.json"
    
    if not registry_path.exists():
        print(f"❌ ERROR: Registry not found at {registry_path}")
        print(f"   Run: python scripts/kie_sync_registry.py")
        sys.exit(1)
    
    report = generate_report(registry_path)
    exit_code = print_report(report)
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

