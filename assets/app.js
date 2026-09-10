"use strict";

const floor = document.getElementById("floor");
const project = document.getElementById("project");
const taskState = document.getElementById("task-state");
const updated = document.getElementById("updated");
const connectionDot = document.getElementById("connection-dot");
const connectionText = document.getElementById("connection-text");

const icons = {
  idle: "☕", thinking: "💭", researching: "📚", coding: "⌨️",
  running: "⚙️", delegating: "📣", waiting: "✋", working: "🛠️",
  success: "✅", failure: "⚠️"
};

const avatars = ["🧑‍💻", "🧑‍🔬", "🕵️", "🧑‍🎨", "🧑‍🚀", "🧙"];

function hash(text) {
  let value = 0;
  for (const char of text) value = ((value << 5) - value + char.charCodeAt(0)) | 0;
  return Math.abs(value);
}

function render(state) {
  project.textContent = state.project_label || "Codex task";
  updated.textContent = state.updated_at ? `Updated ${new Date(state.updated_at).toLocaleTimeString()}` : "No events yet";
  const agents = Array.isArray(state.agents) ? state.agents : [];
  const lead = agents.find((agent) => agent.id === "main");
  taskState.textContent = lead ? lead.activity : (state.active ? "Task active" : "Ready for work");

  if (!agents.length) {
    floor.innerHTML = '<div class="empty"><span class="big">🏗️</span><strong>The workshop is ready</strong><span>Start a Codex task to bring the team in.</span></div>';
    return;
  }

  floor.replaceChildren(...agents.map((agent) => {
    const station = document.createElement("article");
    station.className = `station${agent.id === "main" ? " lead" : ""}`;
    station.dataset.state = agent.state;
    station.setAttribute("aria-label", `${agent.label}: ${agent.activity}`);

    const icon = document.createElement("span");
    icon.className = "state-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = icons[agent.state] || "•";

    const avatar = document.createElement("span");
    avatar.className = "avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = agent.id === "main" ? "🧑‍✈️" : avatars[hash(agent.id) % avatars.length];

    const name = document.createElement("strong");
    name.textContent = agent.id === "main" ? "Lead agent" : agent.label;
    const activity = document.createElement("span");
    activity.className = "activity";
    activity.textContent = agent.activity;
    station.append(icon, avatar, name, activity);
    return station;
  }));
}

async function refresh() {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error("offline");
    render(await response.json());
    connectionDot.className = "online";
    connectionText.textContent = "Live and local";
  } catch {
    connectionDot.className = "offline";
    connectionText.textContent = "Reconnecting";
  }
}

refresh();
setInterval(refresh, 700);
