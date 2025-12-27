"""Test post-result retention panel."""
import pytest
from app.ui.retention_panel import (
    build_retention_panel,
    build_improvement_goals_keyboard,
    build_project_list_keyboard,
    get_variants_prompt,
    apply_improvement_goal,
    format_result_type,
)


@pytest.mark.asyncio
async def test_retention_panel_has_all_actions():
    """Ensure retention panel has all key actions."""
    keyboard = build_retention_panel("image")
    
    assert keyboard is not None
    
    # Flatten all callback_data
    all_callbacks = [
        btn.callback_data
        for row in keyboard.inline_keyboard
        for btn in row
    ]
    
    # Should have variants, improve, save, retry, home
    assert any("variants" in cb for cb in all_callbacks), "Missing variants action"
    assert any("improve" in cb for cb in all_callbacks), "Missing improve action"
    assert any("save" in cb for cb in all_callbacks), "Missing save action"
    assert any("retry" in cb for cb in all_callbacks), "Missing retry action"
    assert any("main_menu" in cb for cb in all_callbacks), "Missing home action"


@pytest.mark.asyncio
async def test_variants_prompt_generates_different():
    """Test that variant prompts are different from original."""
    original = "Красивая обложка для поста"
    
    variant1 = await get_variants_prompt(original, 1, "text-to-image")
    variant2 = await get_variants_prompt(original, 2, "text-to-image")
    variant3 = await get_variants_prompt(original, 3, "text-to-image")
    
    # Should contain original
    assert original in variant1
    assert original in variant2
    assert original in variant3
    
    # Should be different from each other
    assert variant1 != variant2
    assert variant2 != variant3


def test_improvement_goals_keyboard():
    """Ensure improvement goals keyboard has options."""
    keyboard = build_improvement_goals_keyboard()
    
    assert keyboard is not None
    assert len(keyboard.inline_keyboard) >= 3, "Should have at least 3 goal options"
    
    # Should have Back button
    has_back = any(
        any(btn.callback_data == "cancel_improve" for btn in row)
        for row in keyboard.inline_keyboard
    )
    assert has_back, "Missing Back button"


@pytest.mark.asyncio
async def test_improvement_goal_modifies_prompt():
    """Test that improvement goals modify prompt."""
    original = "Баннер для рекламы"
    
    ctr_prompt = await apply_improvement_goal(original, "ctr", "text-to-image")
    premium_prompt = await apply_improvement_goal(original, "premium", "text-to-image")
    
    # Should contain original
    assert original in ctr_prompt
    assert original in premium_prompt
    
    # Should have added guidance
    assert len(ctr_prompt) > len(original)
    assert len(premium_prompt) > len(original)
    
    # Should be different
    assert ctr_prompt != premium_prompt


def test_project_list_keyboard():
    """Test project list keyboard generation."""
    mock_projects = [
        {"project_id": 1, "name": "Проект 1", "generation_count": 5},
        {"project_id": 2, "name": "Проект 2", "generation_count": 3},
    ]
    
    keyboard = build_project_list_keyboard(mock_projects)
    
    assert keyboard is not None
    
    # Should have project buttons + new project + back
    assert len(keyboard.inline_keyboard) >= 4
    
    # Should have "create new" option
    has_new = any(
        any(btn.callback_data == "create_new_project" for btn in row)
        for row in keyboard.inline_keyboard
    )
    assert has_new, "Missing create new project option"


@pytest.mark.asyncio
async def test_format_result_type():
    """Test result type formatting."""
    assert await format_result_type("text-to-image") == "изображение"
    assert await format_result_type("text-to-video") == "видео"
    assert await format_result_type("text-to-audio") == "аудио"
    assert await format_result_type("image-upscale") == "улучшенное изображение"


def test_retention_panel_no_variants_option():
    """Test retention panel can hide variants option."""
    keyboard = build_retention_panel("image", show_variants=False)
    
    all_callbacks = [
        btn.callback_data
        for row in keyboard.inline_keyboard
        for btn in row
    ]
    
    # Should NOT have variants
    assert not any("variants" in cb for cb in all_callbacks), "Variants should be hidden"
    
    # Should still have other actions
    assert any("improve" in cb for cb in all_callbacks), "Should have improve"
    assert any("retry" in cb for cb in all_callbacks), "Should have retry"
