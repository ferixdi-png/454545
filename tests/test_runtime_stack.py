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
    from main_render import create_bot_application, preflight_webhook
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
    import main_render

    monkeypatch.setenv("BOT_MODE", "polling")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example")
    monkeypatch.setenv("DRY_RUN", "0")
    monkeypatch.setenv("PORT", "0")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:TEST")
    monkeypatch.setenv("KIE_API_KEY", "kie_test_key")

    async def fake_acquire_lock(*_args, **_kwargs):
        return False

    class DummyStorage:
        async def initialize(self):
            return None

        async def close(self):
            return None

    class DummySession:
        async def close(self):
            return None

    class DummyBot:
        session = DummySession()

    start_polling_called = False

    class DummyDispatcher:
        async def start_polling(self, *_args, **_kwargs):
            nonlocal start_polling_called
            start_polling_called = True

    class DummyEvent:
        async def wait(self):
            return None

    class DummyLock:
        async def acquire(self, *args, **kwargs):
            return await fake_acquire_lock(*args, **kwargs)
        async def release(self):
            pass

    monkeypatch.setattr(main_render, "SingletonLock", lambda *_args, **_kwargs: DummyLock())
    monkeypatch.setattr(main_render, "PostgresStorage", lambda *_args, **_kwargs: DummyStorage())
    monkeypatch.setattr(main_render, "create_bot_application", lambda: (DummyDispatcher(), DummyBot()))
    monkeypatch.setattr(main_render.asyncio, "Event", lambda: DummyEvent())

    await main_render.main()

    assert start_polling_called is False
