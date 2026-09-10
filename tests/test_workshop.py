import importlib.util
import io
import pathlib
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = load_module("workshop_hook", ROOT / "scripts" / "workshop_hook.py")
server = load_module("workshop_server", ROOT / "scripts" / "workshop_server.py")


class HookTests(unittest.TestCase):
    def test_normalize_drops_sensitive_fields(self):
        event = hook.normalize({
            "hook_event_name": "PreToolUse",
            "session_id": "s1",
            "cwd": "/tmp/project",
            "tool_name": "apply_patch",
            "tool_input": {"command": "secret code"},
            "prompt": "private prompt",
            "tool_response": "private output",
        })
        self.assertEqual(event["state"], "coding")
        rendered = repr(event)
        self.assertNotIn("secret code", rendered)
        self.assertNotIn("private prompt", rendered)
        self.assertNotIn("private output", rendered)

    def test_tool_classification(self):
        self.assertEqual(hook.classify_tool("Bash")[0], "running")
        self.assertEqual(hook.classify_tool("mcp__docs__search")[0], "researching")
        self.assertEqual(hook.classify_tool("spawn_agent")[0], "delegating")

    def test_prompt_event_does_not_launch_external_browser(self):
        payload = io.StringIO('{"hook_event_name":"UserPromptSubmit","session_id":"s1"}')
        with mock.patch.object(hook.sys, "stdin", payload), \
             mock.patch.object(hook, "ensure_server"), \
             mock.patch.object(hook.subprocess, "Popen") as popen:
            self.assertEqual(hook.main(), 0)
        popen.assert_not_called()


class StateTests(unittest.TestCase):
    def setUp(self):
        server.STATE.update({"session_id": None, "project_label": "Waiting", "active": False, "updated_at": 0, "agents": {}})

    def test_new_session_replaces_previous_agents(self):
        first = {"session_id": "one", "agent_id": "main", "agent_type": "Lead", "project_label": "A", "kind": "upsert", "state": "thinking", "activity": "starting", "occurred_at": 1}
        second = {**first, "session_id": "two", "project_label": "B", "occurred_at": 2}
        self.assertTrue(server.apply_event(first))
        self.assertTrue(server.apply_event(second))
        self.assertEqual(server.STATE["session_id"], "two")
        self.assertEqual(server.STATE["project_label"], "B")
        self.assertEqual(list(server.STATE["agents"]), ["main"])

    def test_rejects_unknown_state(self):
        event = {"session_id": "one", "agent_id": "main", "kind": "upsert", "state": "secret", "activity": "x", "occurred_at": 1}
        self.assertFalse(server.apply_event(event))


if __name__ == "__main__":
    unittest.main()
