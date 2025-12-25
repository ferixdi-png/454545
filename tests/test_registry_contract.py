import json

import pytest

from app.kie.builder import build_payload, load_source_of_truth
from app.kie.generator import KieGenerator


def _sample_value(field_spec: dict) -> object:
    field_type = field_spec.get("type", "string")
    if "enum" in field_spec and field_spec["enum"]:
        return field_spec["enum"][0]
    if field_type in {"integer", "int"}:
        return int(field_spec.get("minimum", 1))
    if field_type in {"number", "float"}:
        return float(field_spec.get("minimum", 1))
    if field_type in {"boolean", "bool"}:
        return True
    if field_type in {"url", "link", "source_url"}:
        return "https://example.com/input"
    if field_type in {"file", "file_id", "file_url"}:
        return "https://example.com/file.png"
    return "test"


def _build_user_inputs(model_schema: dict) -> dict:
    input_schema = model_schema.get("input_schema", {})
    required_fields = input_schema.get("required", [])
    properties = input_schema.get("properties", {})
    user_inputs = {}
    for field_name in required_fields:
        field_spec = properties.get(field_name, {})
        user_inputs[field_name] = _sample_value(field_spec)
    return user_inputs


def test_registry_payloads_build():
    source = load_source_of_truth()
    models = source.get("models", [])
    pricing = source.get("pricing", {})
    assert models, "source_of_truth must contain models"

    for model in models:
        model_id = model.get("model_id")
        if not model_id:
            continue
        # Skip models without pricing (technical/hidden models)
        if model_id not in pricing:
            continue
        user_inputs = _build_user_inputs(model)
        payload = build_payload(model_id, user_inputs, source)
        assert payload.get("model") == model_id


@pytest.mark.asyncio
async def test_stub_success_per_category():
    source = load_source_of_truth()
    models = source.get("models", [])
    assert models, "source_of_truth must contain models"

    generator = KieGenerator()
    generator.source_of_truth = source

    for model in models:
        model_id = model.get("model_id")
        if not model_id:
            continue
        user_inputs = _build_user_inputs(model)
        result = await generator.generate(model_id, user_inputs)
        assert "success" in result
        if result["success"]:
            assert "result_urls" in result
