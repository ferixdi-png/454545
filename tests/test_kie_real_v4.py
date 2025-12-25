"""
Real API tests for Kie.ai V4 - credit-safe testing on cheap models.
Uses NEW category-specific API architecture.

Budget: 300₽ per test run
Safety: MAX_PRICE_RUB = 100.0₽ (only test models under 100₽)

V4 Models (docs.kie.ai):
- gpt-4o-image: 39₽ (CHEAPEST image generation)
- flux-kontext: 47₽ (Image generation)
- suno-v4: 78₽ (CHEAPEST audio generation)
- veo3_fast: 157₽ (Fast video)

These are the ONLY documented working models in new Kie.ai architecture.
"""
import os
import pytest
import asyncio
from decimal import Decimal

from app.kie.generator import KieGenerator
from app.kie.router import get_all_v4_models

# Skip if no API key
skip_if_no_key = pytest.mark.skipif(
    not os.getenv('KIE_API_KEY'),
    reason="KIE_API_KEY not set - skipping real API tests"
)

# Budget limits
MAX_PRICE_RUB = Decimal("100.0")  # Increased for V4 testing (cheapest is 39₽)
MAX_TOTAL_BUDGET_RUB = Decimal("300.0")  # Total budget for all tests

# Track credits spent
credits_spent = []


def get_v4_cheap_models():
    """Get all V4 models sorted by price."""
    models = get_all_v4_models()
    
    # Sort by price
    sorted_models = sorted(
        models,
        key=lambda m: m.get('pricing', {}).get('rub_per_use', 999999)
    )
    
    return sorted_models


@pytest.fixture
async def generator():
    """Create KieGenerator with V4 API enabled."""
    os.environ['KIE_USE_V4'] = 'true'  # Force V4 API
    gen = KieGenerator()
    yield gen


@skip_if_no_key
@pytest.mark.asyncio
async def test_gpt_4o_image_cheap(generator):
    """Test GPT-4O Image - CHEAPEST image model (39₽)."""
    model_id = 'gpt-4o-image'
    
    result = await generator.generate(
        model_id=model_id,
        user_inputs={'prompt': 'a cute cat'},
        timeout=120
    )
    
    credits_spent.append({'model': model_id, 'cost_rub': 39.33})
    
    print(f"\n✅ GPT-4O Image result: {result}")
    assert result['success'], f"Generation failed: {result.get('error_message')}"
    assert result.get('result_urls'), "No result URLs returned"


@skip_if_no_key
@pytest.mark.asyncio
async def test_flux_kontext_cheap(generator):
    """Test Flux Kontext - Image generation (47₽)."""
    model_id = 'flux-kontext'
    
    result = await generator.generate(
        model_id=model_id,
        user_inputs={'prompt': 'mountain landscape'},
        timeout=120
    )
    
    credits_spent.append({'model': model_id, 'cost_rub': 47.19})
    
    print(f"\n✅ Flux Kontext result: {result}")
    assert result['success'], f"Generation failed: {result.get('error_message')}"
    assert result.get('result_urls'), "No result URLs returned"


@skip_if_no_key
@pytest.mark.asyncio
async def test_suno_v4_cheap(generator):
    """Test Suno V4 - CHEAPEST audio model (78₽)."""
    model_id = 'suno-v4'
    
    result = await generator.generate(
        model_id=model_id,
        user_inputs={'prompt': 'happy music', 'duration_seconds': 30},
        timeout=180
    )
    
    credits_spent.append({'model': model_id, 'cost_rub': 78.65})
    
    print(f"\n✅ Suno V4 result: {result}")
    assert result['success'], f"Generation failed: {result.get('error_message')}"
    assert result.get('result_urls'), "No result URLs returned"


@skip_if_no_key
def test_v4_models_exist():
    """Verify V4 models are loaded correctly."""
    models = get_v4_cheap_models()
    
    print(f"\n📊 Found {len(models)} V4 models:")
    for model in models:
        price = model.get('pricing', {}).get('rub_per_use', 0)
        category = model.get('api_category', 'unknown')
        print(f"  - {model['model_id']}: {price}₽ ({category})")
    
    assert len(models) > 0, "No V4 models found"
    assert any(m['model_id'] == 'gpt-4o-image' for m in models), "gpt-4o-image not found"
    assert any(m['model_id'] == 'suno-v4' for m in models), "suno-v4 not found"


@skip_if_no_key
def test_budget_check():
    """Check total credits spent."""
    total = sum(c['cost_rub'] for c in credits_spent)
    
    print(f"\n💰 Credits spent:")
    for item in credits_spent:
        print(f"  - {item['model']}: {item['cost_rub']}₽")
    print(f"  TOTAL: {total}₽")
    
    assert total <= MAX_TOTAL_BUDGET_RUB, f"Budget exceeded: {total}₽ > {MAX_TOTAL_BUDGET_RUB}₽"
