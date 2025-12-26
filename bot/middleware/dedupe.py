from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from aiogram import BaseMiddleware
from aiogram.types import Update, CallbackQuery

import logging

logger = logging.getLogger(__name__)


@dataclass
class _Hit:
    ts: float
    count: int = 1


class CallbackDedupeMiddleware(BaseMiddleware):
    """
    Prevents accidental duplicate callback processing (double tap, network retries).
    Works in-memory (stateless deployments still benefit per-instance).

    Strategy:
      - key = (user_id, callback_data, message_id)
      - if same key seen within window_s -> short-circuit handler.
      - always answer callback to stop Telegram loading spinner.
    """

    def __init__(self, window_s: float = 2.0, max_cache: int = 5000) -> None:
        self.window_s = float(window_s)
        self.max_cache = int(max_cache)
        self._cache: Dict[Tuple[int, str, int], _Hit] = {}

    def _prune(self, now: float) -> None:
        if len(self._cache) <= self.max_cache:
            return
        # Drop oldest ~25%
        items = sorted(self._cache.items(), key=lambda kv: kv[1].ts)
        drop_n = max(1, int(self.max_cache * 0.25))
        for k, _ in items[:drop_n]:
            self._cache.pop(k, None)

    async def __call__(self, handler, event: Update, data: Dict[str, Any]) -> Any:
        cq: Optional[CallbackQuery] = getattr(event, "callback_query", None)
        if cq is None:
            return await handler(event, data)

        user = cq.from_user
        if user is None:
            return await handler(event, data)

        cb_data = cq.data or ""
        msg_id = cq.message.message_id if cq.message else 0
        key = (int(user.id), cb_data, int(msg_id))

        now = time.time()
        hit = self._cache.get(key)
        if hit and (now - hit.ts) <= self.window_s:
            hit.count += 1
            hit.ts = now
            self._cache[key] = hit
            try:
                await cq.answer("⏳ Уже обрабатываю…", cache_time=1)
            except Exception:
                pass
            logger.warning(
                "dedupe_callback",
                extra={
                    "uid": user.id,
                    "cb": cb_data[:96],
                    "msg_id": msg_id,
                    "dup_count": hit.count,
                    "window_s": self.window_s,
                },
            )
            return None

        self._cache[key] = _Hit(ts=now, count=1)
        self._prune(now)
        return await handler(event, data)
