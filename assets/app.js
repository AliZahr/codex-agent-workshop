"use strict";

const floor = document.getElementById("floor");
const project = document.getElementById("project");
const taskState = document.getElementById("task-state");
const updated = document.getElementById("updated");
const agentCount = document.getElementById("agent-count");
const connectionDot = document.getElementById("connection-dot");
const connectionText = document.getElementById("connection-text");

const stateLabels = {
  idle: "Ready", thinking: "Thinking", researching: "Researching", coding: "Coding",
  running: "Running", delegating: "Coordinating", waiting: "Waiting", working: "Working",
  success: "Complete", failure: "Needs attention"
};

const stateMarks = {
  idle: "○", thinking: "•••", researching: "⌕", coding: "</>", running: "↻",
  delegating: "↗", waiting: "Ⅱ", working: "◇", success: "✓", failure: "!"
};

function hash(text) {
  let value = 0;
  for (const char of text) value = ((value << 5) - value + char.charCodeAt(0)) | 0;
  return Math.abs(value);
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function createPerson() {
  const person = element("div", "person");
  person.setAttribute("aria-hidden", "true");
  person.append(element("span", "body"), element("span", "head"), element("span", "hair"), element("span", "face"), element("span", "headset"));
  return person;
}

function createMonitor() {
  const rig = element("div", "screen-rig");
  rig.setAttribute("aria-hidden", "true");
  const monitor = element("div", "monitor");
  for (let index = 0; index < 4; index += 1) monitor.append(element("i", "code-line"));
  rig.append(monitor);
  return rig;
}

function createStation(agent) {
  const station = element("article", `station${agent.id === "main" ? " lead" : ""}`);
  station.dataset.state = agent.state;
  station.style.setProperty("--agent-hue", String(agent.id === "main" ? 230 : 190 + (hash(agent.id) % 105)));
  station.setAttribute("aria-label", `${agent.label}: ${agent.activity}`);

  const head = element("div", "station-head");
  head.append(
    element("span", "role", agent.id === "main" ? "Primary agent" : agent.label),
    element("span", "state-chip", stateLabels[agent.state] || "Active")
  );

  const workspace = element("div", "workspace");
  workspace.append(
    createPerson(),
    element("span", "state-bubble", stateMarks[agent.state] || "•"),
    createMonitor(),
    element("span", "desk")
  );

  const copy = element("div", "station-copy");
  copy.append(
    element("strong", "agent-name", agent.id === "main" ? "Lead agent" : agent.label),
    element("span", "activity", agent.activity)
  );
  station.append(head, workspace, copy);
  return station;
}

function renderEmpty() {
  const empty = element("div", "empty");
  const robot = element("span", "empty-robot");
  robot.setAttribute("aria-hidden", "true");
  empty.append(robot, element("strong", "", "The studio is ready"), element("span", "", "Start a Codex task and your agents will take their desks."));
  floor.replaceChildren(empty);
}

function render(state) {
  project.textContent = state.project_label || "Codex task";
  updated.textContent = state.updated_at ? `Updated ${new Date(state.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}` : "No events yet";
  const agents = Array.isArray(state.agents) ? state.agents : [];
  const lead = agents.find((agent) => agent.id === "main");
  taskState.textContent = lead ? lead.activity : (state.active ? "Task active" : "Ready for work");
  agentCount.textContent = agents.length ? `${agents.length} agent${agents.length === 1 ? "" : "s"} in the studio` : "Workshop standing by";

  if (!agents.length) {
    renderEmpty();
    return;
  }
  floor.replaceChildren(...agents.map(createStation));
}

async function refresh() {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error("offline");
    render(await response.json());
    connectionDot.className = "signal online";
    connectionText.textContent = "Live · local";
  } catch {
    connectionDot.className = "signal offline";
    connectionText.textContent = "Reconnecting";
  }
}

refresh();
setInterval(refresh, 700);
