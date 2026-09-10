# Agent Workshop

Agent Workshop opens a local cartoon office when a new Codex task starts. The lead agent and subagents change posture and status as Codex moves through thinking, research, edits, commands, approvals, completion, failure, and interruption.

Source: [github.com/AliZahr/codex-agent-workshop](https://github.com/AliZahr/codex-agent-workshop)

## Privacy and security

- The server binds only to `127.0.0.1`.
- Hooks send coarse lifecycle metadata only.
- The plugin does not read transcripts.
- Prompts, commands, tool inputs, tool results, code, file paths, and assistant output are discarded.
- The hook is fail-open: a visualization error never blocks a Codex task.

## Local development

Run the server:

```sh
python3 scripts/workshop_server.py
```

Then open `http://127.0.0.1:8765`.

Run tests:

```sh
python3 -m unittest discover -s tests -v
```

After installation, start a new Codex task and review/trust the plugin hooks when Codex asks. On macOS, the workshop opens once per new task in the default browser.
