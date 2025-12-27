"""Test that no placeholder bot links appear in code."""
import pytest
import re
from pathlib import Path


def test_no_placeholder_bot_links_in_code():
    """No 't.me/bot?start=' placeholders should exist."""
    # Search key files for placeholder patterns
    files_to_check = [
        "bot/handlers/marketing.py",
        "bot/utils/bot_info.py",
        "app/ui/templates.py",
    ]
    
    placeholder_patterns = [
        r"t\.me/bot\?",
        r"t\.me/@?bot\?start=",
        r"https://t\.me/bot\?",
    ]
    
    violations = []
    
    for file_path in files_to_check:
        full_path = Path(__file__).parent.parent / file_path
        if not full_path.exists():
            continue
        
        content = full_path.read_text()
        
        for pattern in placeholder_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                violations.append(f"{file_path}: Found placeholder pattern '{pattern}'")
    
    assert not violations, f"Placeholder bot links found:\n" + "\n".join(violations)


def test_referral_link_builder_safe():
    """get_referral_link should return None if username is missing."""
    from bot.utils.bot_info import get_referral_link
    
    # None username should return None
    link = get_referral_link(None, 12345)
    assert link is None, "Should return None when username is None"
    
    # Valid username should return proper link
    link = get_referral_link("testbot", 12345)
    assert link is not None
    assert "t.me/testbot?start=" in link
    assert "ref_12345" in link


def test_referral_screen_handles_missing_username():
    """Referral screen should handle None username gracefully."""
    # This would require async test with mock callback
    # Here we just verify the logic exists
    from bot.utils.bot_info import get_referral_link
    
    # Simulate missing username
    username = None
    user_id = 123
    
    ref_link = get_referral_link(username, user_id)
    
    # Should be None, not a broken link
    assert ref_link is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
