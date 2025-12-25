"""
Runtime state shared across handlers for diagnostics.
"""
from dataclasses import dataclass
import os
import socket
import uuid


@dataclass
class RuntimeState:
    instance_id: str
    lock_acquired: bool | None = None
    storage_mode: str = "auto"
    bot_mode: str = "polling"
    last_start_time: str | None = None


def _build_instance_id() -> str:
    host = socket.gethostname()
    suffix = uuid.uuid4().hex[:8]
    return f"{host}-{suffix}"


runtime_state = RuntimeState(
    instance_id=_build_instance_id(),
    storage_mode=os.getenv("STORAGE_MODE", "auto"),
    bot_mode=os.getenv("BOT_MODE", "polling"),
)
