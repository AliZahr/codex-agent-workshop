#!/usr/bin/env python3
"""Translate Codex hooks into small, privacy-preserving workshop events."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib import error, request


HOST = "127.0.0.1"
PORT = int(os.environ.get("AGENT_WORKSHOP_PORT", "8765"))
BASE_URL = f"http://{HOST}:{PORT}"
PLUGIN_ROOT = Path(os.environ.get("PLUGIN_ROOT", Path(__file__).resolve().parents[1]))
PLUGIN_DATA = Path(os.environ.get("PLUGIN_DATA", Path.home() / ".agent-workshop"))


def classify_tool(name: str) -> tuple[str, str]:
    value = name.lower()
    if value in {"apply_patch", "edit", "write"} or any(x in value for x in ("write_file", "edit_file")):
        return "coding", "editing files"
    if value in {"bash", "exec_command", "write_stdin"} or any(x in value for x in ("terminal", "shell", "command")):
        return "running", "running a command"
    if value in {"agent", "spawn_agent"} or "collaboration" in value:
        return "delegating", "coordinating agents"
    if any(x in value for x in ("read", "search", "find", "list", "view", "browse", "web")):
        return "researching", "researching"
    return "working", "using a tool"


def normalize(payload: dict) -> dict:
    event_name = str(payload.get("hook_event_name", "Unknown"))
    session_id = str(payload.get("session_id", "unknown"))
    cwd = str(payload.get("cwd", ""))
    agent_id = str(payload.get("agent_id") or "main")
    agent_type = str(payload.get("agent_type") or ("Lead agent" if agent_id == "main" else "Agent"))
    state, activity, kind = "thinking", "thinking", "upsert"

    if event_name == "SessionStart":
        state, activity = "idle", "ready"
    elif event_name == "UserPromptSubmit":
        state, activity = "thinking", "starting the task"
    elif event_name == "PreToolUse":
        state, activity = classify_tool(str(payload.get("tool_name", "")))
    elif event_name == "PostToolUse":
        state, activity = "thinking", "reviewing the result"
    elif event_name == "PermissionRequest":
        state, activity = "waiting", "waiting for approval"
    elif event_name == "SubagentStart":
        state, activity = "working", "joining the workshop"
    elif event_name == "SubagentStop":
        state, activity = "success", "finished"
    elif event_name == "Stop":
        state, activity = "success", "task complete"
    elif event_name == "Interrupt":
        state, activity = "failure", "interrupted"
    elif event_name == "SessionEnd":
        state, activity, kind = "idle", "left the workshop", "end"

    # Deliberately exclude prompt, transcript_path, tool_input, tool_response,
    # assistant messages, command text, code, file paths, and output.
    return {
        "version": 1,
        "provider": "codex",
        "session_id": session_id,
        "agent_id": agent_id,
        "agent_type": agent_type[:80],
        "project_label": Path(cwd).name[:80] if cwd else "Codex task",
        "kind": kind,
        "state": state,
        "activity": activity,
        "event": event_name,
        "occurred_at": int(time.time() * 1000),
    }


def post_event(event: dict) -> bool:
    body = json.dumps(event, separators=(",", ":")).encode("utf-8")
    req = request.Request(
        f"{BASE_URL}/api/event",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=0.35) as response:
            return response.status == 204
    except (error.URLError, TimeoutError, OSError):
        return False


def ensure_server(event: dict) -> None:
    if post_event(event):
        return
    PLUGIN_DATA.mkdir(parents=True, exist_ok=True)
    server = PLUGIN_ROOT / "scripts" / "workshop_server.py"
    with (PLUGIN_DATA / "server.log").open("ab") as log:
        subprocess.Popen(
            [sys.executable, str(server), "--host", HOST, "--port", str(PORT)],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            close_fds=True,
            env={**os.environ, "AGENT_WORKSHOP_DATA": str(PLUGIN_DATA)},
        )
    for _ in range(12):
        time.sleep(0.08)
        if post_event(event):
            return


def open_once(session_id: str) -> None:
    if sys.platform != "darwin":
        return
    seen = PLUGIN_DATA / "opened"
    seen.mkdir(parents=True, exist_ok=True)
    marker = seen / hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    try:
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    except FileExistsError:
        return
    subprocess.Popen(
        ["open", BASE_URL],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        event = normalize(payload if isinstance(payload, dict) else {})
        ensure_server(event)
        if event["event"] == "UserPromptSubmit":
            open_once(event["session_id"])
    except Exception:
        # Visualization must never block or alter the Codex task.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
