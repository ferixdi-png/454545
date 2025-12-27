"""Test backward-compatible payload alias in generate_with_payment."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.payments.integration import generate_with_payment


@pytest.mark.asyncio
async def test_payload_alias_backward_compatibility():
    """Test that generate_with_payment accepts both user_inputs and payload parameters."""
    
    # Mock dependencies
    mock_cm = MagicMock()
    mock_cm.can_afford = AsyncMock(return_value=True)
    mock_cm.charge_for_generation = AsyncMock(return_value={"success": True})
    mock_cm.db_service.get_connection = AsyncMock()
    
    with patch("app.payments.integration.get_charge_manager", return_value=mock_cm), \
         patch("app.payments.integration.KIEAPIService") as mock_kie, \
         patch("app.payments.integration.get_model_config") as mock_config:
        
        mock_config.return_value = {
            "id": "test-model",
            "display_name": "Test Model",
            "pricing": {"rub_per_gen": 10.0}
        }
        
        mock_kie_instance = AsyncMock()
        mock_kie_instance.generate = AsyncMock(return_value={
            "status": "completed",
            "media_url": "https://example.com/result.png"
        })
        mock_kie.return_value = mock_kie_instance
        
        # Test NEW signature: user_inputs=
        result1 = await generate_with_payment(
            model_id="test-model",
            user_inputs={"prompt": "test prompt"},
            user_id=12345,
            amount=10.0
        )
        
        assert result1["status"] == "completed"
        
        # Test OLD signature: payload= (backward compatibility)
        result2 = await generate_with_payment(
            model_id="test-model",
            payload={"prompt": "test prompt old"},
            user_id=67890,
            amount=10.0
        )
        
        assert result2["status"] == "completed"


@pytest.mark.asyncio
async def test_payload_priority_user_inputs_wins():
    """If both user_inputs and payload provided, user_inputs takes priority."""
    
    mock_cm = MagicMock()
    mock_cm.can_afford = AsyncMock(return_value=True)
    mock_cm.charge_for_generation = AsyncMock(return_value={"success": True})
    mock_cm.db_service.get_connection = AsyncMock()
    
    with patch("app.payments.integration.get_charge_manager", return_value=mock_cm), \
         patch("app.payments.integration.KIEAPIService") as mock_kie, \
         patch("app.payments.integration.get_model_config") as mock_config:
        
        mock_config.return_value = {
            "id": "test-model",
            "pricing": {"rub_per_gen": 5.0}
        }
        
        mock_kie_instance = AsyncMock()
        mock_kie_instance.generate = AsyncMock(return_value={"status": "completed"})
        mock_kie.return_value = mock_kie_instance
        
        # Both provided - user_inputs should win
        result = await generate_with_payment(
            model_id="test-model",
            user_inputs={"prompt": "CORRECT"},
            payload={"prompt": "WRONG"},
            user_id=111,
            amount=5.0
        )
        
        # Verify KIE was called with user_inputs, not payload
        called_inputs = mock_kie_instance.generate.call_args[1]["inputs"]
        assert called_inputs["prompt"] == "CORRECT"
