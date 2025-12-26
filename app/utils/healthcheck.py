"""
Lightweight healthcheck HTTP server for Render.
Uses standard library only.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Optional, Tuple


# Global state for healthcheck
_started_at = __import__("time").time()
_health_state = {
    "mode": "starting",
    "reason": "initializing",
    "status": "starting",
    "ready": False,
    "instance": None,
    "uptime_s": 0,
}

def set_health_state(
    mode: str,
    reason: str = "",
    *,
    ready: Optional[bool] = None,
    instance: Optional[str] = None,
    extra: Optional[dict] = None,
) -> None:
    """Update health state visible in /health and /ready endpoints.

    Tolerant to additional kwargs used during startup.
    """
    global _health_state
    if ready is None:
        ready = _health_state.get("ready", False)
    state = {
        **_health_state,
        "mode": mode,
        "reason": reason,
        "status": "ok" if mode in ("active", "standby") else mode,
        "ready": bool(ready),
    }
    if instance is not None:
        state["instance"] = instance
    if extra:
        state.update(extra)
    _health_state = state

class _HealthcheckHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        # Update uptime on every request
        _health_state["uptime_s"] = int(__import__("time").time() - _started_at)

        if self.path in ("/", "/health", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            response = json.dumps(_health_state).encode('utf-8')
            self.wfile.write(response)
            return

        if self.path in ("/ready", "/readyz"):
            mode = _health_state.get("mode")
            ready = _health_state.get("ready", False)
            status = 200 if (mode == "active" and ready) else 503
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            response = json.dumps(_health_state).encode('utf-8')
            self.wfile.write(response)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def start_healthcheck_server(port: int) -> Tuple[ThreadingHTTPServer, Thread]:
    server = ThreadingHTTPServer(("0.0.0.0", port), _HealthcheckHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop_healthcheck_server(server: Optional[ThreadingHTTPServer]) -> None:
    if not server:
        return
    server.shutdown()
    server.server_close()



def get_health_state() -> dict:
    """Return a copy of current health state (safe for JSON)."""
    return dict(_health_state)
