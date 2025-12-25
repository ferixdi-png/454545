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
_health_state = {"mode": "starting", "reason": "initializing"}


def set_health_state(mode: str, reason: str = "") -> None:
    """Update health state visible in /health endpoint."""
    global _health_state
    _health_state = {"mode": mode, "reason": reason, "status": "ok"}


class _HealthcheckHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/health", "/healthz"):
            self.send_response(200)
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
