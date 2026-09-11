#!/usr/bin/env python3
"""Translate Codex hooks into small, privacy-preserving workshop events."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib import error, request


HOST = "127.0.0.1"
PORT = int(os.environ.get("AGENT_WORKSHOP_PORT", "8765"))
BASE_URL = f"http://{HOST}:{PORT}"
PLUGIN_ROOT = Path(os.environ.get("PLUGIN_ROOT", Path(__file__).resolve().parents[1]))
PLUGIN_DATA = Path(os.environ.get("PLUGIN_DATA", Path.home() / ".agent-workshop"))
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\b(bearer|token|password|secret|api[_ -]?key)\s*[:=]\s*\S+"),
)


def safe_summary(value: object, limit: int = 100) -> str:
    text = re.sub(r"\x60{3}.*?\x60{3}", " [code] ", str(value or ""), flags=re.DOTALL)
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" #*-\"'")
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[redacted]", text)
    if len(text) > limit:
        text = text[: max(1, limit - 1)].rstrip() + "…"
    return text


def task_title(payload: dict, cwd: str) -> str:
    prompt = safe_summary(payload.get("prompt"), 84)
    if prompt:
        prompt = re.split(r"(?<=[.!?])\s+", prompt, maxsplit=1)[0]
        return prompt[:84]
    return Path(cwd).name[:80] if cwd else "Codex task"


def first_detail(value: object) -> str:
    if isinstance(value, dict):
        for key in ("description", "query", "q", "message", "task_name", "path", "file_path"):
            detail = value.get(key)
            if isinstance(detail, str) and detail.strip():
                if key in {"path", "file_path"}:
                    return Path(detail).name
                return safe_summary(detail)
        for nested in value.values():
            detail = first_detail(nested)
            if detail:
                return detail
    elif isinstance(value, list):
        for nested in value:
            detail = first_detail(nested)
            if detail:
                return detail
    return ""


def tool_activity(name: str, tool_input: object) -> tuple[str, str, dict | None]:
    state, generic = classify_tool(name)
    lowered = name.lower()
    values = tool_input if isinstance(tool_input, dict) else {}
    assignment = None

    if "spawn_agent" in lowered or lowered == "agent":
        detail = safe_summary(values.get("message"), 110)
        task_name = safe_summary(values.get("task_name"), 60)
        assignment = {
            "task_name": task_name or "Specialist agent",
            "agent_type": safe_summary(values.get("agent_type"), 60),
            "detail": detail or "Working on a delegated task",
        }
        return "delegating", f"Delegating: {assignment['detail']}", assignment
    if lowered in {"bash", "exec_command", "write_stdin"} or "command" in lowered:
        description = safe_summary(values.get("description"), 110)
        return state, description or generic, None
    if lowered in {"apply_patch", "edit", "write"} or any(x in lowered for x in ("write_file", "edit_file")):
        return state, "Editing project files", None

    detail = first_detail(values)
    if detail:
        verb = "Researching" if state == "researching" else "Working on"
        return state, f"{verb}: {detail}", None
    return state, generic, None


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
    title = ""
    assignment = None

    if event_name == "SessionStart":
        state, activity = "idle", "ready"
    elif event_name == "UserPromptSubmit":
        title = task_title(payload, cwd)
        state, activity = "thinking", f"Starting: {title}"
    elif event_name == "PreToolUse":
        state, activity, assignment = tool_activity(
            str(payload.get("tool_name", "")),
            payload.get("tool_input"),
        )
    elif event_name == "PostToolUse":
        state, activity = "thinking", "reviewing the result"
    elif event_name == "PermissionRequest":
        detail = first_detail(payload.get("tool_input"))
        state, activity = "waiting", f"Waiting for approval: {detail}" if detail else "Waiting for approval"
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

    event = {
        "version": 1,
        "provider": "codex",
        "session_id": session_id,
        "agent_id": agent_id,
        "agent_type": agent_type[:80],
        "project_label": Path(cwd).name[:80] if cwd else "Codex task",
        "task_title": title,
        "kind": kind,
        "state": state,
        "activity": activity,
        "event": event_name,
        "occurred_at": int(time.time() * 1000),
    }
    if assignment:
        event["assignment"] = assignment
    # Never include full prompts, transcripts, commands, code, tool results,
    # or file paths. Only the short summaries above leave this process.
    return event


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


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        event = normalize(payload if isinstance(payload, dict) else {})
        ensure_server(event)
    except Exception:
        # Visualization must never block or alter the Codex task.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
