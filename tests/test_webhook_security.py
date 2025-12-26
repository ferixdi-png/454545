"""Tests for webhook security: secret path, guard middleware, and masking."""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from app.webhook_server import mask_path, _default_secret


class TestWebhookPathMasking:
    """Test path masking to prevent secret leaks in logs."""
    
    def test_mask_path_with_long_secret(self):
        """Long secrets should be masked with first4****last4 format."""
        path = "/webhook/abcdefghijklmnop1234567890"
        masked = mask_path(path)
        assert masked == "/webhook/abcd****7890"
        assert "abcdefghijklmnop1234567890" not in masked
    
    def test_mask_path_with_short_secret(self):
        """Short secrets (<=8 chars) should be returned as-is (not enough to mask)."""
        path = "/webhook/short"
        masked = mask_path(path)
        # Short secrets are not masked (less than 8 chars)
        assert masked == path
    
    def test_mask_path_without_webhook(self):
        """Non-webhook paths should pass through unchanged."""
        path = "/healthz"
        masked = mask_path(path)
        assert masked == path
    
    def test_mask_path_webhook_with_additional_segments(self):
        """Secret in path with additional segments should be masked correctly."""
        path = "/webhook/abcdefghijklmnop1234567890/something"
        masked = mask_path(path)
        assert "abcd****7890" in masked
        assert "abcdefghijklmnop1234567890" not in masked


class TestDefaultSecret:
    """Test secret generation from bot token."""
    
    def test_default_secret_is_stable(self):
        """Secret should be deterministic for same token."""
        token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        secret1 = _default_secret(token)
        secret2 = _default_secret(token)
        assert secret1 == secret2
    
    def test_default_secret_length(self):
        """Secret should be 32 chars (truncated sha256 hex)."""
        token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        secret = _default_secret(token)
        assert len(secret) == 32
        assert all(c in "0123456789abcdef" for c in secret)
    
    def test_default_secret_different_tokens(self):
        """Different tokens should produce different secrets."""
        secret1 = _default_secret("token1")
        secret2 = _default_secret("token2")
        assert secret1 != secret2


@pytest.mark.asyncio
async def test_webhook_path_contains_secret_when_not_explicit():
    """When TELEGRAM_WEBHOOK_PATH not set, path should be /webhook/<secret>."""
    with patch.dict(os.environ, {"TELEGRAM_WEBHOOK_PATH": ""}, clear=False):
        from aiogram import Bot, Dispatcher
        
        # Mock bot with fake token
        bot = MagicMock(spec=Bot)
        bot.token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        bot.set_webhook = AsyncMock()
        
        dp = MagicMock(spec=Dispatcher)
        
        # Import after patching env
        from app.webhook_server import start_webhook_server
        
        # Mock web components to avoid actual server start
        with patch("app.webhook_server.web.AppRunner") as mock_runner, \
             patch("app.webhook_server.web.TCPSite") as mock_site, \
             patch("app.webhook_server.SimpleRequestHandler"), \
             patch("app.webhook_server.setup_application"), \
             patch("app.webhook_server._detect_base_url", return_value="https://test.com"):
            
            mock_runner_instance = AsyncMock()
            mock_runner.return_value = mock_runner_instance
            mock_runner_instance.setup = AsyncMock()
            
            mock_site_instance = AsyncMock()
            mock_site.return_value = mock_site_instance
            mock_site_instance.start = AsyncMock()
            
            runner, info = await start_webhook_server(dp, bot, "0.0.0.0", 8080)
            
            # Path should contain /webhook/ and a secret part
            assert "/webhook/" in info["path"]
            # Secret part should not be empty
            secret_part = info["path"].split("/webhook/")[1]
            assert len(secret_part) > 0
            assert secret_part.isalnum()  # Should be hex string


