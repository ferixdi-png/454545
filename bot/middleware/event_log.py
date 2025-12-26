"""Event logging middleware.

Provides structured, correlation-friendly logs for every incoming update.
Does NOT log secrets or full message content.
"""
from __future__ import annotations

import logging
import time
import uuid

from app.utils.trace import TraceContext
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

logger = logging.getLogger(__name__)


def _short_uuid() -> str:
    return str(uuid.uuid4())[:8]


class EventLogMiddleware(BaseMiddleware):
    """Logs each update start/end with basic metadata and current FSM state if available."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        start = time.perf_counter()

        event_id = data.get("event_id") or _short_uuid()
        data["event_id"] = event_id

        uid = None
        chat_id = None
        upd_type = type(event).__name__

        # Try to extract user/chat from Update-like events
        try:
            if isinstance(event, Update):
                if event.message and event.message.from_user:
                    uid = event.message.from_user.id
                    chat_id = event.message.chat.id if event.message.chat else None
                elif event.callback_query and event.callback_query.from_user:
                    uid = event.callback_query.from_user.id
                    chat_id = event.callback_query.message.chat.id if event.callback_query.message and event.callback_query.message.chat else None
        except Exception:
            pass

        # FSM state (aiogram injects FSMContext as 'state' in data)
        state_name = None
        try:
            fsm = data.get("state")
            if fsm:
                state_name = await fsm.get_state()
        except Exception:
            state_name = None

        # Light payload hints (lengths only)
        msg_len = None
        cb_len = None
        try:
            if isinstance(event, Update) and event.message and event.message.text:
                msg_len = len(event.message.text)
            if isinstance(event, Update) and event.callback_query and event.callback_query.data:
                cb_len = len(event.callback_query.data)
        except Exception:
            pass

        logger.info(
            "[iid=%s rid=%s uid=%s state=%s type=%s msg_len=%s cb_len=%s] update_in",
            data.get("instance_id") or __import__("os").environ.get("INSTANCE_ID") or "-",
            event_id,
            uid or "-",
            state_name or "-",
            upd_type,
            msg_len if msg_len is not None else "-",
            cb_len if cb_len is not None else "-",
        )

        try:
            # Bind a stable request_id for the whole update lifecycle
            with TraceContext(user_id=uid if (uid and str(uid).isdigit()) else None, request_id=event_id):
                result = await handler(event, data)
                return result
        finally:
            dur_ms = int((time.perf_counter() - start) * 1000)
            logger.info(
                "[iid=%s rid=%s uid=%s state=%s type=%s dur_ms=%s] update_out",
                data.get("instance_id") or __import__("os").environ.get("INSTANCE_ID") or "-",
                event_id,
                uid or "-",
                state_name or "-",
                upd_type,
                dur_ms,
            )
