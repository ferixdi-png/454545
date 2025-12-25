# MODEL CONTRACT SPECIFICATION

## Overview

This document defines the strict contract for Kie.ai models. The contract ensures that **it is impossible to reach createTask with invalid data**.

## Contract Guarantees

### 1. Single Source of Truth

**File:** `models/kie_models_source_of_truth.json`

- **MUST** be the only source of model definitions
- **MUST** contain complete `input_schema` for each model
- **MUST** define `required` and `optional` fields
- **MUST** specify field `type` (string/int/bool/enum/url/file)

### 2. Unified Schema

**Module:** `app/kie/builder.py`

- **MUST** use `source_of_truth` for all model schemas
- **MUST** build payload only from schema
- **MUST NOT** add fields not in schema
- **MUST** validate inputs before building payload

### 3. Strict Input Validation

**Module:** `app/kie/validator.py`

**Rules:**
- Model requires file → **MUST NOT** accept text
- Model requires file → **MUST NOT** accept URL
- Model requires URL → **MUST NOT** accept file upload
- Model requires text → **MUST NOT** accept file
- Model requires text → **MUST NOT** accept URL
- Required fields → **MUST** be present
- Field types → **MUST** match schema

**Validation Points:**
1. `validate_model_inputs()` - Before payload building
2. `validate_payload_before_create_task()` - Before API call

### 4. Unified Payload Builder

**Module:** `app/kie/builder.py`

**Function:** `build_payload(model_id, user_inputs)`

**Contract:**
- Raises `ModelContractError` if inputs invalid
- Raises `ValueError` if model not found
- Returns valid payload or raises exception
- **Impossible** to return invalid payload

### 5. Unified Result Parser

**Module:** `app/kie/parser.py`

**Function:** `parse_record_info(record_info)`

**Contract:**
- Handles all states: `waiting`, `success`, `fail`
- Extracts `resultUrls` and `resultObject`
- Provides human-readable error messages
- **MUST** handle all response formats

## Implementation

### Validation Flow

```
User Inputs
    ↓
validate_model_inputs()  ← STRICT: file vs text vs URL
    ↓
build_payload()          ← Uses schema only
    ↓
validate_payload_before_create_task()  ← Final check
    ↓
createTask API           ← Payload guaranteed valid
```

### Error Handling

**ModelContractError:**
- Raised when input type mismatch (file vs text vs URL)
- Raised when required fields missing
- Raised when field types don't match schema
- **Prevents** reaching createTask with invalid data

**ValueError:**
- Raised when model not found
- Raised when schema missing
- **Prevents** building payload for unknown models

## Examples

### Example 1: File-Requiring Model

**Schema:**
```json
{
  "model_id": "image_processor",
  "input_schema": {
    "required": ["image_file"],
    "properties": {
      "image_file": {"type": "file"}
    }
  }
}
```

**Valid Input:**
```python
user_inputs = {"file": "file_id_123"}
# ✅ Passes validation
```

**Invalid Input:**
```python
user_inputs = {"text": "some text"}
# ❌ Raises ModelContractError: "Model requires file input, but text was provided"
```

### Example 2: URL-Requiring Model

**Schema:**
```json
{
  "model_id": "url_processor",
  "input_schema": {
    "required": ["source_url"],
    "properties": {
      "source_url": {"type": "url"}
    }
  }
}
```

**Valid Input:**
```python
user_inputs = {"url": "https://example.com/data"}
# ✅ Passes validation
```

**Invalid Input:**
```python
user_inputs = {"file": "file_id_123"}
# ❌ Raises ModelContractError: "Model requires URL input, but file was provided"
```

### Example 3: Text-Requiring Model

**Schema:**
```json
{
  "model_id": "text_processor",
  "input_schema": {
    "required": ["prompt"],
    "properties": {
      "prompt": {"type": "text"}
    }
  }
}
```

**Valid Input:**
```python
user_inputs = {"text": "Hello world"}
# ✅ Passes validation
```

**Invalid Input:**
```python
user_inputs = {"file": "file_id_123"}
# ❌ Raises ModelContractError: "Model requires text input, but file was provided"
```

## Success Criteria

✅ **Impossible to reach createTask with invalid data**

- File-requiring models reject text/URL
- URL-requiring models reject file uploads
- Text-requiring models reject file/URL
- Required fields must be present
- Field types must match schema
- All validation happens before API call

## Files

- `app/kie/validator.py` - Strict validation logic
- `app/kie/builder.py` - Payload builder with validation
- `app/kie/parser.py` - Result parser (unchanged)
- `app/kie/generator.py` - Generator with contract enforcement
- `models/kie_models_source_of_truth.json` - Single source of truth