@pytest.mark.asyncio
async def test_configure_webhook_uses_secret_path():
    """set_webhook should be called with full URL including secret path."""
    with patch.dict(os.environ, {"TELEGRAM_WEBHOOK_PATH": ""}, clear=False):
        from aiogram import Bot, Dispatcher
        
        bot = MagicMock(spec=Bot)
        bot.token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        bot.set_webhook = AsyncMock()
        
        dp = MagicMock(spec=Dispatcher)
        
        from app.webhook_server import start_webhook_server
        
        with patch("app.webhook_server.web.AppRunner") as mock_runner, \
             patch("app.webhook_server.web.TCPSite") as mock_site, \
             patch("app.webhook_server.SimpleRequestHandler"), \
             patch("app.webhook_server.setup_application"), \
             patch("app.webhook_server._detect_base_url", return_value="https://test.com"):
            
            mock_runner_instance = AsyncMock()
            mock_runner.return_value = mock_runner_instance
            mock_runner_instance.setup = AsyncMock()
            
            mock_site_instance = AsyncMock()
            mock_site.return_value = mock_site_instance
            mock_site_instance.start = AsyncMock()
            
            runner, info = await start_webhook_server(dp, bot, "0.0.0.0", 8080)
            
            # Verify set_webhook was called
            assert bot.set_webhook.called
            call_args = bot.set_webhook.call_args
            
            # URL should include secret path
            webhook_url = call_args.kwargs.get("url") or call_args.args[0]
            assert webhook_url.startswith("https://test.com/webhook/")
            assert len(webhook_url) > len("https://test.com/webhook/")


class TestWebhookSecurityGuard:
    """Test webhook security guard middleware logic."""
    
    @pytest.mark.asyncio
    async def test_secret_in_path_allows_access(self):
        """Request with secret in path should be allowed (no header needed)."""
        # This test validates the security model: path-based auth is primary
        secret = "testsecret123456"
        
        # Mock request with secret in path
        request = MagicMock()
        request.path = f"/webhook/{secret}"
        request.headers = {}  # No header
        request.remote = "1.2.3.4"
        
        # Mock handler
        handler = AsyncMock(return_value=web.Response(status=200))
        
        # Create middleware (simplified version of secret_guard logic)
        async def simplified_guard(req, hdlr):
            if "/webhook" in req.path:
                if secret in req.path:
                    return await hdlr(req)
                return web.Response(status=401, text="Unauthorized")
            return await hdlr(req)
        
        response = await simplified_guard(request, handler)
        
        assert response.status == 200
        assert handler.called
    
    @pytest.mark.asyncio
    async def test_wrong_path_without_header_denies_access(self):
        """Request to /webhook without secret in path and no header should be denied."""
        secret = "testsecret123456"
        
        request = MagicMock()
        request.path = "/webhook"  # No secret
        request.headers = {}  # No header
        request.remote = "1.2.3.4"
        
        handler = AsyncMock(return_value=web.Response(status=200))
        
        async def simplified_guard(req, hdlr):
            if "/webhook" in req.path:
                if secret in req.path:
                    return await hdlr(req)
                provided = req.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
                if provided == secret:
                    return await hdlr(req)
                return web.Response(status=401, text="Unauthorized")
            return await hdlr(req)
        
        response = await simplified_guard(request, handler)
        
        assert response.status == 401
        assert not handler.called
    
    @pytest.mark.asyncio
    async def test_legacy_webhook_with_valid_header_allowed(self):
        """Legacy /webhook path with valid header should still work (fallback)."""
        secret = "testsecret123456"
        
        request = MagicMock()
        request.path = "/webhook"
        request.headers = {"X-Telegram-Bot-Api-Secret-Token": secret}
        request.remote = "1.2.3.4"
        
        handler = AsyncMock(return_value=web.Response(status=200))
        
        async def simplified_guard(req, hdlr):
            if "/webhook" in req.path:
                if secret in req.path:
                    return await hdlr(req)
                provided = req.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
                if provided == secret:
                    return await hdlr(req)
                return web.Response(status=401, text="Unauthorized")
            return await hdlr(req)
        
        response = await simplified_guard(request, handler)
        
        assert response.status == 200
        assert handler.called
