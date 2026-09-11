# Agent Workshop

Agent Workshop is a miniature local conference room for Codex. The lead agent and subagents work in parallel from stable seats around a shared table. Waiting states draw dependency routes, and a completed agent walks to the receiving agent, delivers a work packet, then returns to its place.

The interface is designed as a native-feeling Codex companion: edge-to-edge system styling, a live activity rail, a room focus mode, dark/light appearance support, and responsive layouts for narrow panels.

Concurrent Codex chats are kept as separate studios. Use the task switcher to move between them. Each studio shows a short title derived locally from its first prompt and a concise description of what every agent is doing.

Source: [github.com/AliZahr/codex-agent-workshop](https://github.com/AliZahr/codex-agent-workshop)

## Privacy and security

- The server binds only to `127.0.0.1`.
- Hooks send lifecycle metadata plus short, locally generated task and activity summaries.
- The plugin does not read transcripts.
- Full prompts, commands, tool inputs, tool results, code, file paths, transcripts, and assistant output are discarded.
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

After installation, start a new Codex task and review/trust the plugin hooks when Codex asks. Keep http://127.0.0.1:8765 open in Codex's built-in browser to watch it update. The plugin deliberately does not launch an external browser.
