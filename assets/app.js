"use strict";

const stage = document.getElementById("office-stage");
const agentsLayer = document.getElementById("agents-layer");
const dependencyLayer = document.getElementById("dependency-layer");
const emptyRoom = document.getElementById("empty-room");
const project = document.getElementById("project");
const taskTitle = document.getElementById("task-title");
const taskState = document.getElementById("task-state");
const tableActivity = document.getElementById("table-activity");
const updated = document.getElementById("updated");
const agentCount = document.getElementById("agent-count");
const announcement = document.getElementById("announcement");
const connectionDot = document.getElementById("connection-dot");
const connectionText = document.getElementById("connection-text");
const activityList = document.getElementById("activity-list");
const activeTotal = document.getElementById("active-total");
const focusToggle = document.getElementById("focus-toggle");
const taskList = document.getElementById("task-list");
const taskTotal = document.getElementById("task-total");
const agentInspector = document.getElementById("agent-inspector");
const inspectorClose = document.getElementById("inspector-close");
const inspectorName = document.getElementById("inspector-name");
const inspectorState = document.getElementById("inspector-state");
const inspectorTask = document.getElementById("inspector-task");
const inspectorActivity = document.getElementById("inspector-activity");
const inspectorProject = document.getElementById("inspector-project");
const inspectorKicker = document.getElementById("inspector-kicker");
const historySection = document.getElementById("history-section");
const historyList = document.getElementById("history-list");
const historyTotal = document.getElementById("history-total");
const studioClock = document.getElementById("studio-clock");

const stateLabels = {
  idle: "Ready", thinking: "Thinking", researching: "Researching", coding: "Coding",
  running: "Running", delegating: "Coordinating", waiting: "Waiting for input", working: "Working",
  success: "Complete", failure: "Needs attention"
};
const stateMarks = {
  idle: "○", thinking: "•••", researching: "⌕", coding: "</>", running: "↻",
  delegating: "↗", waiting: "Ⅱ", working: "◇", success: "✓", failure: "!"
};
const slots = [
  { x: 50, y: 83 }, { x: 18, y: 62 }, { x: 82, y: 62 }, { x: 29, y: 24 },
  { x: 71, y: 24 }, { x: 11, y: 36 }, { x: 89, y: 36 }, { x: 50, y: 18 }
];
const seatById = new Map();
const slotById = new Map();
const previousStates = new Map();
let lastSignature = "";
let connectionState = "connecting";
let lastAgents = [];
let lastSessions = [];
let selectedSessionId = null;
let inspectedRecord = null;

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

function createCharacter() {
  const character = element("div", "mini-agent");
  character.setAttribute("aria-hidden", "true");
  character.append(
    element("span", "agent-body"), element("span", "agent-head"), element("span", "agent-hair"),
    element("span", "agent-face"), element("span", "agent-arm left"), element("span", "agent-arm right"),
    element("span", "headset"), element("span", "packet")
  );
  return character;
}

function nextSlot(agentId) {
  if (agentId === "main") return 0;
  const used = new Set(slotById.values());
  for (let index = 1; index < slots.length; index += 1) if (!used.has(index)) return index;
  return 1 + (hash(agentId) % (slots.length - 1));
}

function buildSeat(agent) {
  const seat = element("button", `agent-seat${agent.id === "main" ? " lead" : ""}`);
  seat.type = "button";
  const slot = nextSlot(agent.id);
  slotById.set(agent.id, slot);
  seat.style.setProperty("--x", slots[slot].x);
  seat.style.setProperty("--y", slots[slot].y);
  seat.style.setProperty("--agent-hue", String(agent.id === "main" ? 230 : 185 + (hash(agent.id) % 115)));
  seat.dataset.agentId = agent.id;
  seat.addEventListener("click", () => openAgentDetails(agent.id));

  const label = element("div", "seat-label");
  label.append(element("strong", "agent-name"), element("span", "agent-status"));
  const bubble = element("span", "state-bubble");
  bubble.setAttribute("aria-hidden", "true");
  seat.append(element("span", "chair"), createCharacter(), element("span", "seat-laptop"), bubble, label);
  agentsLayer.append(seat);
  seat.classList.add("arriving");
  window.setTimeout(() => seat.classList.remove("arriving"), 850);
  seatById.set(agent.id, seat);
  return seat;
}

function updateSeat(agent) {
  const seat = seatById.get(agent.id) || buildSeat(agent);
  const stateLabel = stateLabels[agent.state] || "Active";
  seat.dataset.state = agent.state;
  seat.setAttribute("aria-label", `${agent.label}, ${stateLabel}: ${agent.activity}`);
  seat.querySelector(".agent-name").textContent = agent.id === "main" ? "Lead agent" : agent.label;
  seat.querySelector(".agent-status").textContent = `${stateLabel} · ${agent.activity}`;
  seat.querySelector(".state-bubble").textContent = stateMarks[agent.state] || "•";
  return seat;
}

