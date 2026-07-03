const API = "/api/v1";

const RECONNECT_DELAYS_MS = [1500, 3000, 5000];
const MAX_RECONNECT_ATTEMPTS = 3;

const state = {
  sessionId: null,
  pc: null,
  connected: false,
  performing: false,
  metrics: { tokens: 0, audio: 0, frames: 0 },
  statsInterval: null,
  icePollInterval: null,
  lastPrompt: null,
  connectionMode: "new", // 'new' | 'resumed'
  manualDisconnect: false,
  reconnecting: false,
  turnCount: 0,
  catalog: null,
  selectedAvatarId: null,
  selectedRelationshipMode: "friendly",
  appVersion: null,
  heartbeatInterval: null,
  serverMetricsInterval: null,
  webrtcSessions: [],
  companionSessions: [],
  providerStatus: null,
  providerStatusInterval: null,
  bootstrapped: false,
  historyHydratedFor: null,
  bondScore: 0,
  sseMode: false,
  webrtcFailCount: 0,
  workforceLoaded: false,
};

let _fullIdVisible = false;

const els = {
  statusDot: document.getElementById("statusDot"),
  statusText: document.getElementById("statusText"),
  connectBtn: document.getElementById("connectBtn"),
  sseModeBtn: document.getElementById("sseModeBtn"),
  disconnectBtn: document.getElementById("disconnectBtn"),
  sendBtn: document.getElementById("sendBtn"),
  promptInput: document.getElementById("promptInput"),
  avatarVideo: document.getElementById("avatarVideo"),
  sessionLabel: document.getElementById("sessionLabel"),
  connectionLabel: document.getElementById("connectionLabel"),
  transcript: document.getElementById("transcript"),
  log: document.getElementById("log"),
  metricTokens: document.getElementById("metricTokens"),
  metricAudio: document.getElementById("metricAudio"),
  metricFrames: document.getElementById("metricFrames"),
  resumeInput: document.getElementById("resumeInput"),
  resumeBtn: document.getElementById("resumeBtn"),
  refreshSessionsBtn: document.getElementById("refreshSessionsBtn"),
  sessionsSelect: document.getElementById("sessionsSelect"),
  webrtcStats: document.getElementById("webrtcStats"),
  toast: document.getElementById("toast"),
  avatarSelect: document.getElementById("avatarSelect"),
  voiceSelect: document.getElementById("voiceSelect"),
  systemPromptInput: document.getElementById("systemPromptInput"),
  clearHistoryBtn: document.getElementById("clearHistoryBtn"),
  memoryIndicator: document.getElementById("memoryIndicator"),
  bondMeter: document.getElementById("bondMeter"),
  bondFill: document.getElementById("bondFill"),
  bondScoreLabel: document.getElementById("bondScoreLabel"),
  avatarGallery: document.getElementById("avatarGallery"),
  promptPresets: document.getElementById("promptPresets"),
  providerStatus: document.getElementById("providerStatus"),
  persistedSessionsIndicator: document.getElementById("persistedSessionsIndicator"),
  relationshipModes: document.getElementById("relationshipModes"),
  exportBtn: document.getElementById("exportBtn"),
  versionBadge: document.getElementById("versionBadge"),
  serverMetricsPeek: document.getElementById("serverMetricsPeek"),
  refreshMetricsBtn: document.getElementById("refreshMetricsBtn"),
  workforcePanel: document.getElementById("workforcePanel"),
  workforceRoster: document.getElementById("workforceRoster"),
};

const FALLBACK_CATALOG = {
  avatars: [
    { id: "default", label: "Default", emoji: "🙂", accent_color: "#6c8cff" },
    { id: "professional", label: "Professional", emoji: "💼", accent_color: "#4a9eff" },
    { id: "casual", label: "Casual", emoji: "😊", accent_color: "#3dd68c" },
  ],
  voices: [
    { id: "default", label: "Default" },
    { id: "warm", label: "Warm" },
    { id: "bright", label: "Bright" },
  ],
  prompt_presets: [
    {
      id: "friendly",
      label: "Friendly",
      prompt:
        "You are a friendly, helpful AI video companion. Keep replies concise and conversational for spoken dialogue.",
    },
  ],
  relationship_modes: [
    { id: "friendly", label: "Friendly", description: "Warm, approachable companion energy." },
    { id: "flirtatious", label: "Flirtatious", description: "Playful banter with light charm." },
    { id: "romantic", label: "Romantic", description: "Affectionate, emotionally attentive tone." },
    { id: "deep", label: "Deep", description: "Thoughtful, vulnerable conversations." },
  ],
};

const DEFAULT_ICE_SERVERS = [{ urls: "stun:stun.l.google.com:19302" }];

function setStatus(text, live = false, reconnecting = false) {
  els.statusText.textContent = text;
  els.statusDot.classList.toggle("live", live && !reconnecting);
  els.statusDot.classList.toggle("reconnecting", reconnecting);
  const pill = els.statusText ? els.statusText.parentElement : null;
  if (pill) pill.title = text;
}

function updateMemoryIndicator() {
  if (!els.memoryIndicator) return;
  const turns = state.turnCount;
  els.memoryIndicator.textContent = turns > 0 ? `memory on · ${turns} turn${turns === 1 ? "" : "s"}` : "memory on";
  els.memoryIndicator.title = "Server-side conversation memory is enabled";
}

function updateBondMeter(score = state.bondScore) {
  const clamped = Math.max(0, Math.min(100, Number(score) || 0));
  state.bondScore = clamped;
  if (els.bondFill) els.bondFill.style.width = `${clamped}%`;
  if (els.bondScoreLabel) els.bondScoreLabel.textContent = String(clamped);
  if (els.bondMeter) {
    els.bondMeter.title = `Affinity bond ${clamped}/100`;
    els.bondMeter.setAttribute("aria-label", `Bond score ${clamped} out of 100`);
  }
}

function canSendPrompt() {
  return !!state.sessionId && (state.connected || state.sseMode) && !state.performing;
}

function updateSendButtonState() {
  if (els.sendBtn) els.sendBtn.disabled = !canSendPrompt();
}

async function refreshBondScore() {
  if (!state.sessionId) {
    updateBondMeter(0);
    return;
  }
  const config = await fetchCompanionConfig(state.sessionId);
  if (config && typeof config.bond_score === "number") {
    updateBondMeter(config.bond_score);
  }
}

function renderWorkforceRoster(members) {
  if (!els.workforceRoster) return;
  if (!Array.isArray(members) || members.length === 0) {
    els.workforceRoster.textContent = "No team data.";
    return;
  }
  els.workforceRoster.innerHTML = "";
  members.forEach((member) => {
    const row = document.createElement("div");
    row.className = "workforce-member";

    const name = document.createElement("span");
    name.className = "workforce-member-name";
    name.textContent = member.codename || member.id;

    const award = document.createElement("span");
    award.className = "workforce-member-award";
    const gold = Number(member.award_lb_gold) || 0;
    award.textContent = `${gold}lb gold`;

    const tier = document.createElement("span");
    tier.className = "workforce-member-tier";
    tier.textContent = `${member.tier || "team"} · phase ${member.phase_earned ?? "?"}`;

    const skills = document.createElement("span");
    skills.className = "workforce-member-skills";
    skills.textContent = (member.skills || []).join(" · ");

    row.appendChild(name);
    row.appendChild(award);
    row.appendChild(tier);
    row.appendChild(skills);
    els.workforceRoster.appendChild(row);
  });
}

