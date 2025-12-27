"""Test onboarding flow paths."""
import pytest
from app.ui.onboarding import (
    get_onboarding_goals,
    build_onboarding_screen,
    build_goal_presets_screen,
    is_first_run,
    mark_onboarding_complete,
)


def test_onboarding_goals_defined():
    """Ensure all onboarding goals are defined."""
    goals = get_onboarding_goals()
    
    assert len(goals) >= 5, "Should have at least 5 goal options"
    
    # Check structure
    for goal_id, button_text, description in goals:
        assert isinstance(goal_id, str)
        assert isinstance(button_text, str)
        assert isinstance(description, str)
        assert len(button_text) > 0
        assert len(goal_id) > 0


def test_onboarding_screen_has_all_goals():
    """Ensure onboarding screen shows all goals."""
    text, keyboard = build_onboarding_screen()
    
    assert "Что ты хочешь сделать" in text
    assert keyboard is not None
    
    # Should have goal buttons + skip
    goals = get_onboarding_goals()
    assert len(keyboard.inline_keyboard) >= len(goals), "Missing goal buttons"


def test_goal_callbacks_valid():
    """Ensure goal button callbacks are properly formatted."""
    text, keyboard = build_onboarding_screen()
    
    for row in keyboard.inline_keyboard:
        for button in row:
            if button.callback_data.startswith("onboarding_goal:"):
                goal_id = button.callback_data.split(":")[1]
                assert len(goal_id) > 0, "Goal ID cannot be empty"


def test_presets_screen_for_each_goal():
    """Ensure preset screen can be built for each goal."""
    goals = get_onboarding_goals()
    
    # Mock presets
    mock_presets = [
        {"id": "test1", "title": "Test 1", "category": "ads"},
        {"id": "test2", "title": "Test 2", "category": "reels"},
        {"id": "test3", "title": "Test 3", "category": "branding"},
    ]
    
    for goal_id, _, _ in goals:
        text, keyboard = build_goal_presets_screen(goal_id, mock_presets)
        
        assert keyboard is not None
        assert len(text) > 0
        # Should have Back button
        has_back = any(
            any(btn.callback_data == "restart_onboarding" for btn in row)
            for row in keyboard.inline_keyboard
        )
        assert has_back, f"Goal {goal_id} screen missing Back button"


def test_first_run_detection():
    """Test first run detection and completion."""
    test_user_id = 999999
    
    # Initially should be first run (memory)
    assert is_first_run(test_user_id) is True
    
    # Mark complete
    mark_onboarding_complete(test_user_id)
    
    # Should no longer be first run
    assert is_first_run(test_user_id) is False


def test_skip_onboarding_available():
    """Ensure skip option is always available."""
    text, keyboard = build_onboarding_screen()
    
    has_skip = any(
        any(btn.callback_data == "skip_onboarding" for btn in row)
        for row in keyboard.inline_keyboard
    )
    
    assert has_skip, "Onboarding must have skip option"
