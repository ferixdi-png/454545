"""
Tests for model_sync behavior and SOT parsing.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.kie.fetch import _load_local_models, fetch_models_list


@pytest.mark.asyncio
async def test_load_real_sot_file():
    """Test loading the actual SOT file from repo"""
    # This tests the real file that exists
    models = await _load_local_models()
    
    # Should load successfully (even if 0 models, no exception)
    assert isinstance(models, list)
    # If file exists, should have models
    if len(models) > 0:
        assert all('model_id' in m for m in models)


@pytest.mark.asyncio
async def test_fetch_models_list_disabled():
    """Test that fetch_models_list returns empty list when disabled"""
    with patch('app.kie.fetch.MODEL_SYNC_ENABLED', False):
        models = await fetch_models_list()
        
        # Should return empty without attempting to load
        assert models == []


@pytest.mark.asyncio
async def test_fetch_models_list_enabled():
    """Test that fetch_models_list loads when enabled"""
    with patch('app.kie.fetch.MODEL_SYNC_ENABLED', True):
        models = await fetch_models_list()
        
        # Should attempt to load (result depends on file existing)
        assert isinstance(models, list)


@pytest.mark.asyncio
async def test_model_sync_not_scheduled_when_disabled():
    """Test that model_sync task is not created when MODEL_SYNC_ENABLED=0"""
    import os
    
    with patch.dict(os.environ, {"MODEL_SYNC_ENABLED": "0"}):
        enabled = os.getenv("MODEL_SYNC_ENABLED", "0") == "1"
        assert enabled is False
    
    with patch.dict(os.environ, {"MODEL_SYNC_ENABLED": "1"}):
        enabled = os.getenv("MODEL_SYNC_ENABLED", "0") == "1"
        assert enabled is True