async function loadWorkforceRoster() {
  if (!els.workforceRoster) return;
  try {
    const res = await fetch(`${API}/workforce/roster`);
    if (!res.ok) throw new Error(`roster ${res.status}`);
    const data = await res.json();
    renderWorkforceRoster(data.members || []);
    state.workforceLoaded = true;
  } catch (e) {
    console.warn("Workforce roster fetch failed", e);
    els.workforceRoster.textContent = "Workforce roster unavailable.";
  }
}

async function enterSseMode(reason = "manual") {
  if (state.connected) {
    showToast("Disconnect WebRTC first to use SSE mode", true);
    return;
  }
  if (state.performing) return;

  state.sseMode = true;
  state.manualDisconnect = false;
  state.connectionMode = "new";

  if (!state.sessionId) {
    state.sessionId = crypto.randomUUID();
    setupSessionBadgeCopy(state.sessionId);
  }

  els.connectionLabel.textContent = "sse";
  els.disconnectBtn.disabled = false;
  if (els.clearHistoryBtn) els.clearHistoryBtn.disabled = false;
  if (els.exportBtn) els.exportBtn.disabled = false;
  if (els.connectBtn) els.connectBtn.disabled = false;
  updateSendButtonState();

  await patchCompanionConfig(state.sessionId);
  const config = await fetchCompanionConfig(state.sessionId);
  if (config) applyCompanionConfig(config);
  startHeartbeat();

  const toastMsg =
    reason === "auto"
      ? "WebRTC failed twice — SSE mode (video unavailable, tokens in transcript only)"
      : "SSE mode — video unavailable, tokens stream to transcript only";
  showToast(toastMsg);
  setStatus("SSE mode", true);
  setLog(toastMsg);
  addBubble("system", "SSE mode active. Chat works without WebRTC — video and audio playback unavailable.");

  try {
    localStorage.setItem("prochar_last_session_id", state.sessionId);
  } catch (_) {}
  if (els.resumeInput) els.resumeInput.value = state.sessionId;
}

function getCompanionConfigPayload() {
  return {
    avatar_id: els.avatarSelect?.value || "default",
    voice: els.voiceSelect?.value || "default",
    system_prompt: (els.systemPromptInput?.value || "").trim() || null,
    relationship_mode: state.selectedRelationshipMode || "friendly",
  };
}

function applyCompanionConfig(config) {
  if (!config) return;
  if (config.avatar_id) selectAvatar(config.avatar_id, { patch: false });
  if (els.voiceSelect && config.voice) els.voiceSelect.value = config.voice;
  if (els.systemPromptInput && config.system_prompt != null) {
    els.systemPromptInput.value = config.system_prompt;
    syncPromptPresetHighlight();
  }
  selectRelationshipMode(config.relationship_mode || "friendly", { patch: false });
  if (typeof config.turn_count === "number") {
    state.turnCount = config.turn_count;
    updateMemoryIndicator();
  }
  if (typeof config.bond_score === "number") {
    updateBondMeter(config.bond_score);
  }
}

function selectAvatar(avatarId, options = {}) {
  const { patch = true } = options;
  if (!avatarId) return;
  state.selectedAvatarId = avatarId;
  if (els.avatarSelect) els.avatarSelect.value = avatarId;
  if (els.avatarGallery) {
    els.avatarGallery.querySelectorAll(".avatar-card").forEach((card) => {
      const isSelected = card.dataset.avatarId === avatarId;
      card.classList.toggle("selected", isSelected);
      card.setAttribute("aria-selected", isSelected ? "true" : "false");
      if (isSelected) {
        const accent = card.dataset.accentColor || "#6c8cff";
        card.style.borderColor = accent;
        card.style.boxShadow = `0 0 0 1px ${accent}55`;
      } else {
        card.style.borderColor = "";
        card.style.boxShadow = "";
      }
    });
  }
  if (patch && state.connected && state.sessionId) {
    patchCompanionConfig(state.sessionId);
  }
}

function renderAvatarGallery() {
  if (!els.avatarGallery) return;
  const avatars = state.catalog?.avatars || FALLBACK_CATALOG.avatars;
  els.avatarGallery.innerHTML = "";
  avatars.forEach((avatar) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "avatar-card";
    card.dataset.avatarId = avatar.id;
    card.dataset.accentColor = avatar.accent_color || "#6c8cff";
    card.setAttribute("role", "option");
    card.title = avatar.description || avatar.label;

    const emoji = document.createElement("span");
    emoji.className = "avatar-card-emoji";
    emoji.textContent = avatar.emoji || "🙂";

    const label = document.createElement("span");
    label.className = "avatar-card-label";
    label.textContent = avatar.label || avatar.id;

    card.appendChild(emoji);
    card.appendChild(label);
    card.addEventListener("click", () => selectAvatar(avatar.id));
    els.avatarGallery.appendChild(card);
  });

  if (els.avatarSelect) {
    const current = state.selectedAvatarId || els.avatarSelect.value || avatars[0]?.id;
    els.avatarSelect.innerHTML = "";
    avatars.forEach((avatar) => {
      const opt = document.createElement("option");
      opt.value = avatar.id;
      opt.textContent = avatar.label || avatar.id;
      els.avatarSelect.appendChild(opt);
    });
    selectAvatar(current, { patch: false });
  }
}

function renderVoiceSelect() {
  if (!els.voiceSelect) return;
  const voices = state.catalog?.voices || FALLBACK_CATALOG.voices;
  const previous = els.voiceSelect.value;
  els.voiceSelect.innerHTML = "";
  voices.forEach((voice) => {
    const opt = document.createElement("option");
    opt.value = voice.id;
    opt.textContent = voice.label || voice.id;
    if (voice.description) opt.title = voice.description;
    els.voiceSelect.appendChild(opt);
  });
  if (previous && voices.some((v) => v.id === previous)) {
    els.voiceSelect.value = previous;
  } else if (voices[0]) {
    els.voiceSelect.value = voices[0].id;
  }
}

function syncPromptPresetHighlight() {
  if (!els.promptPresets || !els.systemPromptInput) return;
  const current = (els.systemPromptInput.value || "").trim();
  els.promptPresets.querySelectorAll(".preset-chip").forEach((chip) => {
    const prompt = chip.dataset.prompt || "";
    chip.classList.toggle("active", prompt.trim() === current && current.length > 0);
  });
}

function selectRelationshipMode(modeId, options = {}) {
  const { patch = true } = options;
  if (!modeId) return;
  state.selectedRelationshipMode = modeId;
  if (els.relationshipModes) {
    els.relationshipModes.querySelectorAll(".mode-chip").forEach((chip) => {
      const isSelected = chip.dataset.modeId === modeId;
      chip.classList.toggle("selected", isSelected);
      chip.setAttribute("aria-checked", isSelected ? "true" : "false");
    });
  }
  if (patch && state.connected && state.sessionId) {
    patchCompanionConfig(state.sessionId);
  }
}

