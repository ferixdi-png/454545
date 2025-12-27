"""Test examples.json and wizard examples."""
import pytest
import json
from pathlib import Path


@pytest.fixture
def examples_data():
    """Load examples.json."""
    examples_file = Path(__file__).parent.parent / "app" / "ui" / "content" / "examples.json"
    
    if not examples_file.exists():
        pytest.skip("examples.json not found")
    
    return json.loads(examples_file.read_text(encoding="utf-8"))


def test_examples_schema(examples_data):
    """Validate examples.json structure."""
    assert "formats" in examples_data, "Missing 'formats' key"
    assert "input_types" in examples_data, "Missing 'input_types' key"
    assert "wizard_hints" in examples_data, "Missing 'wizard_hints' key"


def test_format_examples_exist(examples_data):
    """Ensure main formats have examples."""
    required_formats = [
        "text-to-image",
        "image-to-image",
        "text-to-video",
        "text-to-audio",
    ]
    
    formats = examples_data["formats"]
    
    for format_id in required_formats:
        assert format_id in formats, f"Missing examples for format: {format_id}"
        
        format_examples = formats[format_id]
        assert "general" in format_examples, f"Format {format_id} missing 'general' examples"
        assert isinstance(format_examples["general"], list)
        assert len(format_examples["general"]) >= 2, f"Format {format_id} needs at least 2 general examples"


def test_input_type_examples(examples_data):
    """Ensure input types have good practices."""
    required_input_types = [
        "prompt",
        "negative_prompt",
        "style",
        "image",
    ]
    
    input_types = examples_data["input_types"]
    
    for input_type in required_input_types:
        assert input_type in input_types, f"Missing examples for input type: {input_type}"
        
        input_data = input_types[input_type]
        assert "good_practices" in input_data, f"Input type {input_type} missing good_practices"
        assert "examples" in input_data, f"Input type {input_type} missing examples"
        
        assert len(input_data["good_practices"]) >= 2, f"Input type {input_type} needs more good_practices"
        assert len(input_data["examples"]) >= 1, f"Input type {input_type} needs at least 1 example"


def test_wizard_hints_present(examples_data):
    """Ensure wizard hints are defined."""
    hints = examples_data["wizard_hints"]
    
    required_hints = [
        "prompt_placeholder",
        "image_placeholder",
        "style_placeholder",
    ]
    
    for hint_key in required_hints:
        assert hint_key in hints, f"Missing wizard hint: {hint_key}"
        assert len(hints[hint_key]) > 10, f"Wizard hint {hint_key} too short"


def test_examples_no_placeholders(examples_data):
    """Ensure examples are not placeholders."""
    formats = examples_data["formats"]
    
    for format_id, format_data in formats.items():
        for category, examples in format_data.items():
            for example in examples:
                assert not example.startswith("TODO"), f"Placeholder example in {format_id}/{category}"
                assert len(example) > 15, f"Example too short in {format_id}/{category}: {example}"


def test_good_practices_useful(examples_data):
    """Ensure good practices are actionable."""
    input_types = examples_data["input_types"]
    
    for input_type, data in input_types.items():
        for practice in data["good_practices"]:
            # Should be actionable (not just descriptions)
            assert len(practice) > 10, f"Practice too short in {input_type}"
            # Should not be just "TODO"
            assert not practice.startswith("TODO")
