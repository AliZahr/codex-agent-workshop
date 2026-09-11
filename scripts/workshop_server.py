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
MAX_SESSIONS = 12
MAX_HISTORY = 40
STATE = {"sessions": {}, "updated_at": 0}
ALLOWED_STATES = {"idle", "thinking", "researching", "coding", "running", "delegating", "waiting", "working", "success", "failure"}


def new_session(session_id: str, event: dict, occurred_at: int) -> dict:
    return {
        "id": session_id,
        "title": str(event.get("task_title") or event.get("project_label") or "Codex task")[:84],
        "has_title": bool(str(event.get("task_title") or "").strip()),
        "project_label": str(event.get("project_label") or "Codex task")[:80],
        "active": True,
        "turn_id": str(event.get("turn_id") or "")[:200],
        "updated_at": occurred_at,
        "agents": {},
        "history": [],
        "pending_assignments": [],
    }


def prune_sessions() -> None:
    sessions = STATE["sessions"]
    while len(sessions) > MAX_SESSIONS:
        candidate = min(
            sessions.values(),
            key=lambda item: (bool(item["active"]), int(item["updated_at"])),
        )
        sessions.pop(candidate["id"], None)


def claim_assignment(session: dict, event: dict) -> dict | None:
    pending = session["pending_assignments"]
    agent_type = str(event.get("agent_type") or "").lower()
    for index, assignment in enumerate(pending):
        expected = str(assignment.get("agent_type") or "").lower()
        if not expected or expected == agent_type:
            return pending.pop(index)
    return pending.pop(0) if pending else None


def attach_or_queue_assignment(session: dict, assignment: dict) -> None:
    expected = str(assignment.get("agent_type") or "").lower()
    candidates = [
        agent for agent in session["agents"].values()
        if agent["id"] != "main"
        and agent.get("awaiting_assignment")
        and (not expected or str(agent.get("agent_type") or "").lower() == expected)
    ]
    if candidates:
        agent = max(candidates, key=lambda item: int(item["occurred_at"]))
        agent["label"] = assignment["task_name"] or agent["label"]
        agent["activity"] = assignment["detail"]
        agent["awaiting_assignment"] = False
        return
    history_candidates = [
        item for item in session["history"]
        if item.get("awaiting_assignment")
        and (not expected or str(item.get("agent_type") or "").lower() == expected)
    ]
    if history_candidates:
        item = max(history_candidates, key=lambda value: int(value["completed_at"]))
        item["label"] = assignment["task_name"] or item["label"]
        item["activity"] = assignment["detail"]
        item["awaiting_assignment"] = False
        return
    session["pending_assignments"].append(assignment)
    session["pending_assignments"] = session["pending_assignments"][-16:]


def archive_agent(session: dict, agent_id: str, event: dict, occurred_at: int) -> None:
    previous = session["agents"].pop(agent_id, None)
    if previous is None:
        return
    session["history"].append({
        "id": f"{agent_id}:{occurred_at}",
        "agent_id": agent_id,
        "label": previous.get("label") or event.get("agent_type") or "Agent",
        "agent_type": previous.get("agent_type") or event.get("agent_type") or "Agent",
        "activity": previous.get("activity") or "Completed delegated work",
        "completed_at": occurred_at,
        "awaiting_assignment": bool(previous.get("awaiting_assignment")),
    })
    session["history"] = session["history"][-MAX_HISTORY:]


def apply_event(event: dict) -> bool:
    required = {"session_id", "agent_id", "state", "activity", "occurred_at", "kind"}
    if not required.issubset(event) or event.get("state") not in ALLOWED_STATES:
        return False
    session_id = str(event["session_id"])[:200]
    agent_id = str(event["agent_id"])[:200]
    occurred_at = int(event["occurred_at"])

    with LOCK:
        sessions = STATE["sessions"]
        session = sessions.get(session_id)
        if session is None:
            session = new_session(session_id, event, occurred_at)
            sessions[session_id] = session

        title = str(event.get("task_title") or "").strip()
        if title and not session["has_title"]:
            session["title"] = title[:84]
            session["has_title"] = True
        project_label = str(event.get("project_label") or "").strip()
        if project_label:
            session["project_label"] = project_label[:80]

        assignment = event.get("assignment")
        if isinstance(assignment, dict):
            attach_or_queue_assignment(session, {
                "task_name": str(assignment.get("task_name") or "Specialist agent")[:60],
                "agent_type": str(assignment.get("agent_type") or "")[:60],
                "detail": str(assignment.get("detail") or "Working on a delegated task")[:500],
            })

        if event["kind"] == "end":
            if agent_id == "main":
                session["active"] = False
            else:
                archive_agent(session, agent_id, event, occurred_at)
        elif event.get("event") == "SubagentStop" and agent_id != "main":
            archive_agent(session, agent_id, event, occurred_at)
        else:
            previous = session["agents"].get(agent_id, {})
            if occurred_at >= int(previous.get("occurred_at", 0)):
                label = str(previous.get("label") or event.get("agent_type") or ("Lead agent" if agent_id == "main" else "Agent"))[:80]
                activity = str(event["activity"])[:500]
                claimed = None
                if agent_id != "main" and event.get("event") == "SubagentStart":
                    claimed = claim_assignment(session, event)
                    if claimed:
                        label = claimed["task_name"] or label
                        activity = claimed["detail"]
                session["agents"][agent_id] = {
                    "id": agent_id,
                    "label": label,
                    "state": event["state"],
                    "activity": activity,
                    "occurred_at": occurred_at,
                    "agent_type": str(event.get("agent_type") or previous.get("agent_type") or "")[:80],
                    "awaiting_assignment": bool(
                        agent_id != "main"
                        and event.get("event") == "SubagentStart"
                        and claimed is None
                    ),
                }
            event_name = event.get("event")
            event_turn_id = str(event.get("turn_id") or "")[:200]
            if event_name in {"SessionStart", "UserPromptSubmit"}:
                session["active"] = True
                if event_name == "UserPromptSubmit" and event_turn_id:
                    session["turn_id"] = event_turn_id
            elif event_name == "Stop":
                current_turn_id = session.get("turn_id") or ""
                if not current_turn_id or not event_turn_id or event_turn_id == current_turn_id:
                    session["active"] = False

        session["updated_at"] = max(int(session["updated_at"]), occurred_at)
        STATE["updated_at"] = max(int(STATE["updated_at"]), occurred_at)
        prune_sessions()
    return True


def public_state() -> dict:
    sessions = []
    active_sessions = (session for session in STATE["sessions"].values() if session["active"])
    for session in sorted(active_sessions, key=lambda item: int(item["updated_at"]), reverse=True):
        sessions.append({
            "id": session["id"],
            "title": session["title"],
            "project_label": session["project_label"],
            "active": session["active"],
            "updated_at": session["updated_at"],
            "agents": [
                {
                    "id": agent["id"],
                    "label": agent["label"],
                    "state": agent["state"],
                    "activity": agent["activity"],
                    "occurred_at": agent["occurred_at"],
                }
                for agent in session["agents"].values()
            ],
            "history": [
                {
                    "id": item["id"],
                    "agent_id": item["agent_id"],
                    "label": item["label"],
                    "agent_type": item["agent_type"],
                    "activity": item["activity"],
                    "completed_at": item["completed_at"],
                }
                for item in reversed(session["history"])
            ],
        })
    return {
        "sessions": sessions,
        "updated_at": STATE["updated_at"],
        "server_time": int(time.time() * 1000),
    }


class WorkshopHandler(BaseHTTPRequestHandler):
    server_version = "AgentWorkshop/0.2"

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
                payload = public_state()
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