function renderActivityList(agents) {
  activeTotal.textContent = String(agents.length);
  if (!agents.length) {
    activityList.replaceChildren();
    const empty = element("div", "activity-empty");
    const icon = element("span", "", "◎");
    icon.setAttribute("aria-hidden", "true");
    empty.append(icon, element("p", "", "Agents will appear here as they join."));
    activityList.append(empty);
    return;
  }

  const rows = agents.map((agent) => {
    const row = element("button", "activity-row");
    row.type = "button";
    row.dataset.state = agent.state;
    row.dataset.agentId = agent.id;
    row.setAttribute("aria-label", `Show details for ${agent.id === "main" ? "Lead agent" : agent.label}`);
    row.addEventListener("click", () => openAgentDetails(agent.id));
    const dot = element("span", "row-dot");
    dot.setAttribute("aria-hidden", "true");
    const copy = element("div", "row-copy");
    copy.append(
      element("strong", "", agent.id === "main" ? "Lead agent" : agent.label),
      element("span", "", agent.activity)
    );
    row.append(dot, copy, element("span", "row-state", stateLabels[agent.state] || "Active"));
    return row;
  });
  activityList.replaceChildren(...rows);
}

function formatCompletedTime(value) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function renderHistoryList(history) {
  historyTotal.textContent = String(history.length);
  historySection.hidden = history.length === 0;
  const rows = history.map((item) => {
    const row = element("button", "history-row");
    row.type = "button";
    row.setAttribute("aria-label", `Show completed work by ${item.label}`);
    row.addEventListener("click", () => openHistoryDetails(item.id));
    const avatar = element("span", "history-avatar", "✓");
    const copy = element("span", "history-copy");
    copy.append(element("strong", "", item.label), element("span", "", item.activity));
    row.append(avatar, copy, element("time", "", formatCompletedTime(item.completed_at)));
    return row;
  });
  historyList.replaceChildren(...rows);
}

function selectedSession() {
  return lastSessions.find((item) => item.id === selectedSessionId) || null;
}

function updateAgentInspector() {
  if (!inspectedRecord) return;
  const session = selectedSession();
  const records = session && (inspectedRecord.kind === "history" ? session.history : session.agents);
  const agent = records && records.find((item) => item.id === inspectedRecord.id);
  if (!session || !agent) {
    inspectedRecord = null;
    if (agentInspector.open) agentInspector.close();
    return;
  }
  inspectorName.textContent = agent.id === "main" ? "Lead agent" : agent.label;
  const completed = inspectedRecord.kind === "history";
  inspectorKicker.textContent = completed ? "COMPLETED WORK" : "CURRENT ASSIGNMENT";
  inspectorState.textContent = completed ? `Delivered ${formatCompletedTime(agent.completed_at)}` : (stateLabels[agent.state] || "Active");
  inspectorState.dataset.state = completed ? "success" : agent.state;
  inspectorTask.textContent = session.title || session.project_label || "Codex task";
  inspectorActivity.textContent = agent.activity || "Working on the current task.";
  inspectorProject.textContent = session.project_label || "Codex";
}

function openAgentDetails(agentId) {
  inspectedRecord = { kind: "active", id: agentId };
  updateAgentInspector();
  if (!agentInspector.open) agentInspector.showModal();
}

function openHistoryDetails(historyId) {
  inspectedRecord = { kind: "history", id: historyId };
  updateAgentInspector();
  if (!agentInspector.open) agentInspector.showModal();
}

function resetRoom() {
  agentsLayer.replaceChildren();
  dependencyLayer.replaceChildren();
  seatById.clear();
  slotById.clear();
  previousStates.clear();
  lastAgents = [];
  lastSignature = "";
  if (agentInspector.open) agentInspector.close();
  inspectedRecord = null;
}

function selectSession(sessionId) {
  if (selectedSessionId !== sessionId) {
    selectedSessionId = sessionId;
    resetRoom();
  }
  renderTaskList(lastSessions);
  const session = lastSessions.find((item) => item.id === selectedSessionId);
  if (session) render(session);
}

function renderTaskList(sessions) {
  taskTotal.textContent = String(sessions.length);
  if (!sessions.length) {
    taskList.replaceChildren(element("div", "task-empty", "No active tasks yet"));
    return;
  }

  const rows = sessions.map((session) => {
    const button = element("button", "task-row");
    button.type = "button";
    button.dataset.sessionId = session.id;
    button.classList.toggle("selected", session.id === selectedSessionId);
    button.setAttribute("aria-pressed", String(session.id === selectedSessionId));
    const copy = element("span", "task-row-copy");
    copy.append(
      element("strong", "", session.title || session.project_label || "Codex task"),
      element("span", "", `${session.project_label || "Codex"} · ${session.agents.length} agent${session.agents.length === 1 ? "" : "s"}`)
    );
    button.append(
      element("i", session.active ? "task-live" : "task-done"),
      copy,
      element("span", "task-state-pill", session.active ? "Live" : "Done")
    );
    button.addEventListener("click", () => selectSession(session.id));
    return button;
  });
  taskList.replaceChildren(...rows);
}

