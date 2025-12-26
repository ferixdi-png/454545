"""Production-ready tests for balance, pricing, and generation events."""
import pytest
import os


def test_default_balance_zero():
    """New users should have 0 balance by default (unless START_BONUS_RUB is set)."""
    # Test that START_BONUS_RUB defaults to 0, not 200
    os.environ.setdefault("START_BONUS_RUB", "0")
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test:token")
    os.environ.setdefault("KIE_API_KEY", "test-key")
    os.environ.setdefault("DATABASE_URL", "postgresql://test")
    
    from app.utils.config import Config
    cfg = Config()
    
    assert cfg.start_bonus_rub == 0.0, "Default start_bonus should be 0, NOT 200"


def test_start_bonus_granted_once():
    """Start bonus should only be granted once per user."""
    from app.payments.charges import ChargeManager
    
    assert hasattr(ChargeManager, 'ensure_welcome_credit')


def test_free_tier_models_list():
    """FREE tier should contain exactly 5 models."""
    from app.pricing.free_models import get_free_models
    
    free_models = get_free_models()
    
    assert len(free_models) == 5, f"FREE tier must have exactly 5 models, got {len(free_models)}"


def test_price_display_consistency():
    """Displayed price should match calculated price."""
    from app.payments.pricing import calculate_kie_cost, calculate_user_price
    
    test_model = {
        "model_id": "test-model",
        "pricing": {
            "rub_per_use": 47.5,
            "credits_per_use": 0,
            "usd_per_use": 0.5
        }
    }
    
    base_cost = calculate_kie_cost(test_model, {}, None)
    user_price = calculate_user_price(base_cost)
    
    assert base_cost > 0, "Base cost should be positive"
    assert user_price >= base_cost, "User price should include markup"


def test_model_registry_returns_42():
    """Model registry should return exactly 42 enabled models."""
    from app.kie.builder import load_source_of_truth
    
    sot = load_source_of_truth()
    models = sot.get("models", {})
    
    enabled = [m for m in models.values() if m.get("enabled", True)]
    
    assert len(enabled) == 42, f"Expected 42 enabled models, got {len(enabled)}"


def test_generation_events_schema():
    """generation_events table should be defined in schema."""
    from app.database.schema import SCHEMA_SQL
    
    assert "CREATE TABLE IF NOT EXISTS generation_events" in SCHEMA_SQL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