function renderRelationshipModes() {
  if (!els.relationshipModes) return;
  const modes = state.catalog?.relationship_modes || FALLBACK_CATALOG.relationship_modes;
  els.relationshipModes.innerHTML = "";
  modes.forEach((mode) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "mode-chip";
    chip.dataset.modeId = mode.id;
    chip.textContent = mode.label || mode.id;
    chip.title = mode.description || mode.label || mode.id;
    chip.setAttribute("role", "radio");
    chip.setAttribute("aria-checked", "false");
    chip.addEventListener("click", () => selectRelationshipMode(mode.id));
    els.relationshipModes.appendChild(chip);
  });
  selectRelationshipMode(state.selectedRelationshipMode || modes[0]?.id || "friendly", {
    patch: false,
  });
}

function renderPromptPresets() {
  if (!els.promptPresets) return;
  const presets = state.catalog?.prompt_presets || FALLBACK_CATALOG.prompt_presets;
  els.promptPresets.innerHTML = "";
  presets.forEach((preset) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "preset-chip";
    chip.textContent = preset.label || preset.id;
    chip.dataset.prompt = preset.prompt || "";
    chip.title = "Apply preset to system prompt";
    chip.addEventListener("click", () => {
      if (!els.systemPromptInput) return;
      els.systemPromptInput.value = preset.prompt || "";
      syncPromptPresetHighlight();
      if (state.connected && state.sessionId) {
        patchCompanionConfig(state.sessionId);
      }
      setLog(`System prompt preset applied: ${preset.label || preset.id}`);
    });
    els.promptPresets.appendChild(chip);
  });
  syncPromptPresetHighlight();
}

async function loadCatalog() {
  try {
    const res = await fetch(`${API}/companion/catalog`);
    if (!res.ok) throw new Error(`catalog ${res.status}`);
    state.catalog = await res.json();
  } catch (e) {
    console.warn("Catalog fetch failed, using fallback", e);
    state.catalog = FALLBACK_CATALOG;
  }
  renderAvatarGallery();
  renderVoiceSelect();
  renderPromptPresets();
  renderRelationshipModes();
}

function providerStatusClass(status) {
  if (status === "ok") return "ok";
  if (status === "degraded") return "degraded";
  if (status === "error") return "error";
  return "unknown";
}

function renderProviderStatus(data) {
  if (!els.providerStatus || !data) return;
  const items = [
    { key: "llm", label: "LLM" },
    { key: "tts", label: "TTS" },
    { key: "video", label: "Vid" },
  ];
  const tooltipLines = [];
  els.providerStatus.innerHTML = "";
  items.forEach((item, index) => {
    if (index > 0) {
      const sep = document.createElement("span");
      sep.className = "provider-sep";
      sep.textContent = "·";
      els.providerStatus.appendChild(sep);
    }
    const row = document.createElement("span");
    row.className = "provider-item";
    row.textContent = item.label;
    const dot = document.createElement("span");
    const info = data[item.key] || {};
    dot.className = `provider-dot ${providerStatusClass(info.status)}`;
    row.appendChild(dot);
    els.providerStatus.appendChild(row);
    tooltipLines.push(
      `${item.label}: ${info.status || "unknown"} (${info.provider || "—"})${info.detail ? ` — ${info.detail}` : ""}`
    );
  });
  els.providerStatus.title = tooltipLines.join("\n");
}

async function refreshProviderStatus() {
  try {
    const res = await fetch(`${API}/providers/status`);
    if (!res.ok) throw new Error(`providers/status ${res.status}`);
    state.providerStatus = await res.json();
    renderProviderStatus(state.providerStatus);
    return;
  } catch (e) {
    console.warn("Provider status fetch failed, falling back to /health", e);
  }
  try {
    const res = await fetch(`${API}/health`);
    if (!res.ok) return;
    const health = await res.json();
    const derived = {
      llm: { status: "ok", provider: health.llm_provider, detail: health.llm_model },
      tts: { status: "ok", provider: health.tts_provider, detail: health.tts_voice },
      video: { status: "ok", provider: health.video_provider, detail: health.video_avatar_id },
    };
    state.providerStatus = derived;
    renderProviderStatus(derived);
  } catch (_) {}
}

function startProviderStatusPolling() {
  if (state.providerStatusInterval) return;
  state.providerStatusInterval = setInterval(() => {
    refreshProviderStatus().catch(() => {});
  }, 60000);
}

async function fetchCompanionSessions() {
  const res = await fetch(`${API}/companion/sessions`);
  if (!res.ok) throw new Error("Failed to list companion sessions");
  const data = await res.json();
  return Array.isArray(data) ? data : data.sessions || [];
}

function updatePersistedSessionsIndicator(count) {
  if (!els.persistedSessionsIndicator) return;
  const label = count === 1 ? "1 saved" : `${count} saved`;
  els.persistedSessionsIndicator.textContent = label;
  els.persistedSessionsIndicator.title =
    count > 0
      ? `${count} persisted companion session${count === 1 ? "" : "s"} (config + history)`
      : "No persisted companion sessions yet";
}

function createHistoryBubble(role, text) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  if (role === "assistant") {
    const content = document.createElement("span");
    content.className = "bubble-content";
    content.textContent = text;
    bubble.appendChild(content);
    bubble.dataset.ended = "true";
  } else {
    bubble.textContent = text;
  }
  return bubble;
}

async function hydrateTranscriptFromHistory(sessionId) {
  if (!sessionId || state.historyHydratedFor === sessionId) return;
  try {
    const res = await fetch(`${API}/companion/${sessionId}/history`);
    if (!res.ok) return;
    const data = await res.json();
    const messages = (data.messages || []).filter(
      (m) => m && (m.role === "user" || m.role === "assistant") && m.content
    );
    if (!messages.length) return;

    const systemBubble = els.transcript.querySelector(".bubble.system");
    const fragment = document.createDocumentFragment();
    messages.forEach((msg) => {
      fragment.appendChild(createHistoryBubble(msg.role, msg.content));
    });

    if (systemBubble) {
      els.transcript.insertBefore(fragment, systemBubble);
    } else {
      els.transcript.appendChild(fragment);
    }
    els.transcript.scrollTop = els.transcript.scrollHeight;

    if (typeof data.turn_count === "number") {
      state.turnCount = data.turn_count;
      updateMemoryIndicator();
    }
    state.historyHydratedFor = sessionId;
    setLog(`Restored ${messages.length} message(s) from session history.`);
  } catch (e) {
    console.warn("History hydration failed", e);
  }
}

function sessionExistsForResume(sessionId) {
  if (!sessionId) return false;
  const inWebRTC = (state.webrtcSessions || []).includes(sessionId);
  const inCompanion = (state.companionSessions || []).some(
    (s) => (typeof s === "string" ? s : s.id) === sessionId
  );
  return inWebRTC || inCompanion;
}

async function attemptAutoResumeOnLoad() {
  let last = null;
  try {
    last = localStorage.getItem("prochar_last_session_id");
  } catch (_) {}
  if (!last || !sessionExistsForResume(last)) return false;

  try {
    await connect(last, { autoResumeOnLoad: true });
    if (state.connected) {
      await hydrateTranscriptFromHistory(last);
    }
    return state.connected;
  } catch (e) {
    console.warn("Auto-resume on load failed", e);
    return false;
  }
}

async function fetchCompanionConfig(sessionId) {
  if (!sessionId) return null;
  try {
    const res = await fetch(`${API}/companion/${sessionId}/config`);
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    console.warn("Failed to fetch companion config", e);
    return null;
  }
}

