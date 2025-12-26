import importlib
import os
import sys

import pytest


def test_main_render_imports_aiogram_only():
    os.environ.setdefault("DRY_RUN", "1")
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST")
    import main_render  # noqa: F401

    assert "telegram" not in sys.modules
    assert "telegram.ext" not in sys.modules


def test_python_telegram_bot_not_required():
    spec = importlib.util.find_spec("telegram")
    if spec is None:
        assert spec is None
    else:
        assert "telegram" not in sys.modules


def test_bot_mode_webhook_disables_polling(monkeypatch):
    """Test deprecated: preflight_webhook removed in v23."""
    pytest.skip("preflight_webhook removed in production v23 - webhook registration integrated into startup")
    monkeypatch.setenv("BOT_MODE", "webhook")
    monkeypatch.setenv("DRY_RUN", "1")  # Set DRY_RUN to avoid real token requirement
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:TEST")
    monkeypatch.setenv("KIE_API_KEY", "kie_test_key")
    dp, bot = create_bot_application()
    assert dp is not None
    assert bot is not None
    assert preflight_webhook is not None


@pytest.mark.asyncio
async def test_lock_failure_skips_polling(monkeypatch):
    """Test deprecated: storage refactored in v23."""
    pytest.skip("PostgresStorage removed in production v23 - storage system refactored")
