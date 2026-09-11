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
    def test_normalize_keeps_only_safe_prompt_summary(self):
        event = hook.normalize({
            "hook_event_name": "UserPromptSubmit",
            "session_id": "s1",
            "cwd": "/tmp/project",
            "prompt": "Build the native dashboard. token=very-secret-token",
            "tool_response": "private output",
        })
        self.assertEqual(event["state"], "thinking")
        self.assertIn("Build the native dashboard", event["task_title"])
        rendered = repr(event)
        self.assertNotIn("very-secret-token", rendered)
        self.assertNotIn("private output", rendered)

    def test_tool_classification(self):
        self.assertEqual(hook.classify_tool("Bash")[0], "running")
        self.assertEqual(hook.classify_tool("mcp__docs__search")[0], "researching")
        self.assertEqual(hook.classify_tool("spawn_agent")[0], "delegating")

    def test_spawn_agent_exposes_assignment_summary(self):
        event = hook.normalize({
            "hook_event_name": "PreToolUse",
            "session_id": "s1",
            "tool_name": "spawn_agent",
            "tool_input": {
                "task_name": "reader",
                "message": "Research task tracking and report the data flow.",
                "agent_type": "explorer",
            },
        })
        self.assertEqual(event["state"], "delegating")
        self.assertEqual(event["assignment"]["task_name"], "reader")
        self.assertIn("Research task tracking", event["assignment"]["detail"])

    def test_prompt_event_does_not_launch_external_browser(self):
        payload = io.StringIO('{"hook_event_name":"UserPromptSubmit","session_id":"s1"}')
        with mock.patch.object(hook.sys, "stdin", payload), \
             mock.patch.object(hook, "ensure_server"), \
             mock.patch.object(hook.subprocess, "Popen") as popen:
            self.assertEqual(hook.main(), 0)
        popen.assert_not_called()


class StateTests(unittest.TestCase):
    def setUp(self):
        server.STATE["sessions"] = {}
        server.STATE["updated_at"] = 0

    def base_event(self, **overrides):
        event = {
            "session_id": "one",
            "agent_id": "main",
            "agent_type": "Lead",
            "project_label": "Project A",
            "task_title": "Build task switcher",
            "kind": "upsert",
            "state": "thinking",
            "activity": "starting",
            "event": "UserPromptSubmit",
            "occurred_at": 1,
        }
        event.update(overrides)
        return event

    def test_multiple_sessions_coexist(self):
        self.assertTrue(server.apply_event(self.base_event()))
        self.assertTrue(server.apply_event(self.base_event(
            session_id="two",
            project_label="Project B",
            task_title="Fix authentication",
            occurred_at=2,
        )))
        self.assertEqual(set(server.STATE["sessions"]), {"one", "two"})
        self.assertEqual(server.STATE["sessions"]["one"]["title"], "Build task switcher")
        self.assertEqual(server.STATE["sessions"]["two"]["title"], "Fix authentication")

    def test_subagent_claims_pending_assignment(self):
        delegated = self.base_event(
            state="delegating",
            activity="delegating",
            event="PreToolUse",
            assignment={
                "task_name": "UI reviewer",
                "agent_type": "explorer",
                "detail": "Inspect the responsive layout",
            },
        )
        started = self.base_event(
            agent_id="agent-2",
            agent_type="explorer",
            task_title="",
            state="working",
            activity="joining",
            event="SubagentStart",
            occurred_at=2,
        )
        server.apply_event(delegated)
        server.apply_event(started)
        agent = server.STATE["sessions"]["one"]["agents"]["agent-2"]
        self.assertEqual(agent["label"], "UI reviewer")
        self.assertEqual(agent["activity"], "Inspect the responsive layout")

    def test_late_assignment_updates_waiting_subagent(self):
        started = self.base_event(
            agent_id="agent-2",
            agent_type="explorer",
            task_title="",
            state="working",
            activity="joining",
            event="SubagentStart",
            occurred_at=2,
        )
        delegated = self.base_event(
            state="delegating",
            activity="delegating",
            event="PreToolUse",
            assignment={
                "task_name": "Session mapper",
                "agent_type": "explorer",
                "detail": "Map concurrent session behavior",
            },
            occurred_at=1,
        )
        server.apply_event(started)
        server.apply_event(delegated)
        agent = server.STATE["sessions"]["one"]["agents"]["agent-2"]
        self.assertEqual(agent["label"], "Session mapper")
        self.assertEqual(agent["activity"], "Map concurrent session behavior")

    def test_public_state_is_sorted_by_recent_activity(self):
        server.apply_event(self.base_event())
        server.apply_event(self.base_event(session_id="two", occurred_at=5))
        self.assertEqual([item["id"] for item in server.public_state()["sessions"]], ["two", "one"])

    def test_task_title_stays_on_first_prompt(self):
        server.apply_event(self.base_event(task_title="Original task"))
        server.apply_event(self.base_event(task_title="Later follow-up", occurred_at=2))
        self.assertEqual(server.STATE["sessions"]["one"]["title"], "Original task")

    def test_rejects_unknown_state(self):
        event = self.base_event(state="secret")
        self.assertFalse(server.apply_event(event))


if __name__ == "__main__":
    unittest.main()
