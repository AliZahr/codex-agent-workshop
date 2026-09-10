#!/usr/bin/env python3
"""Loopback-only HTTP server for Agent Workshop."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
LOCK = threading.RLock()
STATE = {
    "session_id": None,
    "project_label": "Waiting for a Codex task",
    "active": False,
    "updated_at": 0,
    "agents": {},
}
ALLOWED_STATES = {"idle", "thinking", "researching", "coding", "running", "delegating", "waiting", "working", "success", "failure"}


def apply_event(event: dict) -> bool:
    required = {"session_id", "agent_id", "state", "activity", "occurred_at", "kind"}
    if not required.issubset(event) or event.get("state") not in ALLOWED_STATES:
        return False
    session_id = str(event["session_id"])[:200]
    agent_id = str(event["agent_id"])[:200]
    occurred_at = int(event["occurred_at"])

    with LOCK:
        if STATE["session_id"] != session_id and agent_id == "main":
            STATE.update({
                "session_id": session_id,
                "project_label": str(event.get("project_label") or "Codex task")[:80],
                "active": True,
                "updated_at": occurred_at,
                "agents": {},
            })
        if STATE["session_id"] != session_id:
            return True
        if event["kind"] == "end":
            if agent_id == "main":
                STATE["active"] = False
            else:
                STATE["agents"].pop(agent_id, None)
        else:
            previous = STATE["agents"].get(agent_id, {})
            if occurred_at >= int(previous.get("occurred_at", 0)):
                STATE["agents"][agent_id] = {
                    "id": agent_id,
                    "label": str(event.get("agent_type") or ("Lead agent" if agent_id == "main" else "Agent"))[:80],
                    "state": event["state"],
                    "activity": str(event["activity"])[:100],
                    "occurred_at": occurred_at,
                }
            STATE["active"] = True
        STATE["updated_at"] = max(int(STATE["updated_at"]), occurred_at)
    return True


class WorkshopHandler(BaseHTTPRequestHandler):
    server_version = "AgentWorkshop/0.1"

    def log_message(self, fmt: str, *args) -> None:
        return

    def _send(self, status: int, content_type: str, body: bytes, cache: str = "no-store") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._send(200, "text/plain; charset=utf-8", b"ok")
            return
        if path == "/api/state":
            with LOCK:
                payload = {**STATE, "agents": list(STATE["agents"].values()), "server_time": int(time.time() * 1000)}
            self._send(200, "application/json; charset=utf-8", json.dumps(payload).encode("utf-8"))
            return
        files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
        }
        target = files.get(path)
        if not target:
            self._send(404, "text/plain; charset=utf-8", b"not found")
            return
        name, content_type = target
        self._send(200, content_type, (ASSETS / name).read_bytes(), "no-cache")

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/event":
            self._send(404, "text/plain; charset=utf-8", b"not found")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 16384 or self.headers.get_content_type() != "application/json":
                raise ValueError
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or not apply_event(payload):
                raise ValueError
        except (ValueError, TypeError, json.JSONDecodeError):
            self._send(400, "text/plain; charset=utf-8", b"invalid event")
            return
        self.send_response(204)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("Agent Workshop only binds to loopback addresses")
    server = ThreadingHTTPServer((args.host, args.port), WorkshopHandler)
    server.serve_forever(poll_interval=0.4)


if __name__ == "__main__":
    main()