async function patchCompanionConfig(sessionId) {
  if (!sessionId) return;
  try {
    const res = await fetch(`${API}/companion/${sessionId}/config`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(getCompanionConfigPayload()),
    });
    if (!res.ok) {
      console.warn("Companion config PATCH failed", res.status);
      return;
    }
    const data = await res.json();
    applyCompanionConfig(data);
  } catch (e) {
    console.warn("Companion config PATCH error", e);
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForConnectionState(timeoutMs = 12000) {
  if (state.connected) return true;
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (state.connected) return true;
    if (state.manualDisconnect) return false;
    if (!state.pc || ["failed", "closed"].includes(state.pc.connectionState)) return false;
    await sleep(200);
  }
  return state.connected;
}

function setLog(message) {
  els.log.textContent = message;
}

function updateVersionBadge(version) {
  if (!els.versionBadge) return;
  const label = version ? `v${version}` : "v—";
  els.versionBadge.textContent = label;
  els.versionBadge.title = version ? `API version ${version}` : "API version unknown";
}

function formatUptime(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  if (total < 60) return `${total}s`;
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  if (mins < 60) return `${mins}m ${secs}s`;
  const hours = Math.floor(mins / 60);
  const remMins = mins % 60;
  return `${hours}h ${remMins}m`;
}

function renderServerMetricsPeek(data) {
  if (!els.serverMetricsPeek || !data) return;
  const performs = data.perform_requests ?? data.perform_count ?? 0;
  const uptime = formatUptime(data.uptime_seconds);
  els.serverMetricsPeek.textContent = `server · ${performs} perform${performs === 1 ? "" : "s"} · up ${uptime}`;
  els.serverMetricsPeek.title = `Server metrics — ${performs} perform(s), uptime ${uptime}`;
}

async function refreshServerMetrics({ quiet = false } = {}) {
  try {
    const res = await fetch(`${API}/metrics`);
    if (!res.ok) throw new Error(`metrics ${res.status}`);
    const data = await res.json();
    renderServerMetricsPeek(data);
    if (!quiet) {
      const performs = data.perform_requests ?? data.perform_count ?? 0;
      setLog(`Server metrics refreshed — ${performs} perform(s), up ${formatUptime(data.uptime_seconds)}`);
    }
    return data;
  } catch (e) {
    if (els.serverMetricsPeek) {
      els.serverMetricsPeek.textContent = "server metrics unavailable";
      els.serverMetricsPeek.title = "Could not fetch /metrics";
    }
    if (!quiet) setLog("Server metrics unavailable.");
    console.warn("Metrics fetch failed", e);
    return null;
  }
}

function startServerMetricsPolling() {
  if (state.serverMetricsInterval) return;
  refreshServerMetrics({ quiet: true }).catch(() => {});
  state.serverMetricsInterval = setInterval(() => {
    refreshServerMetrics({ quiet: true }).catch(() => {});
  }, 120000);
}

function stopServerMetricsPolling() {
  if (state.serverMetricsInterval) {
    clearInterval(state.serverMetricsInterval);
    state.serverMetricsInterval = null;
  }
}

