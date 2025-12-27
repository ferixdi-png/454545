"""Test tone of voice consistency and CTA label usage."""
import pytest
from app.ui import tone


def test_cta_labels_exist():
    """Ensure all standard CTA labels are defined."""
    required_ctas = [
        "CTA_START",
        "CTA_EXAMPLE",
        "CTA_PRESETS",
        "CTA_FREE",
        "CTA_POPULAR",
        "CTA_FORMATS",
        "CTA_SEARCH",
        "CTA_REFERRAL",
        "CTA_BALANCE",
        "CTA_SUPPORT",
        "CTA_BACK",
        "CTA_HOME",
        "CTA_RETRY",
        "CTA_RECOMMENDED",
        "CTA_HOW_IT_WORKS",
        "CTA_MINI_COURSE",
    ]
    
    for cta in required_ctas:
        assert hasattr(tone, cta), f"Missing CTA label: {cta}"
        value = getattr(tone, cta)
        assert isinstance(value, str), f"{cta} must be string"
        assert len(value) > 0, f"{cta} cannot be empty"


def test_cta_labels_have_emoji():
    """Ensure all CTA labels start with emoji."""
    cta_labels = [
        tone.CTA_START,
        tone.CTA_EXAMPLE,
        tone.CTA_PRESETS,
        tone.CTA_FREE,
        tone.CTA_POPULAR,
        tone.CTA_FORMATS,
        tone.CTA_SEARCH,
        tone.CTA_REFERRAL,
        tone.CTA_BALANCE,
        tone.CTA_SUPPORT,
        tone.CTA_BACK,
        tone.CTA_HOME,
        tone.CTA_RETRY,
    ]
    
    for label in cta_labels:
        # Check that first character is likely emoji (basic check)
        assert len(label) > 1, f"CTA too short: {label}"
        # Emoji are multi-byte, so basic check is hard
        # Just ensure it starts with non-ASCII
        assert ord(label[0]) > 127, f"CTA should start with emoji: {label}"


def test_format_names_complete():
    """Ensure all common formats have display names."""
    expected_formats = [
        "text-to-image",
        "image-to-image",
        "image-to-video",
        "text-to-video",
        "text-to-audio",
        "image-upscale",
        "background-remove",
    ]
    
    for format_id in expected_formats:
        display_name = tone.format_display_name(format_id)
        assert display_name != format_id, f"Format {format_id} has no display name"
        assert "→" in display_name or "удаление" in display_name.lower() or "улучшение" in display_name.lower(), \
            f"Format name should be descriptive: {display_name}"


def test_helper_functions():
    """Test microcopy helper functions."""
    # header
    assert "**" in tone.header("Test Section")
    
    # hint
    hint_text = tone.hint("This is a hint")
    assert "💡" in hint_text
    assert "_" in hint_text
    
    # bullets
    bullets = tone.bullets(["Item 1", "Item 2", "Item 3"])
    assert "•" in bullets
    assert bullets.count("\n") == 2  # 3 items = 2 newlines
    
    # price_line
    assert "Бесплатно" in tone.price_line(0, is_free=True)
    assert "₽" in tone.price_line(10.5, is_free=False)
    
    # input_example
    example = tone.input_example("prompt", "Test example")
    assert "💡" in example
    assert "Test example" in example


def test_standard_messages_no_mentions():
    """Ensure standard messages don't mention 'kie.ai'."""
    messages = [
        tone.WELCOME_MESSAGE,
        tone.FIRST_TIME_HINT,
        tone.HOW_IT_WORKS_MESSAGE,
        tone.MINI_COURSE_MESSAGE,
    ]
    
    for msg in messages:
        assert "kie" not in msg.lower(), f"Message contains 'kie': {msg[:100]}"


def test_standard_messages_length():
    """Ensure messages follow tone guidelines (not too long)."""
    # Check bullets
    bullets = [line for line in tone.WELCOME_MESSAGE.split("\n") if line.strip().startswith("•")]
    assert len(bullets) <= 4, "Welcome message too many bullets"
    
    # Welcome should be concise (header + 1 paragraph + bullets = ok)
    # Don't count bullet block as separate paragraph
    parts = tone.WELCOME_MESSAGE.split("\n\n")
    non_bullet_parts = [p for p in parts if not any(line.strip().startswith("•") for line in p.split("\n"))]
    assert len(non_bullet_parts) <= 2, "Welcome message has too many text paragraphs (excluding bullets)"


def test_emoji_count_helper():
    """Test emoji counting helper."""
    # Basic check
    assert tone.count_emoji("🚀 Test") >= 1
    assert tone.count_emoji("No emoji here") == 0
    assert tone.count_emoji("🚀 Test 💡 Hint") >= 2


def test_message_validation_helper():
    """Test message validation helper."""
    # Good message
    good_msg = "Test message.\n\n• Bullet 1\n• Bullet 2"
    assert tone.validate_message_length(good_msg, max_paragraphs=2, max_bullets=4)
    
    # Too many paragraphs
    bad_msg = "Para 1.\n\nPara 2.\n\nPara 3."
    assert not tone.validate_message_length(bad_msg, max_paragraphs=2, max_bullets=4)
    
    # Too many bullets
    bad_bullets = "\n".join([f"• Item {i}" for i in range(6)])
    assert not tone.validate_message_length(bad_bullets, max_paragraphs=2, max_bullets=4)
