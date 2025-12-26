"""Request-scoped tracing helpers (request_id/user_id/model_id) for structured logs."""

from __future__ import annotations

import contextvars
import uuid
from dataclasses import dataclass
from typing import Optional, Tuple

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_user_id: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="-")
_model_id: contextvars.ContextVar[str] = contextvars.ContextVar("model_id", default="-")

def get_request_id() -> str:
    return _request_id.get()

def get_user_id() -> str:
    return _user_id.get()

def get_model_id() -> str:
    return _model_id.get()

def new_request_id() -> str:
    # short, readable id for logs
    return uuid.uuid4().hex[:12]

@dataclass
class TraceTokens:
    request_id_token: contextvars.Token
    user_id_token: contextvars.Token
    model_id_token: contextvars.Token

class TraceContext:
    """Context manager to set request-scoped trace values."""
    def __init__(self, user_id: Optional[int] = None, model_id: Optional[str] = None, request_id: Optional[str] = None):
        self._rid = request_id or new_request_id()
        self._uid = str(user_id) if user_id is not None else "-"
        self._mid = str(model_id) if model_id is not None else "-"
        self._tokens: Optional[TraceTokens] = None

    @property
    def request_id(self) -> str:
        return self._rid

    def __enter__(self) -> "TraceContext":
        self._tokens = TraceTokens(
            request_id_token=_request_id.set(self._rid),
            user_id_token=_user_id.set(self._uid),
            model_id_token=_model_id.set(self._mid),
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self._tokens:
            return
        _request_id.reset(self._tokens.request_id_token)
        _user_id.reset(self._tokens.user_id_token)
        _model_id.reset(self._tokens.model_id_token)

class TraceLogFilter:
    """Inject trace fields into log records to avoid KeyError in format."""
    def __init__(self, instance_id: str = "-"):
        self.instance_id = instance_id

    def filter(self, record) -> bool:
        # Always present fields used by formatters
        record.request_id = getattr(record, "request_id", None) or get_request_id()
        record.user_id = getattr(record, "user_id", None) or get_user_id()
        record.model_id = getattr(record, "model_id", None) or get_model_id()
        record.instance_id = getattr(record, "instance_id", None) or self.instance_id
        return True
