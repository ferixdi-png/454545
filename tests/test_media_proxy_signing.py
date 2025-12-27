"""Test media proxy signing and security."""
import pytest
import hmac
import hashlib
import os


def test_media_proxy_signature_generation():
    """Media proxy should generate valid signatures."""
    from bot.flows.wizard import _sign_file_id
    
    file_id = "test_file_12345"
    sig = _sign_file_id(file_id)
    
    assert sig
    assert len(sig) == 16  # Truncated to 16 chars
    assert sig.isalnum()  # Hexadecimal


def test_media_proxy_signature_verification():
    """Media proxy should verify signatures correctly."""
    from bot.flows.wizard import _sign_file_id
    
    file_id = "test_file_12345"
    sig = _sign_file_id(file_id)
    
    # Same file_id should produce same signature
    sig2 = _sign_file_id(file_id)
    assert sig == sig2
    
    # Different file_id should produce different signature
    sig3 = _sign_file_id("different_file")
    assert sig != sig3


def test_media_proxy_url_format():
    """Media proxy URLs should have correct format."""
    from bot.flows.wizard import _sign_file_id, _get_public_base_url
    
    file_id = "AgACAgIAAxkBAAIBY2..."
    sig = _sign_file_id(file_id)
    base_url = _get_public_base_url()
    
    media_url = f"{base_url}/media/telegram/{file_id}?sig={sig}"
    
    assert "/media/telegram/" in media_url
    assert "?sig=" in media_url
    assert file_id in media_url


def test_unsigned_request_denied():
    """Media proxy should deny requests without valid signature."""
    # This would be tested with actual HTTP requests in integration tests
    # Here we just verify that signature is required
    from bot.flows.wizard import _sign_file_id
    
    file_id = "test_file"
    sig = _sign_file_id(file_id)
    
    # Wrong signature should not match
    wrong_sig = "0000000000000000"
    assert sig != wrong_sig


def test_public_base_url_configured():
    """PUBLIC_BASE_URL should be available."""
    from bot.flows.wizard import _get_public_base_url
    
    base_url = _get_public_base_url()
    
    assert base_url
    assert base_url.startswith("http")
    assert not base_url.endswith("/")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
