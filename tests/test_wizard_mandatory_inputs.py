"""Test wizard required fields and mandatory inputs."""
import pytest
from app.ui.input_spec import get_input_spec, InputType, InputField


def test_wizard_detects_required_fields():
    """Wizard should identify required fields from model schema."""
    # Mock model with required fields
    model_config = {
        "model_id": "test-model",
        "input_schema": {
            "required": ["prompt", "width"],
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Text description"
                },
                "width": {
                    "type": "integer",
                    "description": "Image width",
                    "default": 1024
                },
                "optional_field": {
                    "type": "string",
                    "description": "Optional parameter"
                }
            }
        }
    }
    
    spec = get_input_spec(model_config)
    
    required_fields = spec.get_required_fields()
    assert len(required_fields) == 2
    assert any(f.name == "prompt" for f in required_fields)
    assert any(f.name == "width" for f in required_fields)
    
    # Optional field should not be in required
    assert not any(f.name == "optional_field" for f in required_fields)


def test_field_validation():
    """InputField should validate values correctly."""
    # Text field
    text_field = InputField(
        name="prompt",
        type=InputType.TEXT,
        required=True,
        description="Your prompt"
    )
    
    is_valid, error = text_field.validate("Valid text")
    assert is_valid
    assert error is None
    
    is_valid, error = text_field.validate("")
    assert not is_valid
    assert "обязателен" in error.lower()
    
    # Number field
    num_field = InputField(
        name="width",
        type=InputType.NUMBER,
        required=True,
        description="Width",
        min_value=256,
        max_value=2048
    )
    
    is_valid, error = num_field.validate("1024")
    assert is_valid
    
    is_valid, error = num_field.validate("100")  # Too small
    assert not is_valid
    
    is_valid, error = num_field.validate("3000")  # Too large
    assert not is_valid


def test_no_empty_required_fields():
    """Wizard should not allow empty required fields."""
    field = InputField(
        name="prompt",
        type=InputType.TEXT,
        required=True,
        description="Required prompt"
    )
    
    is_valid, error = field.validate(None)
    assert not is_valid
    
    is_valid, error = field.validate("")
    assert not is_valid


def test_file_upload_field_types():
    """Wizard should support file upload field types."""
    types_to_test = [
        InputType.IMAGE_FILE,
        InputType.VIDEO_FILE,
        InputType.AUDIO_FILE,
    ]
    
    for file_type in types_to_test:
        field = InputField(
            name="media",
            type=file_type,
            required=True,
            description="Upload file"
        )
        
        assert field.type == file_type
        assert field.required


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
