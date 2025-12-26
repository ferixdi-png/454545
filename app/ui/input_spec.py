"""Input specification and validation for wizard system."""
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class InputType(str, Enum):
    """Input field types."""
    TEXT = "text"
    IMAGE_URL = "image_url"
    IMAGE_FILE = "image_file"
    VIDEO_URL = "video_url"
    VIDEO_FILE = "video_file"
    AUDIO_URL = "audio_url"
    AUDIO_FILE = "audio_file"
    ENUM = "enum"
    NUMBER = "number"
    BOOLEAN = "boolean"


@dataclass
class InputField:
    """Input field specification."""
    name: str
    type: InputType
    required: bool
    description: str
    example: Optional[str] = None
    enum_values: Optional[List[str]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    default: Optional[Any] = None
    
    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """
        Validate input value.
        
        Returns:
            (is_valid, error_message)
        """
        if value is None or value == "":
            if self.required:
                return False, f"{self.name} обязателен"
            return True, None
        
        if self.type == InputType.TEXT:
            if not isinstance(value, str):
                return False, f"{self.name} должен быть текстом"
            return True, None
        
        if self.type == InputType.NUMBER:
            try:
                num = float(value)
                if self.min_value is not None and num < self.min_value:
                    return False, f"{self.name} должен быть >= {self.min_value}"
                if self.max_value is not None and num > self.max_value:
                    return False, f"{self.name} должен быть <= {self.max_value}"
                return True, None
            except (ValueError, TypeError):
                return False, f"{self.name} должен быть числом"
        
        if self.type == InputType.ENUM:
            if self.enum_values and value not in self.enum_values:
                return False, f"{self.name} должен быть одним из: {', '.join(self.enum_values)}"
            return True, None
        
        if self.type in (InputType.IMAGE_URL, InputType.VIDEO_URL, InputType.AUDIO_URL):
            if not isinstance(value, str) or not (value.startswith('http://') or value.startswith('https://')):
                return False, f"{self.name} должен быть URL"
            return True, None
        
        return True, None


@dataclass
class InputSpec:
    """Complete input specification for a model."""
    model_id: str
    fields: List[InputField]
    
    def get_required_fields(self) -> List[InputField]:
        """Get list of required fields."""
        return [f for f in self.fields if f.required]
    
    def get_field(self, name: str) -> Optional[InputField]:
        """Get field by name."""
        for field in self.fields:
            if field.name == name:
                return field
        return None
    
    def validate_payload(self, payload: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate complete payload.
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        for field in self.fields:
            value = payload.get(field.name)
            is_valid, error = field.validate(value)
            if not is_valid:
                errors.append(error)
        
        return len(errors) == 0, errors


def build_input_spec_from_schema(model_id: str, schema: Dict[str, Any]) -> InputSpec:
    """
    Build InputSpec from JSON schema.
    
    Args:
        model_id: Model identifier
        schema: input_schema from KIE_SOURCE_OF_TRUTH
    
    Returns:
        InputSpec object
    """
    fields = []
    
    if not schema or "properties" not in schema:
        logger.warning(f"No schema properties for {model_id}, using empty spec")
        return InputSpec(model_id=model_id, fields=[])
    
    required_fields = schema.get("required", [])
    properties = schema.get("properties", {})
    
    for field_name, field_schema in properties.items():
        field_type_str = field_schema.get("type", "string")
        field_format = field_schema.get("format")
        
        # Map JSON schema types to InputType
        if field_format == "uri":
            # Determine if it's image/video/audio from field name
            if "image" in field_name.lower():
                input_type = InputType.IMAGE_URL
            elif "video" in field_name.lower():
                input_type = InputType.VIDEO_URL
            elif "audio" in field_name.lower():
                input_type = InputType.AUDIO_URL
            else:
                input_type = InputType.TEXT
        elif field_type_str == "integer" or field_type_str == "number":
            input_type = InputType.NUMBER
        elif "enum" in field_schema:
            input_type = InputType.ENUM
        elif field_type_str == "boolean":
            input_type = InputType.BOOLEAN
        else:
            input_type = InputType.TEXT
        
        field = InputField(
            name=field_name,
            type=input_type,
            required=field_name in required_fields,
            description=field_schema.get("description", f"Поле {field_name}"),
            example=None,  # TODO: extract from examples if available
            enum_values=field_schema.get("enum"),
            min_value=field_schema.get("minimum"),
            max_value=field_schema.get("maximum"),
            default=field_schema.get("default"),
        )
        
        fields.append(field)
    
    return InputSpec(model_id=model_id, fields=fields)


def build_input_spec_heuristic(model_id: str, category: str, output_type: str) -> InputSpec:
    """
    Build InputSpec using heuristics when schema is not available.
    
    Args:
        model_id: Model identifier
        category: Model category (e.g., "text-to-image", "image-to-video")
        output_type: Output type (e.g., "image", "video")
    
    Returns:
        InputSpec object
    """
    fields = []
    
    # Common patterns
    if "text-to-" in category or category in ["text-to-image", "text-to-video", "text-to-audio"]:
        fields.append(InputField(
            name="prompt",
            type=InputType.TEXT,
            required=True,
            description="Текстовое описание желаемого результата",
            example="Красивый закат над океаном",
        ))
    
    if "image-to-" in category or category in ["image-to-video", "image-to-image"]:
        fields.append(InputField(
            name="image_url",
            type=InputType.IMAGE_URL,
            required=True,
            description="URL изображения для обработки",
            example="https://example.com/image.jpg",
        ))
        # Optional prompt for image-based generation
        if "image-to-video" in category or "image-to-image" in category:
            fields.append(InputField(
                name="prompt",
                type=InputType.TEXT,
                required=False,
                description="Дополнительное описание (необязательно)",
            ))
    
    if "video" in category or output_type == "video":
        fields.append(InputField(
            name="duration",
            type=InputType.NUMBER,
            required=False,
            description="Длительность видео (секунды)",
            min_value=1,
            max_value=30,
            default=10,
        ))
    
    if "audio-to-" in category or "voice" in category.lower():
        fields.append(InputField(
            name="audio_url",
            type=InputType.AUDIO_URL,
            required=True,
            description="URL аудио для обработки",
        ))
    
    return InputSpec(model_id=model_id, fields=fields)


def get_input_spec(model_config: Dict[str, Any]) -> InputSpec:
    """
    Get InputSpec for a model.
    
    Priority:
    1. Build from input_schema if available
    2. Use heuristics based on category/output_type
    
    Args:
        model_config: Model configuration dict from KIE_SOURCE_OF_TRUTH
    
    Returns:
        InputSpec object
    """
    model_id = model_config.get("model_id", "unknown")
    
    # Try schema-based first
    if "input_schema" in model_config:
        spec = build_input_spec_from_schema(model_id, model_config["input_schema"])
        if spec.fields:
            return spec
    
    # Fallback to heuristic
    category = model_config.get("category", "")
    output_type = model_config.get("output_type", "")
    
    return build_input_spec_heuristic(model_id, category, output_type)