function removeMissingAgents(ids) {
  for (const [id, seat] of seatById) {
    if (ids.has(id)) continue;
    seatById.delete(id);
    slotById.delete(id);
    previousStates.delete(id);
    const courier = seat.querySelector(".mini-agent");
    const leadSeat = seatById.get("main");
    const from = courier.getBoundingClientRect();
    const lead = leadSeat && leadSeat.querySelector(".mini-agent").getBoundingClientRect();
    const stageRect = stage.getBoundingClientRect();
    const toLeadX = lead ? lead.left + lead.width / 2 - from.left - from.width / 2 : 0;
    const toLeadY = lead ? lead.top + lead.height / 2 - from.top - from.height / 2 : 0;
    const exitX = stageRect.right - from.left + 40;
    const exitY = stageRect.bottom - from.top - 70;
    seat.classList.add("departing");
    courier.classList.add("carrying");
    if (courier.animate && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      courier.animate([
        { transform: "translate(0, 0)" },
        { transform: `translate(${toLeadX}px, ${toLeadY}px)`, offset: .42 },
        { transform: `translate(${toLeadX}px, ${toLeadY}px)`, offset: .55 },
        { transform: `translate(${exitX}px, ${exitY}px)`, opacity: 0 }
      ], { duration: 2400, easing: "ease-in-out", fill: "forwards" }).onfinish = () => seat.remove();
    } else {
      window.setTimeout(() => seat.remove(), 650);
    }
  }
}

function addLine(fromSeat, toSeat, className = "") {
  if (!fromSeat || !toSeat) return null;
  const stageRect = stage.getBoundingClientRect();
  const from = fromSeat.getBoundingClientRect();
  const to = toSeat.getBoundingClientRect();
  const x1 = from.left + from.width / 2 - stageRect.left;
  const y1 = from.top + from.height / 2 - stageRect.top;
  const x2 = to.left + to.width / 2 - stageRect.left;
  const y2 = to.top + to.height / 2 - stageRect.top;
  const dx = x2 - x1;
  const dy = y2 - y1;
  const line = element("span", `dependency-line ${className}`.trim());
  line.style.left = `${x1}px`;
  line.style.top = `${y1}px`;
  line.style.width = `${Math.hypot(dx, dy)}px`;
  line.style.transform = `rotate(${Math.atan2(dy, dx)}rad)`;
  dependencyLayer.append(line);
  return line;
}

function rebuildDependencies() {
  dependencyLayer.replaceChildren();
  const lead = lastAgents.find((agent) => agent.id === "main");
  const leadSeat = seatById.get("main");
  if (!lead || !leadSeat) return;
  if (lead.state === "waiting") {
    for (const agent of lastAgents) {
      if (agent.id !== "main" && agent.state !== "success" && agent.state !== "failure") addLine(seatById.get(agent.id), leadSeat);
    }
  }
  for (const agent of lastAgents) {
    if (agent.id !== "main" && agent.state === "waiting") addLine(leadSeat, seatById.get(agent.id));
  }
}

function deliveryTarget(agent) {
  if (agent.id !== "main") return lastAgents.find((item) => item.id === "main");
  return lastAgents.find((item) => item.id !== "main" && item.state === "waiting") ||
    lastAgents.find((item) => item.id !== "main" && item.state !== "success");
}

function deliver(agent) {
  const target = deliveryTarget(agent);
  const fromSeat = seatById.get(agent.id);
  const toSeat = target && seatById.get(target.id);
  if (!fromSeat || !toSeat) return;
  const courier = fromSeat.querySelector(".mini-agent");
  const from = courier.getBoundingClientRect();
  const to = toSeat.querySelector(".mini-agent").getBoundingClientRect();
  const dx = (to.left + to.width / 2 - from.left - from.width / 2) * .78;
  const dy = (to.top + to.height / 2 - from.top - from.height / 2) * .78;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const route = addLine(fromSeat, toSeat, "handoff");
  courier.classList.add("carrying");
  toSeat.classList.add("receiving");
  announcement.textContent = `${agent.label} completed work and delivered it to ${target.label}.`;

  if (reduced || !courier.animate) {
    window.setTimeout(() => {
      courier.classList.remove("carrying");
      toSeat.classList.remove("receiving");
      if (route) route.remove();
    }, 900);
    return;
  }
  const motion = courier.animate([
    { transform: "translate(0, 0) scale(1)", offset: 0 },
    { transform: `translate(${dx * .25}px, ${dy * .25}px) scale(1.04)`, offset: .16 },
    { transform: `translate(${dx}px, ${dy}px) scale(1.04)`, offset: .42 },
    { transform: `translate(${dx}px, ${dy}px) scale(1.04)`, offset: .58 },
    { transform: `translate(${dx * .25}px, ${dy * .25}px) scale(1.02)`, offset: .84 },
    { transform: "translate(0, 0) scale(1)", offset: 1 }
  ], { duration: 4800, easing: "ease-in-out" });
  motion.onfinish = () => {
    courier.classList.remove("carrying");
    toSeat.classList.remove("receiving");
    if (route) route.remove();
  };
}