async function sendHeartbeat() {
  if (!state.sessionId || (!state.connected && !state.sseMode)) return;
  try {
    const res = await fetch(`${API}/companion/${state.sessionId}/heartbeat`, { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      if (typeof data.bond_score === "number") updateBondMeter(data.bond_score);
      if (typeof data.turn_count === "number") {
        state.turnCount = data.turn_count;
        updateMemoryIndicator();
      }
    }
  } catch (e) {
    console.warn("Heartbeat failed", e);
  }
}

function startHeartbeat() {
  stopHeartbeat();
  if (!state.sessionId || (!state.connected && !state.sseMode)) return;
  sendHeartbeat().catch(() => {});
  state.heartbeatInterval = setInterval(() => {
    sendHeartbeat().catch(() => {});
  }, 45000);
}

function stopHeartbeat() {
  if (state.heartbeatInterval) {
    clearInterval(state.heartbeatInterval);
    state.heartbeatInterval = null;
  }
}

function exportConversation(format = "txt") {
  if (!state.sessionId) {
    showToast("Connect to export conversation", true);
    return;
  }
  const url = `${API}/companion/${state.sessionId}/export?format=${encodeURIComponent(format)}`;
  if (format === "json") {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `companion-${state.sessionId.slice(0, 8)}.json`;
    anchor.rel = "noopener";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setLog("Conversation export started (JSON download).");
    showToast("Downloading JSON export");
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer");
  setLog("Conversation export opened in new tab (txt).");
  showToast("Export opened in new tab");
}

function updateMetrics() {
  els.metricTokens.textContent = String(state.metrics.tokens);
  els.metricAudio.textContent = String(state.metrics.audio);
  els.metricFrames.textContent = String(state.metrics.frames);
}

function addBubble(role, text) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  if (role === "assistant") {
    const content = document.createElement("span");
    content.className = "bubble-content";
    content.textContent = text;
    bubble.appendChild(content);
    const indicator = document.createElement("span");
    indicator.className = "speaking-indicator";
    indicator.textContent = "●";
    bubble.appendChild(indicator);
    bubble.dataset.ended = "false";
  } else {
    bubble.textContent = text;
  }
  els.transcript.appendChild(bubble);
  els.transcript.scrollTop = els.transcript.scrollHeight;
  return bubble;
}

function showToast(message, isError = false) {
  const t = els.toast || document.getElementById("toast");
  if (!t) {
    console.log("TOAST:", message);
    return;
  }
  t.textContent = message;
  t.className = `toast ${isError ? "error" : ""}`;
  t.classList.remove("hidden");
  // auto hide
  clearTimeout(t._hideTimer);
  t._hideTimer = setTimeout(() => {
    if (t) t.classList.add("hidden");
  }, 2600);
}

function updateSessionLabel(id) {
  if (!id) {
    els.sessionLabel.textContent = "—";
    els.sessionLabel.title = "";
    return;
  }
  els.sessionLabel.textContent = id.slice(0, 8);
  els.sessionLabel.title = id + " (click to copy / toggle)";
  els.sessionLabel.style.cursor = "pointer";
}

function setupSessionBadgeCopy(sessionId) {
  updateSessionLabel(sessionId);
  const badge = document.getElementById("sessionBadge") || els.sessionLabel;
  const handler = () => {
    if (!sessionId) return;
    navigator.clipboard
      .writeText(sessionId)
      .then(() => {
        const wasFull = _fullIdVisible;
        showToast("Session ID copied");
        if (els.resumeInput) els.resumeInput.value = sessionId;
        // toggle full/short for "always visible full ID option"
        _fullIdVisible = !wasFull;
        if (_fullIdVisible) {
          els.sessionLabel.textContent = sessionId;
          els.sessionLabel.style.fontSize = "0.65rem";
          els.sessionLabel.title = "Full ID visible — click to shorten";
        } else {
          els.sessionLabel.textContent = sessionId.slice(0, 8);
          els.sessionLabel.style.fontSize = "";
          els.sessionLabel.title = sessionId + " (click to copy / toggle)";
        }
        setTimeout(() => {
          if (!_fullIdVisible && els.sessionLabel && state.sessionId === sessionId) {
            els.sessionLabel.textContent = sessionId.slice(0, 8);
            els.sessionLabel.style.fontSize = "";
          }
        }, 1400);
      })
      .catch(() => {
        if (els.resumeInput) els.resumeInput.value = sessionId;
        setLog("Session ID: " + sessionId);
        showToast("Session ID: " + sessionId);
      });
  };
  // remove old if any, attach fresh
  els.sessionLabel.onclick = handler;
  if (badge && badge !== els.sessionLabel) badge.onclick = handler;
}

const DEFAULT_SYSTEM_BUBBLE =
  "Connect to start — or reload to auto-resume your last session. Pick an avatar, voice, and prompt preset below.";

function resetTranscript() {
  els.transcript.innerHTML = "";
  addBubble("system", DEFAULT_SYSTEM_BUBBLE);
}

function clearTranscriptKeepSystem() {
  const systemBubble = els.transcript.querySelector(".bubble.system");
  els.transcript.innerHTML = "";
  if (systemBubble) {
    els.transcript.appendChild(systemBubble);
  } else {
    addBubble("system", DEFAULT_SYSTEM_BUBBLE);
  }
}

async function waitForIceGathering(pc) {
  if (pc.iceGatheringState === "complete") return;
  await new Promise((resolve) => {
    const check = () => {
      if (pc.iceGatheringState === "complete") {
        pc.removeEventListener("icegatheringstatechange", check);
        resolve();
      }
    };
    pc.addEventListener("icegatheringstatechange", check);
    setTimeout(resolve, 2500);
  });
}

async function postIceCandidate(candidate) {
  if (!state.sessionId || !candidate) return;
  await fetch(`${API}/webrtc/ice-candidate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: state.sessionId,
      candidate: candidate.candidate,
      sdp_mid: candidate.sdpMid,
      sdp_mline_index: candidate.sdpMLineIndex,
    }),
  });
}

function stopIceCandidatePolling() {
  if (state.icePollInterval) {
    clearInterval(state.icePollInterval);
    state.icePollInterval = null;
  }
}

function startIceCandidatePolling() {
  stopIceCandidatePolling();
  if (!state.sessionId || !state.pc) return;
  // Immediate first fetch (server candidates may be ready or arrive soon after answer)
  fetchAndAddServerCandidatesOnce().catch(() => {});
  state.icePollInterval = setInterval(() => {
    if (!state.sessionId || !state.pc || ["closed", "failed"].includes(state.pc.connectionState)) {
      stopIceCandidatePolling();
      return;
    }
    fetchAndAddServerCandidatesOnce().catch(() => {});
  }, 300);
}

async function fetchAndAddServerCandidatesOnce() {
  if (!state.sessionId || !state.pc) return;
  try {
    const res = await fetch(`${API}/webrtc/ice-candidates/${state.sessionId}`);
    if (!res.ok) return;
    const data = await res.json();
    const cands = (data && data.candidates) || [];
    for (const c of cands) {
      if (c && c.candidate) {
        try {
          await state.pc.addIceCandidate(new RTCIceCandidate({
            candidate: c.candidate,
            sdpMid: c.sdp_mid ?? null,
            sdpMLineIndex: c.sdp_mline_index ?? null,
          }));
        } catch (e) {
          // Harmless: duplicate candidate or timing (already connected, etc.)
        }
      }
    }
  } catch (e) {
    // non-fatal network / parse during trickle polling
  }
}

async function connect(resumeSessionId = null, options = {}) {
  const { autoReconnect = false, autoResumeOnLoad = false } = options;
  if (state.connected || (state.reconnecting && !autoReconnect)) return;

  const isResume = !!resumeSessionId;
  if (!autoReconnect) state.manualDisconnect = false;
  state.sseMode = false;
  state.connectionMode = isResume ? "resumed" : "new";
  if (autoResumeOnLoad) {
    showToast("Restoring session…");
  }
  setStatus(
    autoReconnect ? "Reconnecting…" : isResume ? "Resuming…" : "Connecting…",
    false,
    autoReconnect
  );
  setLog(
    isResume
      ? `Resuming session ${resumeSessionId.slice(0, 8)}…`
      : "Creating WebRTC session…"
  );
  els.connectBtn.disabled = true;
  if (els.resumeBtn) els.resumeBtn.disabled = true;
  if (els.sessionsSelect) els.sessionsSelect.disabled = true;

  try {
    let iceServers = DEFAULT_ICE_SERVERS;
    let targetSessionId = resumeSessionId;

    if (!isResume) {
      const sessionRes = await fetch(`${API}/webrtc/session`, { method: "POST" });
      if (!sessionRes.ok) throw new Error("Failed to create session.");
      const session = await sessionRes.json();
      targetSessionId = session.session_id;
      iceServers = session.ice_servers || DEFAULT_ICE_SERVERS;
    }

    state.sessionId = targetSessionId;
    setupSessionBadgeCopy(state.sessionId);

    const pc = new RTCPeerConnection({ iceServers });
    state.pc = pc;

    const remoteStream = new MediaStream();
    els.avatarVideo.srcObject = remoteStream;

    pc.addTransceiver("video", { direction: "recvonly" });
    pc.addTransceiver("audio", { direction: "recvonly" });

    pc.ontrack = (event) => {
      event.streams[0]?.getTracks().forEach((track) => {
        if (!remoteStream.getTracks().some((t) => t.id === track.id)) {
          remoteStream.addTrack(track);
        }
      });
      els.avatarVideo.play().catch(() => {});
      setLog(`Receiving ${event.track.kind} track.`);
    };

    pc.onconnectionstatechange = () => {
      els.connectionLabel.textContent = pc.connectionState;
      if (pc.connectionState === "connected") {
        state.connected = true;
        state.reconnecting = false;
        state.webrtcFailCount = 0;
        state.sseMode = false;
        const statusText = state.connectionMode === "resumed" ? "Resumed" : "Connected";
        setStatus(statusText, true);
        setLog(
          state.connectionMode === "resumed"
            ? "WebRTC resumed. Send a prompt to perform."
            : "WebRTC connected. Send a prompt to perform."
        );
        startStatsPolling();
        startHeartbeat();
        try {
          localStorage.setItem("prochar_last_session_id", state.sessionId);
        } catch (_) {}
        if (els.resumeInput) els.resumeInput.value = state.sessionId;
        if (els.clearHistoryBtn) els.clearHistoryBtn.disabled = false;
        if (els.exportBtn) els.exportBtn.disabled = false;
      } else if (pc.connectionState === "disconnected") {
        const wasPerforming = state.performing;
        state.connected = false;
        stopStatsPolling();
        stopHeartbeat();
        if (!state.manualDisconnect && state.sessionId && !state.reconnecting) {
          attemptAutoReconnect(wasPerforming).catch((err) => {
            console.error("Auto-reconnect failed", err);
          });
        } else {
          setStatus("Disconnected");
          if (wasPerforming) {
            setLog("Connection lost during stream. Last partial response kept.");
            showToast("Disconnected during stream", true);
          }
        }
      } else if (["failed", "closed"].includes(pc.connectionState)) {
        const wasPerforming = state.performing;
        state.connected = false;
        setStatus("Disconnected");
        if (wasPerforming) {
          setLog("Connection lost during stream. Last partial response kept.");
          showToast("Disconnected during stream", true);
        }
        stopStatsPolling();
        stopHeartbeat();
      }
    };

    pc.onicecandidate = (event) => {
      if (event.candidate) {
        postIceCandidate(event.candidate).catch((err) => {
          console.warn("ICE post failed", err);
        });
      }
    };

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    await waitForIceGathering(pc);

    const offerRes = await fetch(`${API}/webrtc/offer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: state.sessionId,
        type: "offer",
        sdp: pc.localDescription.sdp,
      }),
    });

    if (!offerRes.ok) {
      let detail = "SDP offer exchange failed.";
      try {
        const errBody = await offerRes.json();
        if (errBody && errBody.detail) detail = errBody.detail;
      } catch (_) {}
      throw new Error(detail);
    }

    const answer = await offerRes.json();

    // Graceful "session not found" handling for resume:
    const returnedId = answer.session_id || state.sessionId;
    const wasNotFoundOnResume = isResume && resumeSessionId && returnedId !== resumeSessionId;
    if (returnedId !== state.sessionId) {
      state.sessionId = returnedId;
      setupSessionBadgeCopy(state.sessionId);
      if (els.resumeInput) els.resumeInput.value = state.sessionId;
    }

    await pc.setRemoteDescription({ type: "answer", sdp: answer.sdp });
    els.avatarVideo.muted = false;

    // Start polling for server ICE candidates (full trickle support). One-shot insufficient because
    // server candidates are emitted asynchronously after setLocalDescription on server PC.
    startIceCandidatePolling();

    els.disconnectBtn.disabled = false;
    els.sendBtn.disabled = false;
    if (els.resumeBtn) els.resumeBtn.disabled = true;
    if (els.sessionsSelect) els.sessionsSelect.disabled = false;
    if (els.clearHistoryBtn) els.clearHistoryBtn.disabled = false;

    if (isResume) {
      const config = await fetchCompanionConfig(state.sessionId);
      if (config) applyCompanionConfig(config);
      if (!autoResumeOnLoad) {
        await hydrateTranscriptFromHistory(state.sessionId);
      }
    }
    await patchCompanionConfig(state.sessionId);

    if (wasNotFoundOnResume) {
      state.connectionMode = "new";
      showToast(`Session ${resumeSessionId.slice(0, 8)} not found — started new`, true);
      setLog(`Session not found (graceful fallback). New ID: ${state.sessionId.slice(0, 8)}`);
      addBubble("system", "Session not found on resume — created a fresh session instead.");
    } else if (isResume) {
      addBubble("system", "Session resumed.");
    } else {
      addBubble("system", "Session ready. Avatar tracks attached.");
    }
    setLog(
      "WebRTC signaling complete. Copy badge ID for reload resume. " +
        (state.connectionMode === "resumed" ? "Resumed successfully." : "")
    );
  } catch (error) {
    console.error(error);
    const msg = error.message || "Connection failed.";
    const isNotFound = /not found|unknown.*session|404/i.test(msg);
    if (autoReconnect) {
      teardownConnection({ clearSession: false });
      throw error;
    }
    await teardownConnection({ clearSession: true });
    state.webrtcFailCount += 1;
    if (state.webrtcFailCount >= 2) {
      await enterSseMode("auto");
      return;
    }
    setStatus(isNotFound ? "Not found" : "Error");
    setLog(msg);
    showToast(msg, true);
    if (isNotFound && resumeSessionId) {
      if (els.resumeInput) els.resumeInput.value = "";
      setLog("Session not found. Use ↻ to list or click Connect to start fresh.");
      showToast("Session not found — pick from active list or Connect new", true);
    }
    els.connectBtn.disabled = false;
    if (els.resumeBtn) els.resumeBtn.disabled = !!(els.resumeInput && els.resumeInput.value.trim());
    if (els.sessionsSelect) els.sessionsSelect.disabled = false;
  }
}

