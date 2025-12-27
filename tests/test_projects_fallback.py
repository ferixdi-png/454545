"""Test projects functionality with DB fallback."""
import pytest
from app.ui.projects import (
    save_to_project,
    get_user_projects,
    get_user_history,
    add_to_history,
    delete_project,
    is_db_available,
)
from datetime import datetime


@pytest.mark.asyncio
async def test_save_to_project_no_db():
    """Test saving to project works without DB (memory fallback)."""
    user_id = 123456
    project_name = "Test Project"
    
    generation_data = {
        "model_id": "test-model",
        "format": "text-to-image",
        "prompt": "Test prompt",
        "result_url": "https://example.com/result.jpg",
        "created_at": datetime.utcnow(),
    }
    
    # Save without DB (pool=None)
    result = await save_to_project(user_id, project_name, generation_data, pool=None)
    
    assert result is True, "Save should succeed without DB"


@pytest.mark.asyncio
async def test_get_projects_no_db():
    """Test getting projects works without DB."""
    user_id = 123457
    
    # Add some test data
    await save_to_project(user_id, "Project A", {
        "model_id": "test",
        "format": "text-to-image",
        "prompt": "Test",
        "result_url": "test.jpg",
    }, pool=None)
    
    # Get projects
    projects = await get_user_projects(user_id, pool=None)
    
    assert isinstance(projects, list), "Should return list"
    # Should have at least the one we just added (memory)
    assert len(projects) >= 1, "Should have projects in memory"


@pytest.mark.asyncio
async def test_history_no_db():
    """Test history tracking without DB."""
    user_id = 123458
    
    # Add to history
    result = await add_to_history(user_id, {
        "model_id": "test",
        "format": "text-to-video",
        "prompt": "Test video",
        "result_url": "test.mp4",
    }, pool=None)
    
    assert result is True, "Should add to history"
    
    # Get history
    history = await get_user_history(user_id, pool=None)
    
    assert isinstance(history, list), "Should return list"


@pytest.mark.asyncio
async def test_delete_project_no_db():
    """Test project deletion without DB."""
    user_id = 123459
    
    # Create project
    await save_to_project(user_id, "To Delete", {
        "model_id": "test",
        "format": "text-to-image",
        "prompt": "Delete me",
        "result_url": "test.jpg",
    }, pool=None)
    
    # Get projects
    projects_before = await get_user_projects(user_id, pool=None)
    count_before = len(projects_before)
    
    # Delete first project
    if projects_before:
        project_id = projects_before[0]["project_id"]
        result = await delete_project(user_id, project_id, pool=None)
        
        assert result is True, "Delete should succeed"
        
        # Check deleted
        projects_after = await get_user_projects(user_id, pool=None)
        assert len(projects_after) < count_before, "Project count should decrease"


def test_db_availability_check():
    """Test DB availability checker."""
    assert is_db_available(None) is False, "None pool should be unavailable"
    
    # Mock pool object
    class MockPool:
        pass
    
    assert is_db_available(MockPool()) is True, "Mock pool should be available"


@pytest.mark.asyncio
async def test_project_generations_limit():
    """Test that projects don't grow unbounded in memory."""
    user_id = 123460
    project_name = "Limit Test"
    
    # Add 60 generations (should keep only last 50)
    for i in range(60):
        await save_to_project(user_id, project_name, {
            "model_id": "test",
            "format": "text-to-image",
            "prompt": f"Prompt {i}",
            "result_url": f"test_{i}.jpg",
        }, pool=None)
    
    # Get project
    projects = await get_user_projects(user_id, pool=None)
    
    if projects:
        project = projects[0]
        # Should have max 50 generations
        assert len(project["generations"]) <= 50, "Should limit generations to 50"


@pytest.mark.asyncio
async def test_history_limit():
    """Test that history doesn't grow unbounded."""
    user_id = 123461
    
    # Add 150 items (should keep only last 100)
    for i in range(150):
        await add_to_history(user_id, {
            "model_id": "test",
            "format": "text-to-image",
            "prompt": f"Prompt {i}",
            "result_url": f"test_{i}.jpg",
        }, pool=None)
    
    # Get history
    history = await get_user_history(user_id, pool=None)
    
    # Should have max 100 items
    assert len(history) <= 100, "Should limit history to 100 items"