function render(state) {
  const agents = Array.isArray(state.agents) ? state.agents : [];
  const history = Array.isArray(state.history) ? state.history : [];
  const signature = JSON.stringify({ id: state.id, title: state.title, project: state.project_label, active: state.active, agents: agents.map(({ id, label, state: status, activity }) => [id, label, status, activity]), history: history.map(({ id, activity }) => [id, activity]) });
  updated.textContent = state.updated_at ? `Updated ${new Date(state.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}` : "No events yet";
  if (signature === lastSignature) return;
  lastSignature = signature;
  lastAgents = agents;
  project.textContent = state.project_label || "Codex task";
  taskTitle.textContent = state.title || state.project_label || "Codex task";
  const lead = agents.find((agent) => agent.id === "main");
  const activity = lead ? lead.activity : (state.active ? "Task active" : "Ready for work");
  taskState.textContent = activity;
  tableActivity.textContent = state.title || activity;
  agentCount.textContent = agents.length ? `${agents.length} agent${agents.length === 1 ? "" : "s"} active` : "Room ready";
  emptyRoom.hidden = agents.length > 0;
  renderActivityList(agents);
  renderHistoryList(history);
  updateAgentInspector();

  const ids = new Set(agents.map((agent) => agent.id));
  removeMissingAgents(ids);
  const deliveries = [];
  for (const agent of agents) {
    const previous = previousStates.get(agent.id);
    updateSeat(agent);
    if (previous && previous !== "success" && agent.state === "success") deliveries.push(agent);
    previousStates.set(agent.id, agent.state);
  }
  announcement.textContent = agents.length ? `${agents.length} agent${agents.length === 1 ? "" : "s"} active. ${activity}.` : "The conference room is ready.";
  window.requestAnimationFrame(() => {
    rebuildDependencies();
    deliveries.forEach((agent, index) => window.setTimeout(() => deliver(agent), index * 350));
  });
}

function setConnection(next) {
  if (connectionState === next) return;
  connectionState = next;
  connectionDot.className = `signal ${next}`;
  connectionText.textContent = next === "online" ? "Live · local" : "Reconnecting";
}

async function refresh() {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error("offline");
    const payload = await response.json();
    lastSessions = Array.isArray(payload.sessions) ? payload.sessions : [];
    if (!selectedSessionId || !lastSessions.some((item) => item.id === selectedSessionId)) {
      const preferred = lastSessions.find((item) => item.active) || lastSessions[0];
      selectedSessionId = preferred ? preferred.id : null;
      resetRoom();
    }
    renderTaskList(lastSessions);
    const selected = lastSessions.find((item) => item.id === selectedSessionId);
    if (selected) {
      render(selected);
    } else {
      project.textContent = "Waiting for a Codex task";
      taskTitle.textContent = "Waiting for a Codex task";
      taskState.textContent = "Ready for work";
      tableActivity.textContent = "Ready for work";
      agentCount.textContent = "Room ready";
      activeTotal.textContent = "0";
      emptyRoom.hidden = false;
      renderActivityList([]);
      renderHistoryList([]);
    }
    setConnection("online");
  } catch {
    setConnection("offline");
  }
}

let resizeTimer;
window.addEventListener("resize", () => {
  window.clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(rebuildDependencies, 120);
});
focusToggle.addEventListener("click", () => {
  const focused = document.body.classList.toggle("focus-mode");
  focusToggle.setAttribute("aria-pressed", String(focused));
  focusToggle.querySelector(".button-label").textContent = focused ? "Team" : "Focus";
  focusToggle.title = focused ? "Show team activity" : "Focus on the room";
  window.requestAnimationFrame(rebuildDependencies);
});
inspectorClose.addEventListener("click", () => agentInspector.close());
agentInspector.addEventListener("click", (event) => {
  if (event.target === agentInspector) agentInspector.close();
});
agentInspector.addEventListener("close", () => { inspectedRecord = null; });
function updateClock() {
  studioClock.textContent = `LIVE · ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}
updateClock();
window.setInterval(updateClock, 1000);
refresh();
setInterval(refresh, 700);