async function attemptAutoReconnect(wasPerforming = false) {
  const savedSessionId = state.sessionId;
  if (!savedSessionId || state.manualDisconnect || state.reconnecting) return;

  state.reconnecting = true;
  setStatus("Reconnecting…", false, true);
  setLog("Connection dropped — attempting auto-resume…");
  if (wasPerforming) {
    showToast("Connection lost — reconnecting…", true);
  }

  teardownConnection({ clearSession: false });

  for (let attempt = 0; attempt < MAX_RECONNECT_ATTEMPTS; attempt++) {
    if (state.manualDisconnect) break;
    if (attempt > 0) {
      const delay = RECONNECT_DELAYS_MS[attempt - 1] ?? 5000;
      setLog(`Reconnecting… attempt ${attempt + 1}/${MAX_RECONNECT_ATTEMPTS} (wait ${delay / 1000}s)`);
      await sleep(delay);
    } else {
      setLog(`Reconnecting… attempt 1/${MAX_RECONNECT_ATTEMPTS}`);
    }

    try {
      await connect(savedSessionId, { autoReconnect: true });
      const reconnected = await waitForConnectionState();
      if (reconnected && state.connected) {
        state.reconnecting = false;
        setStatus(state.connectionMode === "resumed" ? "Resumed" : "Connected", true);
        setLog("Auto-reconnected successfully.");
        showToast("Reconnected");
        addBubble("system", "Connection restored.");
        return;
      }
    } catch (e) {
      console.warn(`Reconnect attempt ${attempt + 1} failed`, e);
    }
  }

  state.reconnecting = false;
  state.sessionId = savedSessionId;
  setupSessionBadgeCopy(savedSessionId);
  if (els.resumeInput) els.resumeInput.value = savedSessionId;
  setStatus("Disconnected");
  setLog("Auto-reconnect failed after 3 attempts. Use Resume or Connect.");
  showToast("Could not reconnect — try Resume", true);
  els.connectBtn.disabled = false;
  if (els.resumeBtn) els.resumeBtn.disabled = false;
  if (els.sessionsSelect) els.sessionsSelect.disabled = false;
}

function teardownConnection({ clearSession = true } = {}) {
  els.disconnectBtn.disabled = true;
  els.sendBtn.disabled = true;
  if (els.clearHistoryBtn && clearSession) els.clearHistoryBtn.disabled = true;
  if (els.exportBtn && clearSession) els.exportBtn.disabled = true;

  stopStatsPolling();
  stopIceCandidatePolling();
  stopHeartbeat();

  if (state.pc) {
    state.pc.getSenders().forEach((sender) => sender.track?.stop());
    state.pc.close();
  }

  state.pc = null;
  if (clearSession) {
    state.sessionId = null;
    els.avatarVideo.srcObject = null;
    els.sessionLabel.textContent = "—";
    els.sessionLabel.title = "";
    els.sessionLabel.style.cursor = "";
    els.sessionLabel.onclick = null;
    _fullIdVisible = false;
    state.turnCount = 0;
    state.historyHydratedFor = null;
    state.sseMode = false;
    state.bondScore = 0;
    updateMemoryIndicator();
    updateBondMeter(0);
  }
  state.connected = false;
  state.performing = false;
  if (clearSession) state.connectionMode = "new";
  state.icePollInterval = null;
  state.metrics = { tokens: 0, audio: 0, frames: 0 };
  updateMetrics();
  if (els.webrtcStats) els.webrtcStats.textContent = "WebRTC: —";
  if (clearSession) {
    els.connectionLabel.textContent = "idle";
  }
}

async function disconnect() {
  state.manualDisconnect = true;
  state.reconnecting = false;
  state.sseMode = false;
  state.webrtcFailCount = 0;

  if (state.sessionId) {
    // Leave the server session alive so it can be resumed (paste the ID shown in the badge).
    console.debug("Leaving session alive for potential resume:", state.sessionId);
  }

  teardownConnection({ clearSession: true });

  els.connectBtn.disabled = false;
  setStatus("Idle");
  setLog("Disconnected. (server session may still be resumable)");
  if (els.resumeBtn) els.resumeBtn.disabled = !(els.resumeInput && els.resumeInput.value.trim());
  if (els.sessionsSelect) els.sessionsSelect.disabled = false;
}

