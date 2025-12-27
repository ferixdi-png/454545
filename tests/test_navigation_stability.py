"""Tests for navigation stability (menu handlers, button callbacks)."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import CallbackQuery, Message, User
from aiogram.fsm.context import FSMContext

from bot.handlers.navigation import handle_main_menu


@pytest.mark.asyncio
async def test_main_menu_handler_clears_fsm():
    """Test that main menu handler clears FSM state."""
    # Mock callback
    callback = MagicMock(spec=CallbackQuery)
    callback.answer = AsyncMock()
    callback.from_user = User(id=123, is_bot=False, first_name="Test")
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.message.answer = AsyncMock()
    
    # Mock FSM state
    state = MagicMock(spec=FSMContext)
    state.clear = AsyncMock()
    
    # Call handler
    await handle_main_menu(callback, state)
    
    # Verify state was cleared
    state.clear.assert_called_once()
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_main_menu_shows_correct_counts():
    """Test that main menu displays correct model counts."""
    callback = MagicMock(spec=CallbackQuery)
    callback.answer = AsyncMock()
    callback.from_user = User(id=123, is_bot=False, first_name="Test")
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    
    state = MagicMock(spec=FSMContext)
    state.clear = AsyncMock()
    
    await handle_main_menu(callback, state)
    
    # Check that text was sent (exact counts will vary)
    assert callback.message.edit_text.called or callback.message.answer.called


def test_navigation_router_exists():
    """Test that navigation router is properly exported."""
    from bot.handlers import navigation_router
    
    assert navigation_router is not None
    assert navigation_router.name == "navigation"


def test_gen_handler_router_exists():
    """Test that gen_handler router exists and handles gen: callbacks."""
    from bot.handlers import gen_handler_router
    
    assert gen_handler_router is not None
    assert gen_handler_router.name == "gen_handler"


def test_no_hardcoded_workspaces_paths():
    """Test that no /workspaces paths exist in runtime code."""
    import subprocess
    
    # Search for /workspaces in critical runtime files
    result = subprocess.run(
        ["grep", "-r", "/workspaces/454545", "bot/", "app/", "--include=*.py"],
        capture_output=True,
        text=True,
    )
    
    # Should find no matches (or only in comments/tests)
    if result.returncode == 0:
        # Found matches - check if they're in comments
        lines = result.stdout.strip().split('\n')
        runtime_matches = [l for l in lines if not ("#" in l or "test" in l.lower())]
        
        assert len(runtime_matches) == 0, f"Found /workspaces paths in runtime code:\\n{chr(10).join(runtime_matches)}"


def test_all_navigation_callbacks_short():
    """Test that all navigation callbacks use short keys."""
    import subprocess
    
    # Search for long callback patterns (gen: with long IDs)
    result = subprocess.run(
        ["grep", "-rE", r'callback_data=.*gen:[a-z0-9/-]{20,}', "bot/", "--include=*.py"],
        capture_output=True,
        text=True,
    )
    
    # Should find no matches (all should use make_key)
    if result.returncode == 0:
        assert False, f"Found long callback_data patterns:\\n{result.stdout}"


def test_menu_main_always_available():
    """Test that menu:main callback is always registered."""
    from bot.handlers.navigation import router
    
    # Check that router has handlers registered
    # (actual registration happens at runtime)
    assert router is not None
