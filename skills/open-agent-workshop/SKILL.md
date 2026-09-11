---
name: open-agent-workshop
description: Open or show the live Agent Workshop inside the Codex app when the user asks to view, watch, or return to the agent room. Do not use for ordinary tasks that do not ask to see the workshop.
---

# Open Agent Workshop

Show Agent Workshop at `http://127.0.0.1:8765/` in a Codex browser panel using the Codex app's `open_in_codex` capability with a browser target. Prefer right-side placement so the user can watch agents while keeping the task visible.

Do not launch or redirect to an external system browser. The workshop server normally starts from its lifecycle hook when a Codex task begins. If the local health endpoint is unavailable, start `scripts/workshop_server.py` from this plugin's installed root on loopback port `8765`, then open the panel.

Keep the resulting Codex browser tab available to the user.