async function clearHistory() {
  if (!state.sessionId) return;
  els.clearHistoryBtn.disabled = true;
  try {
    const res = await fetch(`${API}/companion/${state.sessionId}/history`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error(`Clear history failed (${res.status})`);
    state.turnCount = 0;
    updateMemoryIndicator();
    updateBondMeter(0);
    clearTranscriptKeepSystem();
    addBubble("system", "Conversation history cleared.");
    setLog("Server history cleared.");
    showToast("History cleared");
  } catch (e) {
    console.error(e);
    setLog(e.message || "Could not clear history.");
    showToast(e.message || "Could not clear history", true);
  } finally {
    if ((state.connected || state.sseMode) && els.clearHistoryBtn) els.clearHistoryBtn.disabled = false;
  }
}

async function perform(prompt) {
  if (!state.sessionId || state.performing) return;

  state.performing = true;
  state.lastPrompt = prompt;
  state.metrics = { tokens: 0, audio: 0, frames: 0 };
  updateMetrics();
  els.sendBtn.disabled = true;
  setStatus("Streaming…", true);
  addBubble("user", prompt);
  state.turnCount += 1;
  updateMemoryIndicator();

  const assistantBubble = addBubble("assistant", "");
  const contentEl = assistantBubble.querySelector(".bubble-content") || assistantBubble;
  let assistantText = "";
  let hadError = false;

  try {
    const response = await fetch(`${API}/chat/perform`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: state.sessionId,
        messages: [{ role: "user", content: prompt }],
        use_memory: true,
      }),
    });

    if (!response.ok || !response.body) {
      const msg = `Perform request failed (status ${response.status}).`;
      throw new Error(msg);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";

      for (const chunk of chunks) {
        const line = chunk
          .split("\n")
          .find((entry) => entry.startsWith("data:"));
        if (!line) continue;

        let event;
        try {
          event = JSON.parse(line.slice(5).trim());
        } catch (_) {
          continue;
        }

        if (event.type === "token") {
          assistantText += event.content;
          contentEl.textContent = assistantText;
          state.metrics.tokens += 1;
        } else if (event.type === "audio") {
          state.metrics.audio += 1;
        } else if (event.type === "video_frame") {
          state.metrics.frames += 1;
        } else if (event.type === "error" || event.type === "tts_error" || event.type === "video_error") {
          hadError = true;
          setLog(event.message || "Stream error");
          showToast("Stream error: " + (event.message || ""), true);
          // keep partial text
        } else if (event.type === "done" || event.type === "tts_done" || event.type === "video_done") {
          // stream lifecycle
          const endMsg = event.type === "done" ? "LLM stream complete." : "Stream ended.";
          setLog(endMsg);
          assistantBubble.dataset.ended = "true";
          // remove speaking indicator if still there
          const ind = assistantBubble.querySelector(".speaking-indicator");
          if (ind) ind.remove();
          // briefly show ended state then back to normal
          setTimeout(() => {
            if (state.performing) return;
            if (state.connected) {
              setStatus(state.connectionMode === "resumed" ? "Resumed" : "Connected", true);
            } else if (state.sseMode) {
              setStatus("SSE mode", true);
            }
          }, 1600);
        }
        updateMetrics();
      }

      els.transcript.scrollTop = els.transcript.scrollHeight;
    }

    if (!hadError) {
      assistantBubble.dataset.ended = "true";
      const ind = assistantBubble.querySelector(".speaking-indicator");
      if (ind) ind.remove();
      setLog("Perform stream complete.");
    }
  } catch (error) {
    console.error(error);
    hadError = true;
    contentEl.textContent = assistantText || "(no response)";
    setLog(error.message || "Perform failed.");
    showToast(error.message || "Perform failed.", true);
    // show last prompt hint for retry
    if (state.lastPrompt) {
      setTimeout(() => {
        if (els.log && !els.log.textContent.includes("Retry")) {
          els.log.textContent += " — use example buttons or re-send.";
        }
      }, 50);
    }
  } finally {
    state.performing = false;
    await refreshBondScore();
    updateSendButtonState();
    if (!hadError) {
      if (state.connected) {
        setStatus(state.connectionMode === "resumed" ? "Resumed" : "Connected", true);
      } else if (state.sseMode) {
        setStatus("SSE mode", true);
      }
    }
  }
}

// --- WebRTC live stats (better video/audio stats during connection) ---
let _prevStats = { v: 0, a: 0, t: Date.now() };

async function updateWebRTCStats() {
  if (!state.pc || !state.connected || !els.webrtcStats) return;
  try {
    const stats = await state.pc.getStats();
    let vBytes = 0,
      aBytes = 0,
      vLost = 0,
      aLost = 0,
      frames = 0,
      jitter = 0;
    stats.forEach((r) => {
      if (r.type === "inbound-rtp" && r.kind) {
        if (r.kind === "video") {
          vBytes = r.bytesReceived || 0;
          vLost = r.packetsLost || 0;
          frames = r.framesDecoded || 0;
        } else if (r.kind === "audio") {
          aBytes = r.bytesReceived || 0;
          aLost = r.packetsLost || 0;
          jitter = r.jitter || 0;
        }
      }
    });
    const now = Date.now();
    const dt = Math.max(0.5, (now - _prevStats.t) / 1000);
    const vKbps = Math.round(((vBytes - _prevStats.v) * 8) / 1024 / dt);
    const aKbps = Math.round(((aBytes - _prevStats.a) * 8) / 1024 / dt);
    _prevStats = { v: vBytes, a: aBytes, t: now };

    els.webrtcStats.textContent = `WebRTC live — v:${vKbps}kbps f:${frames} lost:${vLost} | a:${aKbps}kbps j:${jitter.toFixed(3)} lost:${aLost}`;
  } catch (e) {
    // ignore transient getStats errors
  }
}

function startStatsPolling() {
  stopStatsPolling();
  _prevStats = { v: 0, a: 0, t: Date.now() };
  state.statsInterval = setInterval(() => {
    updateWebRTCStats();
  }, 1400);
}

function stopStatsPolling() {
  if (state.statsInterval) {
    clearInterval(state.statsInterval);
    state.statsInterval = null;
  }
  if (els.webrtcStats) els.webrtcStats.textContent = "WebRTC: —";
}

// --- example prompts (small polish) ---
function wireExamplePrompts() {
  const exBtns = document.querySelectorAll(".ex-btn");
  exBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const p = btn.getAttribute("data-prompt") || btn.textContent;
      if (!p) return;
      if (canSendPrompt()) {
        perform(p);
      } else {
        els.promptInput.value = p;
        els.promptInput.focus();
        setLog("Connect, resume, or use SSE mode first, then send (or click example again after).");
      }
    });
  });
}

els.connectBtn.addEventListener("click", () => connect());
if (els.sseModeBtn) {
  els.sseModeBtn.addEventListener("click", () => enterSseMode("manual"));
}
if (els.workforcePanel) {
  els.workforcePanel.addEventListener("toggle", () => {
    if (els.workforcePanel.open) loadWorkforceRoster().catch(() => {});
  });
}

async function fetchActiveSessions() {
  const res = await fetch(`${API}/webrtc/sessions`);
  if (!res.ok) throw new Error("Failed to list sessions");
  return await res.json();
}

function formatSessionOptionLabel(id, { active = false, turns = null } = {}) {
  const short = `${id.slice(0, 8)}…${id.slice(-4)}`;
  const tags = [];
  if (active) tags.push("live");
  if (typeof turns === "number" && turns > 0) tags.push(`${turns}t`);
  return tags.length ? `${short} (${tags.join(", ")})` : short;
}

async function refreshActiveSessions() {
  let webrtcData = { sessions: [], count: 0, details: [] };
  let companionData = [];
  try {
    [webrtcData, companionData] = await Promise.all([
      fetchActiveSessions(),
      fetchCompanionSessions().catch(() => []),
    ]);
  } catch (e) {
    setLog("Could not fetch active sessions.");
    if (els.sessionsSelect) els.sessionsSelect.disabled = true;
    return;
  }

  state.webrtcSessions = webrtcData.sessions || [];
  state.companionSessions = companionData;
  updatePersistedSessionsIndicator(companionData.length);

  const activeSet = new Set(state.webrtcSessions);
  const companionById = new Map();
  companionData.forEach((item) => {
    const id = typeof item === "string" ? item : item.id;
    if (id) companionById.set(id, item);
  });

  const mergedIds = [...state.webrtcSessions];
  companionData.forEach((item) => {
    const id = typeof item === "string" ? item : item.id;
    if (id && !mergedIds.includes(id)) mergedIds.push(id);
  });

  const list = state.webrtcSessions.map((s) => s.slice(0, 8)).join(", ") || "none";
  let detailStr = "";
  if (Array.isArray(webrtcData.details) && webrtcData.details.length) {
    detailStr =
      " · states:" +
      webrtcData.details
        .slice(0, 2)
        .map(
          (d) =>
            `${String(d.session_id || "").slice(0, 4)}:${d.connection_state || d.ice_connection_state || "?"}`
        )
        .join(",");
  }
  const persistedNote =
    companionData.length > 0 ? ` · ${companionData.length} persisted` : "";
  setLog(`Active sessions (${webrtcData.count || 0}): ${list}${detailStr}${persistedNote}`);

  if (els.sessionsSelect) {
    els.sessionsSelect.innerHTML = '<option value="">— sessions —</option>';
    mergedIds.forEach((id) => {
      const opt = document.createElement("option");
      opt.value = id;
      const summary = companionById.get(id);
      opt.textContent = formatSessionOptionLabel(id, {
        active: activeSet.has(id),
        turns: summary?.turn_count,
      });
      els.sessionsSelect.appendChild(opt);
    });
    els.sessionsSelect.disabled = mergedIds.length === 0;
  }

  const lastStored = (() => {
    try {
      return localStorage.getItem("prochar_last_session_id");
    } catch (_) {
      return null;
    }
  })();
  if (els.resumeInput) {
    if (lastStored && sessionExistsForResume(lastStored)) {
      els.resumeInput.value = lastStored;
      setLog(
        `Sessions ready — last session resumable (${lastStored.slice(0, 8)}). ` +
          `${webrtcData.count || 0} live, ${companionData.length} persisted.`
      );
    } else if (!els.resumeInput.value && mergedIds.length) {
      els.resumeInput.value = mergedIds[0];
    }
  }
  if (els.resumeBtn) {
    els.resumeBtn.disabled = !(els.resumeInput && els.resumeInput.value.trim());
  }
}

if (els.refreshSessionsBtn) {
  els.refreshSessionsBtn.addEventListener("click", () => {
    refreshActiveSessions();
    refreshServerMetrics({ quiet: true }).catch(() => {});
  });
}
if (els.refreshMetricsBtn) {
  els.refreshMetricsBtn.addEventListener("click", () => {
    refreshServerMetrics().catch(() => {});
  });
}
if (els.exportBtn) {
  els.exportBtn.addEventListener("click", (event) => {
    const format = event.shiftKey ? "json" : "txt";
    exportConversation(format);
  });
  els.exportBtn.title = "Export conversation (txt in new tab; Shift+click for JSON download)";
}
if (els.sessionsSelect) {
  els.sessionsSelect.addEventListener("change", () => {
    const val = els.sessionsSelect.value;
    if (val && els.resumeInput) {
      els.resumeInput.value = val;
      if (els.resumeBtn) els.resumeBtn.disabled = false;
      setLog("Session selected from active list. Click Resume.");
    }
  });
}
if (els.resumeBtn) {
  els.resumeBtn.addEventListener("click", () => {
    const id = (els.resumeInput?.value || "").trim();
    if (id) {
      refreshActiveSessions()
        .then(() => {
          if (!sessionExistsForResume(id)) {
            showToast(
              "Session not in live or persisted lists — attempting graceful fallback.",
              true
            );
          }
          return connect(id);
        })
        .catch(() => connect(id));
    }
  });
  if (els.resumeInput) {
    els.resumeInput.addEventListener("input", () => {
      if (els.resumeBtn) els.resumeBtn.disabled = !els.resumeInput.value.trim();
    });
    els.resumeInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const id = els.resumeInput.value.trim();
        if (id) {
          els.resumeBtn.click();
        }
      }
    });
  }
}

els.disconnectBtn.addEventListener("click", disconnect);
if (els.clearHistoryBtn) {
  els.clearHistoryBtn.addEventListener("click", clearHistory);
}
els.sendBtn.addEventListener("click", () => {
  const prompt = els.promptInput.value.trim();
  if (!prompt) return;
  els.promptInput.value = "";
  perform(prompt);
});

els.promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    els.sendBtn.click();
  }
});

resetTranscript();
updateMetrics();
updateMemoryIndicator();
updateBondMeter(0);
updateSendButtonState();
wireExamplePrompts();

if (els.voiceSelect) {
  els.voiceSelect.addEventListener("change", () => {
    if (state.connected && state.sessionId) patchCompanionConfig(state.sessionId);
  });
}
if (els.systemPromptInput) {
  els.systemPromptInput.addEventListener("input", () => {
    syncPromptPresetHighlight();
  });
  els.systemPromptInput.addEventListener("change", () => {
    if (state.connected && state.sessionId) patchCompanionConfig(state.sessionId);
  });
}

async function bootstrap() {
  if (state.bootstrapped) return;
  state.bootstrapped = true;

  await loadCatalog();
  await refreshProviderStatus();
  startProviderStatusPolling();

  try {
    const res = await fetch(`${API}/health`);
    const health = await res.json();
    state.appVersion = health.version || null;
    updateVersionBadge(state.appVersion);
    setLog(`${health.service} v${health.version} · pipeline ready`);
  } catch (_) {
    setLog("API unreachable.");
    return;
  }

  startServerMetricsPolling();
  await refreshActiveSessions();

  const resumed = await attemptAutoResumeOnLoad();
  if (!resumed) {
    try {
      const last = localStorage.getItem("prochar_last_session_id");
      if (last && els.resumeInput && !els.resumeInput.value) {
        els.resumeInput.value = last;
        if (els.resumeBtn) els.resumeBtn.disabled = false;
      }
    } catch (_) {}
  }
}

bootstrap().catch((e) => console.error("Bootstrap failed", e));