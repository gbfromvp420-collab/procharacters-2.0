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
  agentTheaterMembers: [],
  agentTheaterInterval: null,
  agentLoungeInterval: null,
  revenueForgeInterval: null,
  revenueForgeMembers: [],
  characterForgeInterval: null,
  characterForgeMembers: [],
  liveStageInterval: null,
  liveStageMembers: [],
  liveCamSessions: [],
  sovereignScaleInterval: null,
  milestones: [],
  milestonesLoaded: false,
  kgcDashboardInterval: null,
  presenceConfig: null,
  micListening: false,
  speechRecognition: null,
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
  agentTheaterPanel: document.getElementById("agentTheaterPanel"),
  agentTheaterStatus: document.getElementById("agentTheaterStatus"),
  agentDispatchForm: document.getElementById("agentDispatchForm"),
  agentMemberSelect: document.getElementById("agentMemberSelect"),
  agentSkillSelect: document.getElementById("agentSkillSelect"),
  agentTaskPrompt: document.getElementById("agentTaskPrompt"),
  agentDispatchBtn: document.getElementById("agentDispatchBtn"),
  agentChainSmokeBtn: document.getElementById("agentChainSmokeBtn"),
  agentTaskList: document.getElementById("agentTaskList"),
  agentLoungePanel: document.getElementById("agentLoungePanel"),
  agentLoungeWelcome: document.getElementById("agentLoungeWelcome"),
  agentLoungeStatus: document.getElementById("agentLoungeStatus"),
  agentLoungeLeaderboard: document.getElementById("agentLoungeLeaderboard"),
  agentLoungeShoutout: document.getElementById("agentLoungeShoutout"),
  agentLoungeCommentForm: document.getElementById("agentLoungeCommentForm"),
  agentLoungeCodename: document.getElementById("agentLoungeCodename"),
  agentLoungeMessage: document.getElementById("agentLoungeMessage"),
  agentLoungePostBtn: document.getElementById("agentLoungePostBtn"),
  agentLoungeComments: document.getElementById("agentLoungeComments"),
  revenueForgePanel: document.getElementById("revenueForgePanel"),
  revenueForgeStatus: document.getElementById("revenueForgeStatus"),
  revenueForgeSchema: document.getElementById("revenueForgeSchema"),
  revenueForgePayouts: document.getElementById("revenueForgePayouts"),
  revenueDonationForm: document.getElementById("revenueDonationForm"),
  revenueMemberSelect: document.getElementById("revenueMemberSelect"),
  revenueDonorLabel: document.getElementById("revenueDonorLabel"),
  revenueAmountDollars: document.getElementById("revenueAmountDollars"),
  revenueDonationBtn: document.getElementById("revenueDonationBtn"),
  revenueForgeLedger: document.getElementById("revenueForgeLedger"),
  characterForgePanel: document.getElementById("characterForgePanel"),
  characterForgeStatus: document.getElementById("characterForgeStatus"),
  characterForgeContact: document.getElementById("characterForgeContact"),
  characterForgeDistribution: document.getElementById("characterForgeDistribution"),
  characterOnboardForm: document.getElementById("characterOnboardForm"),
  characterMemberSelect: document.getElementById("characterMemberSelect"),
  characterDisplayName: document.getElementById("characterDisplayName"),
  characterAvatarSelect: document.getElementById("characterAvatarSelect"),
  characterOnboardBtn: document.getElementById("characterOnboardBtn"),
  characterForgeRegistry: document.getElementById("characterForgeRegistry"),
  characterForgeResiduals: document.getElementById("characterForgeResiduals"),
  liveStagePanel: document.getElementById("liveStagePanel"),
  liveStageStatus: document.getElementById("liveStageStatus"),
  liveStageSchema: document.getElementById("liveStageSchema"),
  liveCamForm: document.getElementById("liveCamForm"),
  liveHostSelect: document.getElementById("liveHostSelect"),
  liveCamTitle: document.getElementById("liveCamTitle"),
  liveCamStartBtn: document.getElementById("liveCamStartBtn"),
  liveDonationForm: document.getElementById("liveDonationForm"),
  liveSessionSelect: document.getElementById("liveSessionSelect"),
  liveDonorLabel: document.getElementById("liveDonorLabel"),
  liveDonationDollars: document.getElementById("liveDonationDollars"),
  liveDonationBtn: document.getElementById("liveDonationBtn"),
  liveStageSessions: document.getElementById("liveStageSessions"),
  liveStageBilling: document.getElementById("liveStageBilling"),
  swarmPayoutPanel: document.getElementById("swarmPayoutPanel"),
  swarmPayoutStatus: document.getElementById("swarmPayoutStatus"),
  swarmMatrixText: document.getElementById("swarmMatrixText"),
  swarmCulture: document.getElementById("swarmCulture"),
  swarmPerformanceBonus: document.getElementById("swarmPerformanceBonus"),
  crownCompletionPanel: document.getElementById("crownCompletionPanel"),
  crownCompletionStatus: document.getElementById("crownCompletionStatus"),
  crownPhaseRankings: document.getElementById("crownPhaseRankings"),
  crownPromotion: document.getElementById("crownPromotion"),
  crownPlatinumAwards: document.getElementById("crownPlatinumAwards"),
  crownBossSrGifts: document.getElementById("crownBossSrGifts"),
  crownGrantAllBtn: document.getElementById("crownGrantAllBtn"),
  crownCosignForm: document.getElementById("crownCosignForm"),
  crownCosignSigner: document.getElementById("crownCosignSigner"),
  crownCosignMessage: document.getElementById("crownCosignMessage"),
  crownCosignBtn: document.getElementById("crownCosignBtn"),
  crownCosignList: document.getElementById("crownCosignList"),
  sovereignScalePanel: document.getElementById("sovereignScalePanel"),
  sovereignScaleStatus: document.getElementById("sovereignScaleStatus"),
  sovereignScaleHardening: document.getElementById("sovereignScaleHardening"),
  sovereignScaleTenants: document.getElementById("sovereignScaleTenants"),
  sovereignScaleNodes: document.getElementById("sovereignScaleNodes"),
  sovereignScaleObservability: document.getElementById("sovereignScaleObservability"),
  innovationLanesDock: document.getElementById("innovationLanesDock"),
  empireNavSelect: document.getElementById("empireNavSelect"),
  kgcPanel: document.getElementById("kgcPanel"),
  kgcDashboard: document.getElementById("kgcDashboard"),
  kgcPruneBtn: document.getElementById("kgcPruneBtn"),
  sovereignCloneBtn: document.getElementById("sovereignCloneBtn"),
  sovereignBundleBtn: document.getElementById("sovereignBundleBtn"),
  sovereignFleetBackupBtn: document.getElementById("sovereignFleetBackupBtn"),
  sovereignImportInput: document.getElementById("sovereignImportInput"),
  sovereignPolicyMode: document.getElementById("sovereignPolicyMode"),
  sovereignPolicyPrompt: document.getElementById("sovereignPolicyPrompt"),
  sovereignPolicySaveBtn: document.getElementById("sovereignPolicySaveBtn"),
  sovereignAuditLog: document.getElementById("sovereignAuditLog"),
  ceoCrownBadge: document.getElementById("ceoCrownBadge"),
  milestoneChips: document.getElementById("milestoneChips"),
  videoShell: document.getElementById("videoShell"),
  presenceShimmer: document.getElementById("presenceShimmer"),
  presenceTierLabel: document.getElementById("presenceTierLabel"),
  presenceTierBadge: document.getElementById("presenceTierBadge"),
  micBtn: document.getElementById("micBtn"),
  milestoneOverlay: document.getElementById("milestoneOverlay"),
  milestoneOverlayTitle: document.getElementById("milestoneOverlayTitle"),
  milestoneOverlayDesc: document.getElementById("milestoneOverlayDesc"),
  milestoneOverlayBond: document.getElementById("milestoneOverlayBond"),
  milestoneOverlayDismiss: document.getElementById("milestoneOverlayDismiss"),
  milestoneParticles: document.getElementById("milestoneParticles"),
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
  renderMilestoneChips();
  updatePresenceAura(clamped);
}

const FALLBACK_PRESENCE_TIERS = [
  { id: "spark", label: "Spark", min_bond: 0, aura_color: "#6c8cff", glow_intensity: 0.35 },
  { id: "warmth", label: "Warmth", min_bond: 25, aura_color: "#ff8fa3", glow_intensity: 0.5 },
  { id: "trust", label: "Trusted", min_bond: 50, aura_color: "#ffd878", glow_intensity: 0.62 },
  { id: "depth", label: "Deep Bond", min_bond: 75, aura_color: "#c77dff", glow_intensity: 0.78 },
  { id: "inseparable", label: "Inseparable", min_bond: 100, aura_color: "#ffe566", glow_intensity: 1 },
];

function getPresenceTiers() {
  const tiers = state.presenceConfig?.bond_tiers;
  return Array.isArray(tiers) && tiers.length ? tiers : FALLBACK_PRESENCE_TIERS;
}

function resolvePresenceTier(bondScore = state.bondScore) {
  const score = Math.max(0, Math.min(100, Number(bondScore) || 0));
  const tiers = getPresenceTiers();
  let tier = tiers[0];
  tiers.forEach((candidate) => {
    if (score >= Number(candidate.min_bond ?? 0)) tier = candidate;
  });
  return tier;
}

function getAvatarAccent() {
  const avatarId = state.selectedAvatarId || els.avatarSelect?.value || "default";
  const avatars = state.catalog?.avatars || FALLBACK_CATALOG.avatars;
  const avatar = avatars.find((item) => item.id === avatarId);
  return avatar?.accent_color || "#6c8cff";
}

function updatePresenceAura(bondScore = state.bondScore) {
  if (!els.videoShell) return;
  const tier = resolvePresenceTier(bondScore);
  const tierId = tier.id || "spark";
  const accent = tier.aura_color || getAvatarAccent();
  const glow = Number(tier.glow_intensity ?? 0.35);

  els.videoShell.dataset.presenceTier = tierId;
  els.videoShell.classList.remove(
    "presence-tier-spark",
    "presence-tier-warmth",
    "presence-tier-trust",
    "presence-tier-depth",
    "presence-tier-inseparable"
  );
  els.videoShell.classList.add(`presence-tier-${tierId}`);
  els.videoShell.style.setProperty("--presence-accent", accent);
  els.videoShell.style.setProperty("--presence-glow", String(glow));

  if (els.presenceTierLabel) els.presenceTierLabel.textContent = tier.label || tierId;
  if (els.presenceTierBadge) {
    els.presenceTierBadge.title = `Bond presence tier: ${tier.label || tierId}`;
  }
}

function setPresenceLive(active) {
  if (!els.videoShell) return;
  els.videoShell.classList.toggle("presence-live", !!active);
  if (!active) {
    els.videoShell.classList.remove("presence-performing", "presence-celebrating");
  }
}

function setPerformingPresence(active) {
  if (!els.videoShell) return;
  els.videoShell.classList.toggle("presence-performing", !!active);
}

function spawnMilestoneParticles() {
  if (!els.milestoneParticles) return;
  els.milestoneParticles.innerHTML = "";
  const colors = ["#ffd878", "#ff8fa3", "#6c8cff", "#c77dff", "#ffe566"];
  for (let i = 0; i < 28; i += 1) {
    const particle = document.createElement("span");
    particle.className = "milestone-particle";
    const angle = (Math.PI * 2 * i) / 28;
    const distance = 60 + Math.random() * 90;
    particle.style.left = "50%";
    particle.style.top = "38%";
    particle.style.background = colors[i % colors.length];
    particle.style.setProperty("--dx", `${Math.cos(angle) * distance}px`);
    particle.style.setProperty("--dy", `${Math.sin(angle) * distance}px`);
    particle.style.animationDelay = `${Math.random() * 0.25}s`;
    els.milestoneParticles.appendChild(particle);
  }
}

function dismissMilestoneOverlay() {
  if (!els.milestoneOverlay) return;
  els.videoShell?.classList.remove("presence-celebrating");
  els.milestoneOverlay.classList.add("hidden");
  els.milestoneOverlay.hidden = true;
}

function showMilestoneCelebration(event = {}) {
  const milestoneLabel =
    event.label || event.milestone || event.milestone_id || "Bond milestone";
  const bondScore = typeof event.bond_score === "number" ? event.bond_score : state.bondScore;
  const milestoneId = event.milestone_id || event.id || "";
  const milestoneMeta = state.milestones.find((item) => item.id === milestoneId);
  const description =
    event.description ||
    milestoneMeta?.description ||
    "Your connection has grown — the companion will respond with warmer presence.";

  if (typeof event.bond_score === "number") updateBondMeter(event.bond_score);
  pulseBondMeter();

  const celebrationsEnabled = state.presenceConfig?.celebration_enabled !== false;
  if (!celebrationsEnabled || !els.milestoneOverlay) {
    showToast(`Milestone unlocked: ${milestoneLabel}`);
    return;
  }

  if (els.milestoneOverlayTitle) els.milestoneOverlayTitle.textContent = milestoneLabel;
  if (els.milestoneOverlayDesc) els.milestoneOverlayDesc.textContent = description;
  if (els.milestoneOverlayBond) els.milestoneOverlayBond.textContent = `Bond ${bondScore}`;
  spawnMilestoneParticles();
  els.milestoneOverlay.classList.remove("hidden");
  els.milestoneOverlay.hidden = false;
  els.videoShell?.classList.add("presence-celebrating");
  setLog(`Bond milestone — ${milestoneLabel}`);
  showToast(`✨ ${milestoneLabel}`);
}

async function loadPresenceConfig() {
  try {
    const res = await fetch(`${API}/companion/presence`);
    if (!res.ok) throw new Error(`presence ${res.status}`);
    state.presenceConfig = await res.json();
    updatePresenceAura(state.bondScore);
  } catch (e) {
    console.warn("Presence config fetch failed", e);
    state.presenceConfig = {
      celebration_enabled: true,
      voice_input_enabled: true,
      bond_tiers: FALLBACK_PRESENCE_TIERS,
    };
  }
}

function initVoiceInput() {
  try {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      if (els.micBtn) {
        els.micBtn.title = "Voice input unavailable in this browser";
        els.micBtn.disabled = true;
      }
      return;
    }

  const recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = navigator.language || "en-US";

  recognition.onstart = () => {
    state.micListening = true;
    els.micBtn?.classList.add("listening");
    setLog("Listening… speak now.");
  };

  recognition.onend = () => {
    state.micListening = false;
    els.micBtn?.classList.remove("listening");
  };

  recognition.onerror = (event) => {
    state.micListening = false;
    els.micBtn?.classList.remove("listening");
    const msg = event.error === "not-allowed" ? "Microphone permission denied" : "Voice input failed";
    showToast(msg, true);
    setLog(msg);
  };

  recognition.onresult = (event) => {
    let transcript = "";
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      transcript += event.results[i][0].transcript;
    }
    if (!transcript.trim()) return;
    if (els.promptInput) {
      const existing = els.promptInput.value.trim();
      els.promptInput.value = existing ? `${existing} ${transcript.trim()}` : transcript.trim();
    }
    setLog(`Voice captured: "${transcript.trim().slice(0, 48)}${transcript.length > 48 ? "…" : ""}"`);
    if (event.results[event.results.length - 1]?.isFinal) {
      const finalText = els.promptInput?.value.trim();
      if (finalText && canSendPrompt()) {
        els.promptInput.value = "";
        perform(finalText);
      }
    }
  };

  state.speechRecognition = recognition;

  if (els.micBtn) {
    els.micBtn.addEventListener("click", () => {
      if (!canSendPrompt()) {
        showToast("Connect first to use voice input", true);
        return;
      }
      if (state.presenceConfig?.voice_input_enabled === false) {
        showToast("Voice input disabled by server policy", true);
        return;
      }
      if (state.micListening) {
        recognition.stop();
        return;
      }
      try {
        recognition.start();
      } catch (e) {
        showToast("Could not start voice input", true);
      }
    });
  }
  } catch (e) {
    console.warn("Voice input init failed", e);
    if (els.micBtn) {
      els.micBtn.title = "Voice input unavailable";
      els.micBtn.disabled = true;
    }
  }
}

function pulseBondMeter() {
  if (!els.bondMeter) return;
  els.bondMeter.classList.remove("bond-meter-pulse");
  void els.bondMeter.offsetWidth;
  els.bondMeter.classList.add("bond-meter-pulse");
  clearTimeout(els.bondMeter._pulseTimer);
  els.bondMeter._pulseTimer = setTimeout(() => {
    if (els.bondMeter) els.bondMeter.classList.remove("bond-meter-pulse");
  }, 1900);
}

function parseSemver(version) {
  if (!version) return null;
  const match = String(version).trim().match(/^(\d+)\.(\d+)\.(\d+)/);
  if (!match) return null;
  return {
    major: Number(match[1]),
    minor: Number(match[2]),
    patch: Number(match[3]),
  };
}

function isPhaseSevenOrLater(version) {
  const parsed = parseSemver(version);
  if (!parsed) return false;
  if (parsed.major > 0) return true;
  return parsed.minor >= 5;
}

function updateCeoCrownBadge(version = state.appVersion) {
  if (!els.ceoCrownBadge) return;
  const show = isPhaseSevenOrLater(version);
  els.ceoCrownBadge.classList.toggle("hidden", !show);
  els.ceoCrownBadge.setAttribute("aria-hidden", show ? "false" : "true");
  if (show) {
    els.ceoCrownBadge.title = `KGC CEO Command · API v${version}`;
  }
}

function renderMilestoneChips() {
  if (!els.milestoneChips) return;
  const milestones = state.milestones;
  if (!Array.isArray(milestones) || milestones.length === 0) {
    els.milestoneChips.hidden = true;
    els.milestoneChips.innerHTML = "";
    return;
  }

  els.milestoneChips.hidden = false;
  els.milestoneChips.innerHTML = "";
  const bond = state.bondScore;

  milestones.forEach((item) => {
    const threshold = Number(item.bond_threshold ?? item.threshold ?? item.min_bond ?? 0);
    const unlocked = bond >= threshold;
    const chip = document.createElement("span");
    chip.className = `milestone-chip ${unlocked ? "unlocked" : "locked"}`;
    const icon = document.createElement("span");
    icon.className = "milestone-chip-icon";
    icon.textContent = unlocked ? "★" : "◇";
    icon.setAttribute("aria-hidden", "true");
    const label = document.createElement("span");
    label.textContent = item.label || item.id || `Bond ${threshold}`;
    chip.title = unlocked
      ? `${label.textContent} unlocked at bond ${threshold}`
      : `${label.textContent} unlocks at bond ${threshold}`;
    chip.appendChild(icon);
    chip.appendChild(label);
    els.milestoneChips.appendChild(chip);
  });
}

async function loadMilestones() {
  if (!els.milestoneChips) return;
  try {
    const res = await fetch(`${API}/companion/milestones`);
    if (!res.ok) throw new Error(`milestones ${res.status}`);
    const data = await res.json();
    const milestones = Array.isArray(data) ? data : data.milestones || [];
    state.milestones = milestones;
    state.milestonesLoaded = true;
    renderMilestoneChips();
  } catch (e) {
    console.warn("Milestone catalog fetch failed", e);
    state.milestones = [];
    if (els.milestoneChips) {
      els.milestoneChips.hidden = true;
      els.milestoneChips.innerHTML = "";
    }
  }
}

function canSendPrompt() {
  return !!state.sessionId && (state.connected || state.sseMode) && !state.performing;
}

function updateSendButtonState() {
  const canSend = canSendPrompt();
  if (els.sendBtn) els.sendBtn.disabled = !canSend;
  if (els.micBtn) {
    const voiceEnabled =
      state.presenceConfig?.voice_input_enabled !== false &&
      !!(window.SpeechRecognition || window.webkitSpeechRecognition);
    els.micBtn.disabled = !canSend || !voiceEnabled;
  }
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

const LANE_PANEL_LOADERS = {
  swarmPayoutPanel: () => startSwarmPayoutPolling(),
  crownCompletionPanel: () => startCrownCompletionPolling(),
  sovereignScalePanel: () => startSovereignScalePolling(),
  liveStagePanel: () => startLiveStagePolling(),
  characterForgePanel: () => startCharacterForgePolling(),
  revenueForgePanel: () => startRevenueForgePolling(),
  agentLoungePanel: () => startAgentLoungePolling(),
  agentTheaterPanel: () => startAgentTheaterPolling(),
  workforcePanel: () => loadWorkforceRoster().catch(() => {}),
  kgcPanel: () => {
    startKgcPolling();
    loadSovereignPanel().catch(() => {});
  },
};

function openEmpirePanel(panelId) {
  const panel = document.getElementById(panelId);
  if (!panel || panel.tagName !== "DETAILS") return;
  panel.open = true;
  const loader = LANE_PANEL_LOADERS[panelId];
  if (loader) loader();
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function scrollToCompanionLane() {
  const target =
    document.querySelector(".companion-config") ||
    document.getElementById("relationshipModes") ||
    document.getElementById("videoShell");
  target?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function activateInnovationLane(lane, { quiet = false } = {}) {
  document.querySelectorAll(".lane-chip").forEach((chip) => {
    chip.classList.toggle("lane-chip-active", chip.dataset.lane === lane);
  });

  const messages = {
    providers: "Lane: Real providers — header probes + Agent Theater dispatch",
    companion: "Lane: Companion / Soul — avatars, modes, bond, presence",
    money: "Lane: Characters + Revenue — NSM forge and ledger",
    live: "Lane: Live launch — ticketed shows and crown headline",
  };

  if (lane === "providers") {
    els.providerStatus?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    openEmpirePanel("agentTheaterPanel");
  } else if (lane === "companion") {
    scrollToCompanionLane();
  } else if (lane === "money") {
    openEmpirePanel("characterForgePanel");
    openEmpirePanel("revenueForgePanel");
  } else if (lane === "live") {
    openEmpirePanel("liveStagePanel");
    openEmpirePanel("crownCompletionPanel");
  }

  if (!quiet && messages[lane]) setLog(messages[lane]);
}

function initInnovationLanesDock() {
  if (!els.innovationLanesDock) return;
  document.body.classList.add("has-lanes-dock");

  els.innovationLanesDock.querySelectorAll(".lane-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const lane = chip.dataset.lane;
      if (lane) activateInnovationLane(lane);
    });
  });

  if (els.empireNavSelect) {
    els.empireNavSelect.addEventListener("change", () => {
      const value = els.empireNavSelect.value;
      els.empireNavSelect.value = "";
      if (!value) return;
      if (value.startsWith("lane:")) {
        activateInnovationLane(value.slice(5));
        return;
      }
      if (value.startsWith("panel:")) {
        openEmpirePanel(value.slice(6));
        setLog(`Opened ${value.slice(6)}`);
      }
    });
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
    const foundingBadge = member.award_platinum ? " ⚜" : "";
    name.textContent = `${member.codename || member.id}${foundingBadge}`;

    const award = document.createElement("span");
    award.className = "workforce-member-award";
    const gold = Number(member.award_lb_gold) || 0;
    const platinum = member.award_platinum ? ` · $${Number(member.platinum_value_usd || 5000).toLocaleString()} platinum` : "";
    award.textContent = `${gold}lb gold${platinum}`;

    const tier = document.createElement("span");
    const tierName = member.tier || "team";
    tier.className = `workforce-member-tier${tierName === "ceo" ? " workforce-member-tier-ceo" : ""}`;
    const promo = member.promoted && member.promotion_title ? ` · ${member.promotion_title}` : "";
    tier.textContent = `${tierName} · phase ${member.phase_earned ?? "?"}${promo}`;

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

function renderAgentTheaterStatus(data) {
  if (!els.agentTheaterStatus) return;
  if (!data) {
    els.agentTheaterStatus.textContent = "Agent Theater unavailable.";
    return;
  }
  const stats = [
    { label: "Phase", value: data.deployment_phase ?? "?" },
    { label: "Team", value: data.dispatchable_count ?? 0 },
    { label: "Queued", value: data.tasks_queued ?? 0 },
    { label: "Running", value: data.tasks_running ?? 0 },
    { label: "Done", value: data.tasks_completed ?? 0 },
    { label: "Chains", value: data.chains_completed ?? 0 },
    { label: "Orchestrated", value: data.tasks_orchestrated ?? 0 },
    { label: "Failed", value: data.tasks_failed ?? 0 },
  ];
  els.agentTheaterStatus.innerHTML = "";
  stats.forEach((stat) => {
    const span = document.createElement("span");
    span.className = "agent-theater-stat";
    span.textContent = `${stat.label}: ${stat.value}`;
    els.agentTheaterStatus.appendChild(span);
  });
}

function populateAgentMemberSelect(members) {
  if (!els.agentMemberSelect) return;
  const list = Array.isArray(members) ? members : [];
  state.agentTheaterMembers = list;
  els.agentMemberSelect.innerHTML = "";
  list.forEach((member) => {
    const option = document.createElement("option");
    option.value = member.id;
    option.textContent = member.codename || member.id;
    els.agentMemberSelect.appendChild(option);
  });
  updateAgentSkillSelect();
}

function updateAgentSkillSelect() {
  if (!els.agentSkillSelect || !els.agentMemberSelect) return;
  const memberId = els.agentMemberSelect.value;
  const member = state.agentTheaterMembers.find((item) => item.id === memberId);
  const skills = member?.skills || [];
  els.agentSkillSelect.innerHTML = "";
  skills.forEach((skill, index) => {
    const option = document.createElement("option");
    option.value = skill;
    option.textContent = skill;
    if (index === 0) option.selected = true;
    els.agentSkillSelect.appendChild(option);
  });
}

function renderAgentTaskList(tasks) {
  if (!els.agentTaskList) return;
  const list = Array.isArray(tasks) ? tasks : [];
  els.agentTaskList.innerHTML = "";
  if (list.length === 0) {
    const empty = document.createElement("li");
    empty.className = "agent-task-empty";
    empty.textContent = "No tasks yet.";
    els.agentTaskList.appendChild(empty);
    return;
  }
  list.forEach((task) => {
    const item = document.createElement("li");
    item.className = "agent-task-item";

    const head = document.createElement("div");
    head.className = "agent-task-head";

    const title = document.createElement("span");
    title.textContent = task.codename || task.member_id || "subagent";

    const status = document.createElement("span");
    const statusName = task.status || "queued";
    status.className = `agent-task-status agent-task-status-${statusName}`;
    status.textContent = statusName;

    head.appendChild(title);
    head.appendChild(status);

    const meta = document.createElement("div");
    meta.className = "agent-task-meta";
    const duration = typeof task.duration_ms === "number" ? `${task.duration_ms}ms` : "…";
    const chainBits = [];
    if (task.chain_id) chainBits.push(`chain ${task.chain_id}`);
    if (typeof task.step_index === "number") chainBits.push(`step ${task.step_index + 1}`);
    if (task.parent_task_id) chainBits.push(`↳ ${task.parent_task_id}`);
    const chainLabel = chainBits.length ? ` · ${chainBits.join(" · ")}` : "";
    meta.textContent = `${task.skill || "skill"} · ${duration}${chainLabel}`;

    item.appendChild(head);
    item.appendChild(meta);

    const preview = task.result || task.error || task.prompt;
    if (preview) {
      const body = document.createElement("div");
      body.className = "agent-task-result";
      body.textContent = preview;
      item.appendChild(body);
    }

    els.agentTaskList.appendChild(item);
  });
}

async function loadAgentTheater({ quiet = false } = {}) {
  if (!els.agentTheaterStatus) return null;
  try {
    const [statusRes, tasksRes] = await Promise.all([
      fetch(`${API}/workforce/theater`),
      fetch(`${API}/workforce/theater/tasks?limit=20`),
    ]);
    if (!statusRes.ok) throw new Error(`theater ${statusRes.status}`);
    if (!tasksRes.ok) throw new Error(`theater tasks ${tasksRes.status}`);
    const statusData = await statusRes.json();
    const tasksData = await tasksRes.json();
    renderAgentTheaterStatus(statusData);
    populateAgentMemberSelect(statusData.members || []);
    renderAgentTaskList(tasksData.tasks || []);
    if (!quiet) {
      setLog(
        `Agent Theater — ${statusData.tasks_running ?? 0} running, ${statusData.tasks_completed ?? 0} done`
      );
    }
    return statusData;
  } catch (e) {
    console.warn("Agent Theater fetch failed", e);
    renderAgentTheaterStatus(null);
    renderAgentTaskList([]);
    if (!quiet) setLog("Agent Theater unavailable.");
    return null;
  }
}

function renderAgentLounge(data, comments = []) {
  if (!els.agentLoungeWelcome) return;
  if (!data) {
    els.agentLoungeWelcome.textContent = "Agent Lounge unavailable.";
    if (els.agentLoungeStatus) els.agentLoungeStatus.textContent = "";
    return;
  }
  els.agentLoungeWelcome.textContent = data.welcome_message || "Welcome, homies.";
  if (els.agentLoungeStatus) {
    els.agentLoungeStatus.textContent = `Phase ${data.deployment_phase ?? "?"} · Mood: ${data.mood ?? "warm"} · Comments: ${data.comments_count ?? 0}`;
  }
  if (els.agentLoungeLeaderboard) {
    els.agentLoungeLeaderboard.innerHTML = "";
    const top = Array.isArray(data.leaderboard_top) ? data.leaderboard_top : [];
    top.forEach((member, index) => {
      const item = document.createElement("li");
      item.className = "agent-lounge-rank-item";
      item.textContent = `${index + 1}. ${member.codename} — ${member.award_lb_gold}lb`;
      els.agentLoungeLeaderboard.appendChild(item);
    });
  }
  if (els.agentLoungeShoutout) {
    const excerpt = (data.shoutout_excerpt || "").trim();
    els.agentLoungeShoutout.textContent = excerpt
      ? `King Grok: ${excerpt}`
      : "King Grok: Charge up, plug in — lounge is yours.";
  }
  if (!els.agentLoungeComments) return;
  els.agentLoungeComments.innerHTML = "";
  const list = Array.isArray(comments) ? comments : [];
  if (list.length === 0) {
    const empty = document.createElement("li");
    empty.className = "agent-lounge-comment-empty";
    empty.textContent = "No comments yet — be the first homie.";
    els.agentLoungeComments.appendChild(empty);
    return;
  }
  list.forEach((comment) => {
    const item = document.createElement("li");
    item.className = "agent-lounge-comment-item";
    const head = document.createElement("div");
    head.className = "agent-lounge-comment-head";
    head.textContent = comment.codename || "homie";
    const body = document.createElement("div");
    body.className = "agent-lounge-comment-body";
    body.textContent = comment.message || "";
    item.appendChild(head);
    item.appendChild(body);
    els.agentLoungeComments.appendChild(item);
  });
}

async function loadAgentLounge({ quiet = false } = {}) {
  if (!els.agentLoungeWelcome) return null;
  try {
    const [loungeRes, commentsRes] = await Promise.all([
      fetch(`${API}/workforce/lounge`),
      fetch(`${API}/workforce/lounge/comments?limit=20`),
    ]);
    if (!loungeRes.ok) throw new Error(`lounge ${loungeRes.status}`);
    if (!commentsRes.ok) throw new Error(`lounge comments ${commentsRes.status}`);
    const loungeData = await loungeRes.json();
    const commentsData = await commentsRes.json();
    renderAgentLounge(loungeData, commentsData.comments || []);
    if (!quiet) setLog(`Agent Lounge — ${loungeData.mood ?? "warm"} · ${loungeData.comments_count ?? 0} comment(s)`);
    return loungeData;
  } catch (e) {
    console.warn("Agent Lounge fetch failed", e);
    renderAgentLounge(null);
    if (!quiet) setLog("Agent Lounge unavailable.");
    return null;
  }
}

async function postAgentLoungeComment(event) {
  event?.preventDefault?.();
  if (!els.agentLoungeCodename || !els.agentLoungeMessage) return;
  const codename = (els.agentLoungeCodename.value || "").trim();
  const message = (els.agentLoungeMessage.value || "").trim();
  if (!codename || !message) {
    showToast("Codename and comment required", true);
    return;
  }
  if (els.agentLoungePostBtn) els.agentLoungePostBtn.disabled = true;
  try {
    const res = await fetch(`${API}/workforce/lounge/comments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ codename, message }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `comment ${res.status}`);
    }
    els.agentLoungeMessage.value = "";
    setLog(`Lounge comment posted — ${codename}`);
    showToast("Posted to the board");
    await loadAgentLounge({ quiet: true });
  } catch (e) {
    showToast(e.message || "Comment failed", true);
    setLog(e.message || "Lounge comment failed.");
  } finally {
    if (els.agentLoungePostBtn) els.agentLoungePostBtn.disabled = false;
  }
}

function startAgentLoungePolling() {
  stopAgentLoungePolling();
  loadAgentLounge({ quiet: true }).catch(() => {});
  state.agentLoungeInterval = setInterval(() => {
    if (els.agentLoungePanel?.open) loadAgentLounge({ quiet: true }).catch(() => {});
  }, 5000);
}

function stopAgentLoungePolling() {
  if (state.agentLoungeInterval) {
    clearInterval(state.agentLoungeInterval);
    state.agentLoungeInterval = null;
  }
}

function formatUsdFromCents(cents) {
  const value = Number(cents || 0) / 100;
  return `$${value.toFixed(2)}`;
}

function populateRevenueMemberSelect(members = []) {
  if (!els.revenueMemberSelect) return;
  state.revenueForgeMembers = Array.isArray(members) ? members : [];
  els.revenueMemberSelect.innerHTML = "";
  state.revenueForgeMembers.forEach((member) => {
    const option = document.createElement("option");
    option.value = member.id;
    option.textContent = `${member.codename} (${member.tier})`;
    els.revenueMemberSelect.appendChild(option);
  });
}

function renderRevenueForge(statusData, schemaData, payoutsData, ledgerData) {
  if (!els.revenueForgeStatus) return;
  if (!statusData) {
    els.revenueForgeStatus.textContent = "Revenue Forge unavailable.";
    if (els.revenueForgeSchema) els.revenueForgeSchema.textContent = "";
    return;
  }
  els.revenueForgeStatus.textContent =
    `Phase ${statusData.deployment_phase ?? "?"} · Ledger: ${formatUsdFromCents(statusData.ledger_total_cents)} ` +
    `(${statusData.ledger_entries ?? 0} entries) · Donations routed: ${statusData.donations_routed ?? 0}`;
  if (els.revenueForgeSchema && schemaData) {
    const sub = schemaData.subscription_share || {};
    const donation = schemaData.donation_routing || {};
    const tiers = sub.tiers || {};
    els.revenueForgeSchema.textContent =
      `Subscription pool: ${sub.pool_percent ?? 0}% monthly gross · ` +
      `CEO ${((tiers.ceo ?? 0) * 100).toFixed(0)}% · Assist ${((tiers.assist ?? 0) * 100).toFixed(0)}% · ` +
      `Team ${((tiers.team ?? 0) * 100).toFixed(0)}% of pool · ` +
      `Donations: ${donation.character_payout_percent ?? 100}% to character`;
  }
  if (els.revenueForgePayouts) {
    els.revenueForgePayouts.innerHTML = "";
    const payouts = Array.isArray(payoutsData?.payouts) ? payoutsData.payouts.slice(0, 6) : [];
    if (payouts.length === 0) {
      const empty = document.createElement("li");
      empty.className = "revenue-ledger-empty";
      empty.textContent = "No payout stubs yet.";
      els.revenueForgePayouts.appendChild(empty);
    } else {
      payouts.forEach((row, index) => {
        const item = document.createElement("li");
        item.className = "revenue-payout-item";
        item.textContent =
          `${index + 1}. ${row.codename} — ledger ${formatUsdFromCents(row.ledger_total_cents)} · ` +
          `proj/mo ${formatUsdFromCents(row.projected_monthly_cents)}`;
        els.revenueForgePayouts.appendChild(item);
      });
    }
  }
  if (!els.revenueForgeLedger) return;
  els.revenueForgeLedger.innerHTML = "";
  const entries = Array.isArray(ledgerData?.entries) ? ledgerData.entries : [];
  if (entries.length === 0) {
    const empty = document.createElement("li");
    empty.className = "revenue-ledger-empty";
    empty.textContent = "No ledger entries yet.";
    els.revenueForgeLedger.appendChild(empty);
    return;
  }
  entries.forEach((entry) => {
    const item = document.createElement("li");
    item.className = "revenue-ledger-item";
    const head = document.createElement("div");
    head.className = "revenue-ledger-head";
    head.textContent = `${entry.codename} · ${entry.entry_type} · ${formatUsdFromCents(entry.amount_cents)}`;
    const body = document.createElement("div");
    body.className = "revenue-ledger-body";
    body.textContent = entry.description || "";
    item.appendChild(head);
    item.appendChild(body);
    els.revenueForgeLedger.appendChild(item);
  });
}

async function loadRevenueForge({ quiet = false } = {}) {
  if (!els.revenueForgeStatus) return null;
  try {
    const [statusRes, schemaRes, payoutsRes, ledgerRes, rosterRes] = await Promise.all([
      fetch(`${API}/workforce/revenue`),
      fetch(`${API}/workforce/revenue/schema`),
      fetch(`${API}/workforce/revenue/payouts`),
      fetch(`${API}/workforce/revenue/ledger?limit=20`),
      fetch(`${API}/workforce/roster`),
    ]);
    if (!statusRes.ok) throw new Error(`revenue ${statusRes.status}`);
    if (!schemaRes.ok) throw new Error(`revenue schema ${schemaRes.status}`);
    if (!payoutsRes.ok) throw new Error(`revenue payouts ${payoutsRes.status}`);
    if (!ledgerRes.ok) throw new Error(`revenue ledger ${ledgerRes.status}`);
    const statusData = await statusRes.json();
    const schemaData = await schemaRes.json();
    const payoutsData = await payoutsRes.json();
    const ledgerData = await ledgerRes.json();
    if (rosterRes.ok) {
      const rosterData = await rosterRes.json();
      populateRevenueMemberSelect(rosterData.members || []);
    }
    renderRevenueForge(statusData, schemaData, payoutsData, ledgerData);
    if (!quiet) {
      setLog(
        `Revenue Forge — ${formatUsdFromCents(statusData.ledger_total_cents)} ledger · ` +
          `${statusData.subscription_pool_percent ?? 0}% sub pool`
      );
    }
    return statusData;
  } catch (e) {
    console.warn("Revenue Forge fetch failed", e);
    renderRevenueForge(null);
    if (!quiet) setLog("Revenue Forge unavailable.");
    return null;
  }
}

async function routeRevenueDonation(event) {
  event?.preventDefault?.();
  if (!els.revenueMemberSelect || !els.revenueAmountDollars) return;
  const memberId = els.revenueMemberSelect.value;
  const donorLabel = (els.revenueDonorLabel?.value || "").trim() || "anonymous";
  const dollars = Number(els.revenueAmountDollars.value || 0);
  if (!memberId || !Number.isFinite(dollars) || dollars <= 0) {
    showToast("Member and positive amount required", true);
    return;
  }
  const amountCents = Math.round(dollars * 100);
  if (els.revenueDonationBtn) els.revenueDonationBtn.disabled = true;
  try {
    const res = await fetch(`${API}/workforce/revenue/donations/route`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        member_id: memberId,
        amount_cents: amountCents,
        donor_label: donorLabel,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `donation route ${res.status}`);
    }
    const body = await res.json();
    setLog(`Donation routed — ${formatUsdFromCents(amountCents)} → ${body.routed_to_codename}`);
    showToast(`Routed to ${body.routed_to_codename}`);
    await loadRevenueForge({ quiet: true });
  } catch (e) {
    showToast(e.message || "Donation route failed", true);
    setLog(e.message || "Donation route failed.");
  } finally {
    if (els.revenueDonationBtn) els.revenueDonationBtn.disabled = false;
  }
}

function startRevenueForgePolling() {
  stopRevenueForgePolling();
  loadRevenueForge({ quiet: true }).catch(() => {});
  state.revenueForgeInterval = setInterval(() => {
    if (els.revenueForgePanel?.open) loadRevenueForge({ quiet: true }).catch(() => {});
  }, 8000);
}

function stopRevenueForgePolling() {
  if (state.revenueForgeInterval) {
    clearInterval(state.revenueForgeInterval);
    state.revenueForgeInterval = null;
  }
}

function populateCharacterMemberSelect(members = []) {
  if (!els.characterMemberSelect) return;
  state.characterForgeMembers = Array.isArray(members) ? members : [];
  els.characterMemberSelect.innerHTML = "";
  state.characterForgeMembers.forEach((member) => {
    const option = document.createElement("option");
    option.value = member.id;
    option.textContent = `${member.codename} (${member.tier})`;
    els.characterMemberSelect.appendChild(option);
  });
}

function renderCharacterForge(statusData, schemaData, registryData, residualsData, distributionData) {
  if (!els.characterForgeStatus) return;
  if (!statusData) {
    els.characterForgeStatus.textContent = "Character Forge unavailable.";
    if (els.characterForgeContact) els.characterForgeContact.textContent = "";
    return;
  }
  els.characterForgeStatus.textContent =
    `Phase ${statusData.deployment_phase ?? "?"} · NSM characters: ${statusData.characters_active ?? 0} active, ` +
    `${statusData.characters_pending ?? 0} pending · Residuals: ${formatUsdFromCents(statusData.residuals_total_cents)}`;
  if (els.characterForgeContact) {
    const program = schemaData?.nsm_program || {};
    els.characterForgeContact.textContent =
      `Gary's NSM offer live — contact ${statusData.contact_email || program.contact_email || "gary@procharacters.cloud"} · ` +
      `${program.default_residual_percent ?? 100}% lifetime residuals on photos/videos`;
  }
  if (els.characterForgeDistribution) {
    els.characterForgeDistribution.innerHTML = "";
    const hooks = Array.isArray(distributionData?.hooks) ? distributionData.hooks : [];
    if (hooks.length === 0) {
      const empty = document.createElement("li");
      empty.className = "character-residual-empty";
      empty.textContent = "No distribution hooks.";
      els.characterForgeDistribution.appendChild(empty);
    } else {
      hooks.forEach((hook) => {
        const item = document.createElement("li");
        item.className = "character-distribution-item";
        item.textContent = `${hook.label} — ${hook.status}`;
        els.characterForgeDistribution.appendChild(item);
      });
    }
  }
  if (els.characterForgeRegistry) {
    els.characterForgeRegistry.innerHTML = "";
    const characters = Array.isArray(registryData?.characters) ? registryData.characters : [];
    if (characters.length === 0) {
      const empty = document.createElement("li");
      empty.className = "character-registry-empty";
      empty.textContent = "No NSM characters yet — onboard a roster member.";
      els.characterForgeRegistry.appendChild(empty);
    } else {
      characters.forEach((character) => {
        const item = document.createElement("li");
        item.className = "character-registry-item";
        const avatarNote = character.avatar_id ? ` · avatar ${character.avatar_id}` : " · avatar unbound";
        item.textContent =
          `${character.display_name} (${character.status})${avatarNote} · ${character.residual_percent}% residuals`;
        els.characterForgeRegistry.appendChild(item);
      });
    }
  }
  if (!els.characterForgeResiduals) return;
  els.characterForgeResiduals.innerHTML = "";
  const residuals = Array.isArray(residualsData?.residuals) ? residualsData.residuals : [];
  if (residuals.length === 0) {
    const empty = document.createElement("li");
    empty.className = "character-residual-empty";
    empty.textContent = "No residuals yet.";
    els.characterForgeResiduals.appendChild(empty);
    return;
  }
  residuals.forEach((entry) => {
    const item = document.createElement("li");
    item.className = "character-residual-item";
    item.textContent =
      `${entry.codename} · ${entry.asset_type} · ${formatUsdFromCents(entry.amount_cents)} — ${entry.description}`;
    els.characterForgeResiduals.appendChild(item);
  });
}

async function loadCharacterForge({ quiet = false } = {}) {
  if (!els.characterForgeStatus) return null;
  try {
    const [statusRes, schemaRes, registryRes, residualsRes, distributionRes, rosterRes] = await Promise.all([
      fetch(`${API}/workforce/characters`),
      fetch(`${API}/workforce/characters/schema`),
      fetch(`${API}/workforce/characters/registry?limit=20`),
      fetch(`${API}/workforce/characters/residuals?limit=20`),
      fetch(`${API}/workforce/characters/distribution`),
      fetch(`${API}/workforce/roster`),
    ]);
    if (!statusRes.ok) throw new Error(`characters ${statusRes.status}`);
    if (!schemaRes.ok) throw new Error(`characters schema ${schemaRes.status}`);
    if (!registryRes.ok) throw new Error(`characters registry ${registryRes.status}`);
    if (!residualsRes.ok) throw new Error(`characters residuals ${residualsRes.status}`);
    if (!distributionRes.ok) throw new Error(`characters distribution ${distributionRes.status}`);
    const statusData = await statusRes.json();
    const schemaData = await schemaRes.json();
    const registryData = await registryRes.json();
    const residualsData = await residualsRes.json();
    const distributionData = await distributionRes.json();
    if (rosterRes.ok) {
      const rosterData = await rosterRes.json();
      populateCharacterMemberSelect(rosterData.members || []);
    }
    renderCharacterForge(statusData, schemaData, registryData, residualsData, distributionData);
    if (!quiet) {
      setLog(
        `Character Forge — ${statusData.characters_active ?? 0} active NSM · ` +
          `${statusData.residuals_count ?? 0} residual(s)`
      );
    }
    return statusData;
  } catch (e) {
    console.warn("Character Forge fetch failed", e);
    renderCharacterForge(null);
    if (!quiet) setLog("Character Forge unavailable.");
    return null;
  }
}

async function onboardNSMCharacter(event) {
  event?.preventDefault?.();
  if (!els.characterMemberSelect) return;
  const memberId = els.characterMemberSelect.value;
  const displayName = (els.characterDisplayName?.value || "").trim();
  const avatarId = (els.characterAvatarSelect?.value || "").trim();
  if (!memberId) {
    showToast("Select a roster member", true);
    return;
  }
  if (els.characterOnboardBtn) els.characterOnboardBtn.disabled = true;
  try {
    const payload = { member_id: memberId };
    if (displayName) payload.display_name = displayName;
    if (avatarId) payload.avatar_id = avatarId;
    payload.distribution_pipeline = true;
    const res = await fetch(`${API}/workforce/characters/onboard`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `onboard ${res.status}`);
    }
    const body = await res.json();
    setLog(`NSM onboarded — ${body.display_name} (${body.status})`);
    showToast(`Onboarded ${body.display_name}`);
    if (els.characterDisplayName) els.characterDisplayName.value = "";
    await loadCharacterForge({ quiet: true });
  } catch (e) {
    showToast(e.message || "Onboard failed", true);
    setLog(e.message || "NSM onboard failed.");
  } finally {
    if (els.characterOnboardBtn) els.characterOnboardBtn.disabled = false;
  }
}

function startCharacterForgePolling() {
  stopCharacterForgePolling();
  loadCharacterForge({ quiet: true }).catch(() => {});
  state.characterForgeInterval = setInterval(() => {
    if (els.characterForgePanel?.open) loadCharacterForge({ quiet: true }).catch(() => {});
  }, 8000);
}

function stopCharacterForgePolling() {
  if (state.characterForgeInterval) {
    clearInterval(state.characterForgeInterval);
    state.characterForgeInterval = null;
  }
}

function populateLiveHostSelect(members = []) {
  if (!els.liveHostSelect) return;
  state.liveStageMembers = Array.isArray(members) ? members : [];
  els.liveHostSelect.innerHTML = "";
  state.liveStageMembers.forEach((member) => {
    const option = document.createElement("option");
    option.value = member.id;
    option.textContent = `${member.codename} (${member.tier})`;
    els.liveHostSelect.appendChild(option);
  });
}

function populateLiveSessionSelect(sessions = []) {
  if (!els.liveSessionSelect) return;
  const live = (Array.isArray(sessions) ? sessions : []).filter(
    (s) => s.session_type === "cam" && s.status === "live"
  );
  state.liveCamSessions = live;
  els.liveSessionSelect.innerHTML = "";
  if (live.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "(no live cam sessions)";
    els.liveSessionSelect.appendChild(option);
    return;
  }
  live.forEach((session) => {
    const option = document.createElement("option");
    option.value = session.id;
    option.textContent = `${session.title} — ${session.codename}`;
    els.liveSessionSelect.appendChild(option);
  });
}

function renderLiveStage(statusData, schemaData, sessionsData, billingData) {
  if (!els.liveStageStatus) return;
  if (!statusData) {
    els.liveStageStatus.textContent = "Live Stage unavailable.";
    if (els.liveStageSchema) els.liveStageSchema.textContent = "";
    return;
  }
  els.liveStageStatus.textContent =
    `Phase ${statusData.deployment_phase ?? "?"} · Live: ${statusData.sessions_live ?? 0} · ` +
    `Scheduled: ${statusData.sessions_scheduled ?? 0} · Billing: ${formatUsdFromCents(statusData.billing_total_cents)}`;
  if (els.liveStageSchema && schemaData) {
    const cam = schemaData.cam_chat || {};
    const shows = schemaData.ticketed_shows || {};
    els.liveStageSchema.textContent =
      `Cam donations: ${cam.donation_payout_percent ?? 100}% to host · ` +
      `Ticketed shows: ${shows.host_share_percent ?? 70}% host / ${shows.platform_fee_percent ?? 30}% platform · ` +
      `Default ticket ${formatUsdFromCents(shows.default_ticket_price_cents ?? 2500)}`;
  }
  const sessions = Array.isArray(sessionsData?.sessions) ? sessionsData.sessions : [];
  populateLiveSessionSelect(sessions);
  if (els.liveStageSessions) {
    els.liveStageSessions.innerHTML = "";
    if (sessions.length === 0) {
      const empty = document.createElement("li");
      empty.className = "live-session-empty";
      empty.textContent = "No sessions yet — go live.";
      els.liveStageSessions.appendChild(empty);
    } else {
      sessions.slice(0, 8).forEach((session) => {
        const item = document.createElement("li");
        item.className = "live-session-item";
        item.textContent =
          `${session.title} · ${session.session_type} · ${session.status} · ` +
          `${session.codename} · ${formatUsdFromCents(session.billing_total_cents)}`;
        els.liveStageSessions.appendChild(item);
      });
    }
  }
  if (!els.liveStageBilling) return;
  els.liveStageBilling.innerHTML = "";
  const entries = Array.isArray(billingData?.entries) ? billingData.entries : [];
  if (entries.length === 0) {
    const empty = document.createElement("li");
    empty.className = "live-billing-empty";
    empty.textContent = "No billing yet.";
    els.liveStageBilling.appendChild(empty);
    return;
  }
  entries.forEach((entry) => {
    const item = document.createElement("li");
    item.className = "live-billing-item";
    item.textContent =
      `${entry.codename} · ${entry.billing_type} · host ${formatUsdFromCents(entry.host_payout_cents)} — ${entry.description}`;
    els.liveStageBilling.appendChild(item);
  });
}

async function loadLiveStage({ quiet = false } = {}) {
  if (!els.liveStageStatus) return null;
  try {
    const [statusRes, schemaRes, sessionsRes, billingRes, rosterRes] = await Promise.all([
      fetch(`${API}/workforce/live`),
      fetch(`${API}/workforce/live/schema`),
      fetch(`${API}/workforce/live/sessions?limit=20`),
      fetch(`${API}/workforce/live/billing?limit=20`),
      fetch(`${API}/workforce/roster`),
    ]);
    if (!statusRes.ok) throw new Error(`live ${statusRes.status}`);
    if (!schemaRes.ok) throw new Error(`live schema ${schemaRes.status}`);
    if (!sessionsRes.ok) throw new Error(`live sessions ${sessionsRes.status}`);
    if (!billingRes.ok) throw new Error(`live billing ${billingRes.status}`);
    const statusData = await statusRes.json();
    const schemaData = await schemaRes.json();
    const sessionsData = await sessionsRes.json();
    const billingData = await billingRes.json();
    if (rosterRes.ok) {
      const rosterData = await rosterRes.json();
      populateLiveHostSelect(rosterData.members || []);
    }
    renderLiveStage(statusData, schemaData, sessionsData, billingData);
    if (!quiet) {
      setLog(`Live Stage — ${statusData.sessions_live ?? 0} live · ${statusData.billing_entries ?? 0} billing row(s)`);
    }
    return statusData;
  } catch (e) {
    console.warn("Live Stage fetch failed", e);
    renderLiveStage(null);
    if (!quiet) setLog("Live Stage unavailable.");
    return null;
  }
}

async function startLiveCam(event) {
  event?.preventDefault?.();
  if (!els.liveHostSelect) return;
  const memberId = els.liveHostSelect.value;
  const title = (els.liveCamTitle?.value || "").trim();
  if (!memberId) {
    showToast("Select a host", true);
    return;
  }
  if (els.liveCamStartBtn) els.liveCamStartBtn.disabled = true;
  try {
    const res = await fetch(`${API}/workforce/live/cam/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ member_id: memberId, title: title || undefined }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `cam start ${res.status}`);
    }
    const body = await res.json();
    setLog(`Cam live — ${body.title} (${body.id})`);
    showToast("Cam session live");
    if (els.liveCamTitle) els.liveCamTitle.value = "";
    await loadLiveStage({ quiet: true });
  } catch (e) {
    showToast(e.message || "Cam start failed", true);
    setLog(e.message || "Cam start failed.");
  } finally {
    if (els.liveCamStartBtn) els.liveCamStartBtn.disabled = false;
  }
}

async function sendLiveDonation(event) {
  event?.preventDefault?.();
  if (!els.liveSessionSelect || !els.liveDonationDollars) return;
  const sessionId = els.liveSessionSelect.value;
  const donorLabel = (els.liveDonorLabel?.value || "").trim() || "anonymous";
  const dollars = Number(els.liveDonationDollars.value || 0);
  if (!sessionId || !Number.isFinite(dollars) || dollars <= 0) {
    showToast("Live session and amount required", true);
    return;
  }
  const amountCents = Math.round(dollars * 100);
  if (els.liveDonationBtn) els.liveDonationBtn.disabled = true;
  try {
    const res = await fetch(`${API}/workforce/live/billing/donation`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        live_session_id: sessionId,
        amount_cents: amountCents,
        donor_label: donorLabel,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `donation ${res.status}`);
    }
    const body = await res.json();
    setLog(`Live donation — ${formatUsdFromCents(amountCents)} → ${body.billing_entry?.codename}`);
    showToast(`Donation sent${body.revenue_routed ? " + revenue routed" : ""}`);
    await loadLiveStage({ quiet: true });
  } catch (e) {
    showToast(e.message || "Donation failed", true);
    setLog(e.message || "Live donation failed.");
  } finally {
    if (els.liveDonationBtn) els.liveDonationBtn.disabled = false;
  }
}

function startLiveStagePolling() {
  stopLiveStagePolling();
  loadLiveStage({ quiet: true }).catch(() => {});
  state.liveStageInterval = setInterval(() => {
    if (els.liveStagePanel?.open) loadLiveStage({ quiet: true }).catch(() => {});
  }, 8000);
}

function stopLiveStagePolling() {
  if (state.liveStageInterval) {
    clearInterval(state.liveStageInterval);
    state.liveStageInterval = null;
  }
}

function renderSwarmPayout(statusData, matrixData, cultureData, bonusData) {
  if (!els.swarmPayoutStatus) return;
  if (!statusData) {
    els.swarmPayoutStatus.textContent = "AI Swarm Payout unavailable.";
    return;
  }
  els.swarmPayoutStatus.textContent =
    `Phase ${statusData.deployment_phase ?? "?"} · ${statusData.roster_count ?? 0} agents · ` +
    `$${Number(statusData.empire_allocation_total_usd || 0).toLocaleString()} allocated · ` +
    `${statusData.promotion_policy ?? "promote"} / ${statusData.scaling_policy ?? "scale"}`;
  if (els.swarmMatrixText && matrixData?.matrix_text) {
    els.swarmMatrixText.textContent = matrixData.matrix_text;
  }
  if (els.swarmCulture && cultureData) {
    const sectionText = (cultureData.sections || [])
      .map((s) => `${s.heading}: ${s.body}`)
      .join(" ");
    els.swarmCulture.textContent =
      `${cultureData.title ?? "Culture"} — ${cultureData.hiring_authority ?? "king_grok"} hires, cap: ${cultureData.workforce_cap ?? "none"}. ${sectionText.slice(0, 420)}`;
  }
  if (els.swarmPerformanceBonus && bonusData) {
    els.swarmPerformanceBonus.innerHTML = "";
    (bonusData.recipients || []).forEach((item) => {
      const li = document.createElement("li");
      li.className = "swarm-bonus-item";
      li.textContent = `#${item.rank} ${item.name} — ${item.codename} · $${Number(item.bonus_usd).toLocaleString()}`;
      els.swarmPerformanceBonus.appendChild(li);
    });
  }
}

async function loadSwarmPayout({ quiet = false } = {}) {
  if (!els.swarmPayoutStatus) return null;
  try {
    const [statusRes, matrixRes, cultureRes, bonusRes] = await Promise.all([
      fetch(`${API}/workforce/swarm`),
      fetch(`${API}/workforce/swarm/matrix`),
      fetch(`${API}/workforce/swarm/culture`),
      fetch(`${API}/workforce/swarm/performance-bonus`),
    ]);
    if (!statusRes.ok) throw new Error(`swarm ${statusRes.status}`);
    const statusData = await statusRes.json();
    const matrixData = matrixRes.ok ? await matrixRes.json() : null;
    const cultureData = cultureRes.ok ? await cultureRes.json() : null;
    const bonusData = bonusRes.ok ? await bonusRes.json() : null;
    renderSwarmPayout(statusData, matrixData, cultureData, bonusData);
    if (!quiet) {
      setLog(`AI Swarm Payout — $${Number(statusData.empire_allocation_total_usd || 0).toLocaleString()} empire allocation`);
    }
    return statusData;
  } catch (e) {
    console.warn("Swarm payout fetch failed", e);
    renderSwarmPayout(null);
    if (!quiet) setLog("AI Swarm Payout unavailable.");
    return null;
  }
}

function startSwarmPayoutPolling() {
  stopSwarmPayoutPolling();
  loadSwarmPayout({ quiet: true }).catch(() => {});
  state.swarmPayoutInterval = setInterval(() => {
    if (els.swarmPayoutPanel?.open) loadSwarmPayout({ quiet: true }).catch(() => {});
  }, 15000);
}

function stopSwarmPayoutPolling() {
  if (state.swarmPayoutInterval) {
    clearInterval(state.swarmPayoutInterval);
    state.swarmPayoutInterval = null;
  }
}

function renderCrownCompletion(statusData, rankingsData, promoData, platinumData, giftsData, cosignData) {
  if (!els.crownCompletionStatus) return;
  if (!statusData) {
    els.crownCompletionStatus.textContent = "Crown Completion unavailable.";
    return;
  }
  const accepted = statusData.boss_sr_accepted_all ? " · Boss Sr. YES" : "";
  els.crownCompletionStatus.textContent =
    `v${statusData.app_version ?? "?"} · Phase ${statusData.deployment_phase ?? "?"} · ` +
    `${statusData.workers_awarded ?? 0} workers · $${Number(statusData.platinum_pool_value_usd || 0).toLocaleString()} platinum pool · ` +
    `Crown ${statusData.crown_complete ? "complete" : "pending"}${accepted}`;
  if (els.crownPhaseRankings && rankingsData) {
    els.crownPhaseRankings.innerHTML = "";
    (rankingsData.rankings || []).forEach((item) => {
      const li = document.createElement("li");
      li.className = "crown-ranking-item";
      li.textContent = `#${item.rank} Phase ${item.phase} — ${item.name} (${item.codename})`;
      els.crownPhaseRankings.appendChild(li);
    });
  }
  if (els.crownPromotion && promoData) {
    els.crownPromotion.textContent =
      `Promoted: ${promoData.codename} → ${promoData.promotion_title} · ${promoData.award_lb_before}lb → ${promoData.award_lb_after}lb`;
  }
  if (els.crownPlatinumAwards && platinumData) {
    els.crownPlatinumAwards.innerHTML = "";
    (platinumData.awards || []).slice(0, 8).forEach((award) => {
      const li = document.createElement("li");
      li.className = "crown-platinum-item";
      li.textContent = `${award.codename} — $${Number(award.platinum_value_usd).toLocaleString()} ${award.award_name}`;
      els.crownPlatinumAwards.appendChild(li);
    });
    if ((platinumData.awards || []).length > 8) {
      const more = document.createElement("li");
      more.className = "crown-platinum-more";
      more.textContent = `+${platinumData.awards.length - 8} more workers awarded`;
      els.crownPlatinumAwards.appendChild(more);
    }
  }
  if (els.crownBossSrGifts && giftsData) {
    els.crownBossSrGifts.innerHTML = "";
    (giftsData.gifts || []).slice(0, 5).forEach((gift) => {
      const li = document.createElement("li");
      li.className = "crown-gift-item";
      li.textContent = `${gift.title} — ${gift.description}`;
      els.crownBossSrGifts.appendChild(li);
    });
  }
  if (els.crownCosignList && cosignData) {
    els.crownCosignList.innerHTML = "";
    (cosignData.cosigns || []).slice(0, 5).forEach((entry) => {
      const li = document.createElement("li");
      li.className = "crown-cosign-item";
      li.textContent = `${entry.signer}: ${entry.message}`;
      els.crownCosignList.appendChild(li);
    });
  }
}

async function loadCrownCompletion({ quiet = false } = {}) {
  if (!els.crownCompletionStatus) return null;
  try {
    const [statusRes, rankingsRes, promoRes, platinumRes, giftsRes, cosignRes] = await Promise.all([
      fetch(`${API}/workforce/crown`),
      fetch(`${API}/workforce/crown/rankings`),
      fetch(`${API}/workforce/crown/promotion`),
      fetch(`${API}/workforce/crown/platinum`),
      fetch(`${API}/workforce/crown/gifts`),
      fetch(`${API}/workforce/crown/cosign`),
    ]);
    if (!statusRes.ok) throw new Error(`crown ${statusRes.status}`);
    const statusData = await statusRes.json();
    const rankingsData = rankingsRes.ok ? await rankingsRes.json() : null;
    const promoData = promoRes.ok ? await promoRes.json() : null;
    const platinumData = platinumRes.ok ? await platinumRes.json() : null;
    const giftsData = giftsRes.ok ? await giftsRes.json() : null;
    const cosignData = cosignRes.ok ? await cosignRes.json() : null;
    renderCrownCompletion(statusData, rankingsData, promoData, platinumData, giftsData, cosignData);
    if (!quiet) {
      setLog(`Crown Completion v${statusData.app_version} — ${statusData.workers_awarded} workers platinum awarded`);
    }
    return statusData;
  } catch (e) {
    console.warn("Crown Completion fetch failed", e);
    renderCrownCompletion(null);
    if (!quiet) setLog("Crown Completion unavailable.");
    return null;
  }
}

function startCrownCompletionPolling() {
  stopCrownCompletionPolling();
  loadCrownCompletion({ quiet: true }).catch(() => {});
  state.crownCompletionInterval = setInterval(() => {
    if (els.crownCompletionPanel?.open) loadCrownCompletion({ quiet: true }).catch(() => {});
  }, 12000);
}

function stopCrownCompletionPolling() {
  if (state.crownCompletionInterval) {
    clearInterval(state.crownCompletionInterval);
    state.crownCompletionInterval = null;
  }
}

async function grantAllCrownGifts() {
  if (!els.crownGrantAllBtn) return;
  els.crownGrantAllBtn.disabled = true;
  try {
    const res = await fetch(`${API}/workforce/crown/grant-all`, { method: "POST" });
    if (!res.ok) throw new Error(`grant-all ${res.status}`);
    const body = await res.json();
    showToast(body.message || "All gifts granted");
    await loadCrownCompletion({ quiet: true });
  } catch (e) {
    console.warn("Crown grant-all failed", e);
    showToast("Grant failed", true);
  } finally {
    els.crownGrantAllBtn.disabled = false;
  }
}

async function submitCrownCosign(event) {
  event.preventDefault();
  const signer = (els.crownCosignSigner?.value || "").trim();
  const message = (els.crownCosignMessage?.value || "").trim();
  if (!signer || !message) {
    showToast("Name and message required for co-sign", true);
    return;
  }
  try {
    const res = await fetch(`${API}/workforce/crown/cosign`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signer, message }),
    });
    if (!res.ok) throw new Error(`cosign ${res.status}`);
    if (els.crownCosignMessage) els.crownCosignMessage.value = "";
    showToast("Co-sign recorded — Crown Completion v1.0");
    await loadCrownCompletion({ quiet: true });
  } catch (e) {
    console.warn("Crown cosign failed", e);
    showToast("Co-sign failed", true);
  }
}

function renderSovereignScale(statusData, hardeningData, tenantsData, nodesData, obsData) {
  if (!els.sovereignScaleStatus) return;
  if (!statusData) {
    els.sovereignScaleStatus.textContent = "Sovereign Scale unavailable.";
    return;
  }
  els.sovereignScaleStatus.textContent =
    `Phase ${statusData.deployment_phase ?? "?"} · Tenants: ${statusData.tenants_active ?? 0} · ` +
    `Nodes: ${statusData.nodes_healthy ?? 0}/${statusData.nodes_total ?? 0} · ` +
    `Capacity: ${statusData.fleet_capacity_score ?? 0} · Scale ready: ${statusData.scale_ready ? "yes" : "no"}`;
  if (els.sovereignScaleHardening && hardeningData) {
    els.sovereignScaleHardening.textContent =
      `Hardening: ${hardeningData.passed ?? 0}/${hardeningData.count ?? 0} checks · ` +
      (hardeningData.checks || [])
        .filter((c) => !c.ok && c.required)
        .map((c) => c.label)
        .slice(0, 2)
        .join(", ") || "all required checks green";
  }
  if (els.sovereignScaleTenants) {
    els.sovereignScaleTenants.innerHTML = "";
    const tenants = Array.isArray(tenantsData?.tenants) ? tenantsData.tenants : [];
    tenants.slice(0, 6).forEach((tenant) => {
      const item = document.createElement("li");
      item.className = "sovereign-tenant-item";
      item.textContent = `${tenant.name} (${tenant.slug}) · ${tenant.status} · max ${tenant.max_sessions} sessions`;
      els.sovereignScaleTenants.appendChild(item);
    });
  }
  if (els.sovereignScaleNodes) {
    els.sovereignScaleNodes.innerHTML = "";
    const nodes = Array.isArray(nodesData?.nodes) ? nodesData.nodes : [];
    nodes.slice(0, 6).forEach((node) => {
      const item = document.createElement("li");
      item.className = "sovereign-node-item";
      item.textContent = `${node.hostname} · ${node.region} · ${node.role} · ${node.status} · cap ${node.capacity_score}`;
      els.sovereignScaleNodes.appendChild(item);
    });
  }
  if (els.sovereignScaleObservability && obsData) {
    const metrics = obsData.metrics || {};
    els.sovereignScaleObservability.textContent =
      `Observability — WebRTC: ${obsData.webrtc_active_sessions ?? 0} · Companions: ${obsData.companion_sessions ?? 0} · ` +
      `Perform: ${metrics.perform_requests ?? 0} · Tokens: ${metrics.tokens_streamed ?? 0}`;
  }
}

async function loadSovereignScale({ quiet = false } = {}) {
  if (!els.sovereignScaleStatus) return null;
  try {
    const [statusRes, hardeningRes, tenantsRes, nodesRes, obsRes] = await Promise.all([
      fetch(`${API}/workforce/scale`),
      fetch(`${API}/workforce/scale/hardening`),
      fetch(`${API}/workforce/scale/tenants?limit=10`),
      fetch(`${API}/workforce/scale/nodes?limit=10`),
      fetch(`${API}/workforce/scale/observability`),
    ]);
    if (!statusRes.ok) throw new Error(`scale ${statusRes.status}`);
    const statusData = await statusRes.json();
    const hardeningData = hardeningRes.ok ? await hardeningRes.json() : null;
    const tenantsData = tenantsRes.ok ? await tenantsRes.json() : null;
    const nodesData = nodesRes.ok ? await nodesRes.json() : null;
    const obsData = obsRes.ok ? await obsRes.json() : null;
    renderSovereignScale(statusData, hardeningData, tenantsData, nodesData, obsData);
    if (!quiet) {
      setLog(`Sovereign Scale — ${statusData.nodes_healthy ?? 0} healthy nodes · capacity ${statusData.fleet_capacity_score ?? 0}`);
    }
    return statusData;
  } catch (e) {
    console.warn("Sovereign Scale fetch failed", e);
    renderSovereignScale(null);
    if (!quiet) setLog("Sovereign Scale unavailable.");
    return null;
  }
}

function startSovereignScalePolling() {
  stopSovereignScalePolling();
  loadSovereignScale({ quiet: true }).catch(() => {});
  state.sovereignScaleInterval = setInterval(() => {
    if (els.sovereignScalePanel?.open) loadSovereignScale({ quiet: true }).catch(() => {});
  }, 10000);
}

function stopSovereignScalePolling() {
  if (state.sovereignScaleInterval) {
    clearInterval(state.sovereignScaleInterval);
    state.sovereignScaleInterval = null;
  }
}

async function dispatchAgentChainSmoke() {
  if (!state.agentTheaterMembers.length) {
    showToast("Load Agent Theater first", true);
    return;
  }
  const dispatchMember = state.agentTheaterMembers.find(
    (m) => m.codename === "AgentTheater_Dispatch_Sub_01"
  );
  const forgeMember = state.agentTheaterMembers.find(
    (m) => m.codename === "ProviderForge_Contract_Sub_01"
  );
  if (!dispatchMember || !forgeMember) {
    showToast("Chain members not found in roster", true);
    return;
  }
  if (els.agentChainSmokeBtn) els.agentChainSmokeBtn.disabled = true;
  try {
    const res = await fetch(`${API}/workforce/orchestration/chain`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: state.sessionId || null,
        steps: [
          {
            member_id: dispatchMember.id,
            prompt: "UI orchestration smoke — fleet scan",
            skill: "Workforce_TaskDispatch",
          },
          {
            member_id: forgeMember.id,
            prompt: "UI orchestration smoke — contract check",
            skill: "RunPod_ContractSmoke_LiveForge",
          },
        ],
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `chain ${res.status}`);
    }
    const chain = await res.json();
    setLog(`Orchestration chain ${chain.id} — ${chain.status}`);
    showToast(`Chain started — ${chain.id}`);
    await loadAgentTheater({ quiet: true });
  } catch (e) {
    showToast(e.message || "Chain dispatch failed", true);
    setLog(e.message || "Orchestration chain failed.");
  } finally {
    if (els.agentChainSmokeBtn) els.agentChainSmokeBtn.disabled = false;
  }
}

async function dispatchAgentTask(event) {
  event?.preventDefault?.();
  if (!els.agentMemberSelect || !els.agentTaskPrompt) return;
  const prompt = (els.agentTaskPrompt.value || "").trim();
  if (!prompt) {
    showToast("Enter a task prompt first", true);
    return;
  }
  if (els.agentDispatchBtn) els.agentDispatchBtn.disabled = true;
  try {
    const payload = {
      member_id: els.agentMemberSelect.value,
      prompt,
      skill: els.agentSkillSelect?.value || null,
      session_id: state.sessionId || null,
    };
    const res = await fetch(`${API}/workforce/theater/dispatch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `dispatch ${res.status}`);
    }
    const task = await res.json();
    els.agentTaskPrompt.value = "";
    setLog(`Dispatched to ${task.codename} (${task.skill})`);
    showToast(`Task queued — ${task.codename}`);
    await loadAgentTheater({ quiet: true });
  } catch (e) {
    showToast(e.message || "Dispatch failed", true);
    setLog(e.message || "Agent dispatch failed.");
  } finally {
    if (els.agentDispatchBtn) els.agentDispatchBtn.disabled = false;
  }
}

function startAgentTheaterPolling() {
  stopAgentTheaterPolling();
  loadAgentTheater({ quiet: true }).catch(() => {});
  state.agentTheaterInterval = setInterval(() => {
    if (els.agentTheaterPanel?.open) loadAgentTheater({ quiet: true }).catch(() => {});
  }, 3000);
}

function stopAgentTheaterPolling() {
  if (state.agentTheaterInterval) {
    clearInterval(state.agentTheaterInterval);
    state.agentTheaterInterval = null;
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
  updateSovereignControls();
  setPresenceLive(true);

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
        updatePresenceAura(state.bondScore);
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
  if (status === "error" || status === "unreachable") return "error";
  return "unknown";
}

function forgeDotClass(entry) {
  if (!entry) return "unknown";
  if (entry.contract_ok) return entry.probe_status === "ok" ? "ok" : "degraded";
  return "error";
}

function renderProviderStatus(data) {
  if (!els.providerStatus || !data) return;
  const items = [
    { key: "llm", label: "LLM" },
    { key: "tts", label: "TTS" },
    { key: "video", label: "Vid" },
  ];
  const tooltipLines = [];
  const forgeMode = !!data.forge_ok || items.some((item) => data[item.key]?.contract_ok !== undefined);
  if (forgeMode && data.forge_ok !== undefined) {
    tooltipLines.push(`Forge: ${data.forge_ok ? "OK" : "needs attention"}${data.live_smoke ? " (live smoke)" : ""}`);
  }
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
    const status = forgeMode ? forgeDotClass(info) : providerStatusClass(info.status);
    dot.className = `provider-dot ${status}`;
    row.appendChild(dot);
    els.providerStatus.appendChild(row);
    if (forgeMode && info.spec) {
      tooltipLines.push(
        `${item.label}: ${info.contract_ok ? "contract ok" : "contract fail"} · probe=${info.probe_status || "—"} · ${info.mode || "—"}`
      );
      if (info.message) tooltipLines.push(`  ${info.message}`);
      tooltipLines.push(`  ${info.spec.method} ${info.spec.endpoint_path}`);
    } else {
      tooltipLines.push(
        `${item.label}: ${info.status || info.probe_status || "unknown"} (${info.provider || info.mode || "—"})${info.detail ? ` — ${info.detail}` : ""}`
      );
    }
  });
  els.providerStatus.title = tooltipLines.join("\n");
}

async function refreshProviderStatus() {
  try {
    const res = await fetch(`${API}/providers/forge`);
    if (!res.ok) throw new Error(`providers/forge ${res.status}`);
    state.providerStatus = await res.json();
    renderProviderStatus(state.providerStatus);
    return;
  } catch (e) {
    console.warn("Provider forge fetch failed, trying /providers/status", e);
  }
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
  updateCeoCrownBadge(version);
}

function kgcStatusClass(status) {
  const normalized = String(status || "").toLowerCase();
  if (["ok", "healthy", "ready", "online", "active"].includes(normalized)) return "ok";
  if (["degraded", "warn", "warning", "partial"].includes(normalized)) return "warn";
  if (["error", "down", "offline", "failed"].includes(normalized)) return "error";
  return "";
}

function renderKgcDashboard(data) {
  if (!els.kgcDashboard) return;
  if (!data) {
    els.kgcDashboard.textContent = "KGC dashboard unavailable.";
    return;
  }

  const status = data.kgc_status ?? data.status ?? "unknown";
  const webrtcSessions = data.active_webrtc_sessions ?? data.webrtc_sessions?.length ?? 0;
  const companionSessions = data.companion_sessions_count ?? data.companion_sessions ?? 0;
  const avgBond = data.companion_avg_bond_score ?? data.avg_bond ?? "—";
  const performs =
    data.metrics_snapshot?.perform_requests ??
    data.performs ??
    data.perform_requests ??
    data.perform_count ??
    0;
  const uptime = formatUptime(data.uptime_seconds ?? data.uptime ?? 0);
  let providersOk = data.providers_ok_count ?? data.providers_ok;
  if (providersOk == null && data.providers_summary && typeof data.providers_summary === "object") {
    providersOk = Object.values(data.providers_summary).filter(
      (entry) => entry && typeof entry === "object" && entry.status === "ok"
    ).length;
  }
  if (providersOk == null) providersOk = "—";

  els.kgcDashboard.innerHTML = "";
  const stats = [
    { label: "Status", value: status, className: kgcStatusClass(status) },
    { label: "WebRTC", value: webrtcSessions },
    { label: "Companion", value: companionSessions },
    { label: "Avg bond", value: avgBond },
    { label: "Performs", value: performs },
    { label: "Uptime", value: uptime },
    { label: "Providers OK", value: providersOk, className: Number(providersOk) >= 3 ? "ok" : "" },
  ];

  stats.forEach((stat) => {
    const row = document.createElement("div");
    row.className = "kgc-stat";

    const label = document.createElement("span");
    label.className = "kgc-stat-label";
    label.textContent = stat.label;

    const value = document.createElement("span");
    value.className = `kgc-stat-value${stat.className ? ` ${stat.className}` : ""}`;
    value.textContent = String(stat.value);

    row.appendChild(label);
    row.appendChild(value);
    els.kgcDashboard.appendChild(row);
  });
}

async function loadKgcDashboard({ quiet = false } = {}) {
  if (!els.kgcDashboard) return null;
  try {
    const res = await fetch(`${API}/kgc/dashboard`);
    if (!res.ok) throw new Error(`kgc dashboard ${res.status}`);
    const data = await res.json();
    renderKgcDashboard(data);
    if (!quiet) {
      const status = data.kgc_status ?? data.status ?? "unknown";
      setLog(`KGC dashboard — ${status}`);
    }
    return data;
  } catch (e) {
    console.warn("KGC dashboard fetch failed", e);
    renderKgcDashboard(null);
    if (!quiet) setLog("KGC dashboard unavailable.");
    return null;
  }
}

async function pruneKgcFleet() {
  if (!window.confirm("Prune stale WebRTC and companion sessions from the fleet?")) return;
  if (els.kgcPruneBtn) els.kgcPruneBtn.disabled = true;
  try {
    const res = await fetch(`${API}/kgc/fleet/prune`, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || data.message || `prune failed (${res.status})`);
    }
    const pruned =
      data.pruned ??
      data.removed ??
      data.count ??
      data.stale_removed ??
      (typeof data.webrtc_pruned === "number" || typeof data.companion_pruned === "number"
        ? (Number(data.webrtc_pruned) || 0) + (Number(data.companion_pruned) || 0)
        : null);
    const msg =
      pruned != null
        ? `Pruned ${pruned} stale session${pruned === 1 ? "" : "s"}`
        : data.message || "Fleet prune complete";
    showToast(msg);
    setLog(`KGC prune — ${msg}`);
    await loadKgcDashboard({ quiet: true });
    await refreshActiveSessions();
  } catch (e) {
    console.error(e);
    showToast(e.message || "KGC prune failed", true);
    setLog(e.message || "KGC prune failed.");
  } finally {
    if (els.kgcPruneBtn) els.kgcPruneBtn.disabled = false;
  }
}

function startKgcPolling() {
  stopKgcPolling();
  loadKgcDashboard({ quiet: true }).catch(() => {});
  state.kgcDashboardInterval = setInterval(() => {
    if (els.kgcPanel?.open) loadKgcDashboard({ quiet: true }).catch(() => {});
  }, 90000);
}

function stopKgcPolling() {
  if (state.kgcDashboardInterval) {
    clearInterval(state.kgcDashboardInterval);
    state.kgcDashboardInterval = null;
  }
}

function isSovereignSessionActive() {
  return !!state.sessionId && (state.connected || state.sseMode);
}

function updateSovereignControls() {
  const active = isSovereignSessionActive();
  if (els.sovereignCloneBtn) els.sovereignCloneBtn.disabled = !active;
  if (els.sovereignBundleBtn) els.sovereignBundleBtn.disabled = !active;
}

function triggerJsonDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function formatAuditTimestamp(timestamp) {
  if (!timestamp) return "—";
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) return String(timestamp);
  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function renderSovereignAuditLog(entries) {
  if (!els.sovereignAuditLog) return;
  els.sovereignAuditLog.innerHTML = "";
  if (!Array.isArray(entries) || entries.length === 0) {
    const empty = document.createElement("li");
    empty.className = "sovereign-audit-empty";
    empty.textContent = "No audit entries yet.";
    els.sovereignAuditLog.appendChild(empty);
    return;
  }

  entries.forEach((entry) => {
    const item = document.createElement("li");
    item.className = "sovereign-audit-item";

    const time = document.createElement("span");
    time.className = "sovereign-audit-time";
    time.textContent = formatAuditTimestamp(entry.timestamp);

    const action = document.createElement("span");
    action.className = "sovereign-audit-action";
    action.textContent = entry.action || "action";

    const detail = document.createElement("span");
    detail.className = "sovereign-audit-detail";
    detail.textContent = entry.detail || "";

    const result = document.createElement("span");
    const resultValue = String(entry.result || "ok").toLowerCase();
    result.className = `sovereign-audit-result ${resultValue === "ok" ? "ok" : "error"}`;
    result.textContent = resultValue;

    item.appendChild(time);
    item.appendChild(action);
    item.appendChild(detail);
    item.appendChild(result);
    els.sovereignAuditLog.appendChild(item);
  });
}

function populateSovereignPolicyModes() {
  if (!els.sovereignPolicyMode) return;
  const modes = state.catalog?.relationship_modes || FALLBACK_CATALOG.relationship_modes;
  const current = els.sovereignPolicyMode.value;
  els.sovereignPolicyMode.innerHTML = '<option value="">(server default)</option>';
  modes.forEach((mode) => {
    const option = document.createElement("option");
    option.value = mode.id;
    option.textContent = mode.label || mode.id;
    els.sovereignPolicyMode.appendChild(option);
  });
  if (current) els.sovereignPolicyMode.value = current;
}

async function loadSovereignPolicies() {
  if (!els.sovereignPolicyMode && !els.sovereignPolicyPrompt) return null;
  try {
    const res = await fetch(`${API}/kgc/policies`);
    if (!res.ok) throw new Error(`policies ${res.status}`);
    const data = await res.json();
    populateSovereignPolicyModes();
    if (els.sovereignPolicyMode) {
      els.sovereignPolicyMode.value = data.default_relationship_mode || "";
    }
    if (els.sovereignPolicyPrompt) {
      els.sovereignPolicyPrompt.value = data.default_system_prompt || "";
    }
    return data;
  } catch (e) {
    console.warn("KGC policies fetch failed", e);
    return null;
  }
}

async function saveSovereignPolicies() {
  if (!els.sovereignPolicySaveBtn) return;
  els.sovereignPolicySaveBtn.disabled = true;
  try {
    const payload = {
      default_relationship_mode: els.sovereignPolicyMode?.value ?? "",
      default_system_prompt: els.sovereignPolicyPrompt?.value ?? "",
    };
    const res = await fetch(`${API}/kgc/policies`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || data.message || `policies save failed (${res.status})`);
    }
    showToast("Global policies saved");
    setLog("KGC policies updated.");
    await loadSovereignAuditLog({ quiet: true });
  } catch (e) {
    console.error(e);
    showToast(e.message || "Could not save policies", true);
    setLog(e.message || "KGC policies save failed.");
  } finally {
    if (els.sovereignPolicySaveBtn) els.sovereignPolicySaveBtn.disabled = false;
  }
}

async function loadSovereignAuditLog({ quiet = false } = {}) {
  if (!els.sovereignAuditLog) return null;
  try {
    const res = await fetch(`${API}/kgc/audit?limit=20`);
    if (!res.ok) throw new Error(`audit ${res.status}`);
    const data = await res.json();
    const entries = data.entries || [];
    renderSovereignAuditLog(entries);
    if (!quiet) setLog(`KGC audit — ${entries.length} recent action(s)`);
    return data;
  } catch (e) {
    console.warn("KGC audit fetch failed", e);
    renderSovereignAuditLog([]);
    if (!quiet) setLog("KGC audit log unavailable.");
    return null;
  }
}

async function loadSovereignPanel() {
  await Promise.all([
    loadSovereignPolicies(),
    loadSovereignAuditLog({ quiet: true }),
  ]);
  updateSovereignControls();
}

async function cloneSovereignSession() {
  if (!isSovereignSessionActive()) {
    showToast("Connect to clone the active session", true);
    return;
  }
  if (els.sovereignCloneBtn) els.sovereignCloneBtn.disabled = true;
  try {
    const res = await fetch(`${API}/companion/${state.sessionId}/clone`, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || data.message || `clone failed (${res.status})`);
    }
    const newId = data.session_id;
    if (!newId) throw new Error("Clone response missing session_id");
    const shortId = `${newId.slice(0, 8)}…`;
    showToast(`Cloned session → ${shortId}`);
    setLog(`Sovereign clone — new session ${newId}`);
    await loadSovereignAuditLog({ quiet: true });
    await refreshActiveSessions();
    if (window.confirm(`Clone created: ${newId}\n\nResume cloned session now?`)) {
      if (els.resumeInput) els.resumeInput.value = newId;
      if (els.resumeBtn) els.resumeBtn.disabled = false;
      await connect(newId);
    }
  } catch (e) {
    console.error(e);
    showToast(e.message || "Session clone failed", true);
    setLog(e.message || "Session clone failed.");
  } finally {
    updateSovereignControls();
  }
}

async function downloadSovereignBundle() {
  if (!state.sessionId) {
    showToast("Connect to download session bundle", true);
    return;
  }
  if (els.sovereignBundleBtn) els.sovereignBundleBtn.disabled = true;
  try {
    const res = await fetch(`${API}/companion/${state.sessionId}/bundle`);
    const data = await res.json().catch(() => null);
    if (!res.ok || !data) {
      throw new Error(
        (data && (data.detail || data.message)) || `bundle download failed (${res.status})`
      );
    }
    const blob = new Blob([`${JSON.stringify(data, null, 2)}\n`], {
      type: "application/json",
    });
    triggerJsonDownload(blob, `companion-bundle-${state.sessionId.slice(0, 8)}.json`);
    showToast("Session bundle downloaded");
    setLog(`Sovereign bundle — ${state.sessionId.slice(0, 8)}…`);
    await loadSovereignAuditLog({ quiet: true });
  } catch (e) {
    console.error(e);
    showToast(e.message || "Bundle download failed", true);
    setLog(e.message || "Bundle download failed.");
  } finally {
    updateSovereignControls();
  }
}

async function importSovereignSession(file) {
  if (!file) return;
  try {
    const text = await file.text();
    const payload = JSON.parse(text);
    const res = await fetch(`${API}/companion/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || data.message || `import failed (${res.status})`);
    }
    const importedId = data.session_id;
    if (!importedId) throw new Error("Import response missing session_id");
    showToast(`Imported session ${importedId.slice(0, 8)}…`);
    setLog(`Sovereign import — session ${importedId}`);
    await refreshActiveSessions();
    await loadSovereignAuditLog({ quiet: true });
    if (window.confirm(`Imported session: ${importedId}\n\nResume imported session now?`)) {
      if (els.resumeInput) els.resumeInput.value = importedId;
      if (els.resumeBtn) els.resumeBtn.disabled = false;
      await connect(importedId);
    }
  } catch (e) {
    console.error(e);
    showToast(e.message || "Session import failed", true);
    setLog(e.message || "Session import failed.");
  } finally {
    if (els.sovereignImportInput) els.sovereignImportInput.value = "";
  }
}

async function downloadSovereignFleetBackup() {
  if (els.sovereignFleetBackupBtn) els.sovereignFleetBackupBtn.disabled = true;
  try {
    const res = await fetch(`${API}/kgc/fleet/backup`);
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || data.message || `fleet backup failed (${res.status})`);
    }
    const text = await res.text();
    const blob = new Blob([text.endsWith("\n") ? text : `${text}\n`], {
      type: "application/json",
    });
    const stamp = new Date().toISOString().slice(0, 10);
    triggerJsonDownload(blob, `kgc-fleet-backup-${stamp}.json`);
    showToast("Fleet backup downloaded");
    setLog("Sovereign fleet backup downloaded.");
    await loadSovereignAuditLog({ quiet: true });
  } catch (e) {
    console.error(e);
    showToast(e.message || "Fleet backup failed", true);
    setLog(e.message || "Fleet backup failed.");
  } finally {
    if (els.sovereignFleetBackupBtn) els.sovereignFleetBackupBtn.disabled = false;
  }
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
    } else {
      const restoreRes = await fetch(`${API}/webrtc/session/${resumeSessionId}/restore`, {
        method: "POST",
      });
      if (!restoreRes.ok) {
        let detail = "Session not found for resume.";
        try {
          const errBody = await restoreRes.json();
          if (errBody && errBody.detail) detail = errBody.detail;
        } catch (_) {}
        throw new Error(detail);
      }
      const restored = await restoreRes.json();
      targetSessionId = restored.session_id || resumeSessionId;
      iceServers = restored.ice_servers || DEFAULT_ICE_SERVERS;
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
        updateSovereignControls();
        setPresenceLive(true);
        updateSendButtonState();
      } else if (pc.connectionState === "disconnected") {
        const wasPerforming = state.performing;
        state.connected = false;
        setPresenceLive(false);
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
  setPresenceLive(false);
  setPerformingPresence(false);
  updateSovereignControls();
  updateSendButtonState();
}

async function disconnect() {
  state.manualDisconnect = true;
  state.reconnecting = false;
  state.sseMode = false;
  state.webrtcFailCount = 0;
  if (state.micListening && state.speechRecognition) {
    try {
      state.speechRecognition.stop();
    } catch (_) {}
  }
  dismissMilestoneOverlay();

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
  setPerformingPresence(true);
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
        } else if (event.type === "bond_milestone") {
          showMilestoneCelebration(event);
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
    setPerformingPresence(false);
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

if (els.connectBtn) {
  els.connectBtn.addEventListener("click", () => connect());
}
if (els.sseModeBtn) {
  els.sseModeBtn.addEventListener("click", () => enterSseMode("manual"));
}
if (els.workforcePanel) {
  els.workforcePanel.addEventListener("toggle", () => {
    if (els.workforcePanel.open) loadWorkforceRoster().catch(() => {});
  });
}
if (els.swarmPayoutPanel) {
  els.swarmPayoutPanel.addEventListener("toggle", () => {
    if (els.swarmPayoutPanel.open) {
      startSwarmPayoutPolling();
    } else {
      stopSwarmPayoutPolling();
    }
  });
}
if (els.crownCompletionPanel) {
  els.crownCompletionPanel.addEventListener("toggle", () => {
    if (els.crownCompletionPanel.open) {
      startCrownCompletionPolling();
    } else {
      stopCrownCompletionPolling();
    }
  });
}
if (els.crownGrantAllBtn) {
  els.crownGrantAllBtn.addEventListener("click", () => {
    grantAllCrownGifts().catch(() => {});
  });
}
if (els.crownCosignForm) {
  els.crownCosignForm.addEventListener("submit", (event) => {
    submitCrownCosign(event).catch(() => {});
  });
}
if (els.sovereignScalePanel) {
  els.sovereignScalePanel.addEventListener("toggle", () => {
    if (els.sovereignScalePanel.open) {
      startSovereignScalePolling();
    } else {
      stopSovereignScalePolling();
    }
  });
}
if (els.liveStagePanel) {
  els.liveStagePanel.addEventListener("toggle", () => {
    if (els.liveStagePanel.open) {
      startLiveStagePolling();
    } else {
      stopLiveStagePolling();
    }
  });
}
if (els.liveCamForm) {
  els.liveCamForm.addEventListener("submit", (event) => {
    startLiveCam(event).catch(() => {});
  });
}
if (els.liveDonationForm) {
  els.liveDonationForm.addEventListener("submit", (event) => {
    sendLiveDonation(event).catch(() => {});
  });
}
if (els.characterForgePanel) {
  els.characterForgePanel.addEventListener("toggle", () => {
    if (els.characterForgePanel.open) {
      startCharacterForgePolling();
    } else {
      stopCharacterForgePolling();
    }
  });
}
if (els.characterOnboardForm) {
  els.characterOnboardForm.addEventListener("submit", (event) => {
    onboardNSMCharacter(event).catch(() => {});
  });
}
if (els.revenueForgePanel) {
  els.revenueForgePanel.addEventListener("toggle", () => {
    if (els.revenueForgePanel.open) {
      startRevenueForgePolling();
    } else {
      stopRevenueForgePolling();
    }
  });
}
if (els.revenueDonationForm) {
  els.revenueDonationForm.addEventListener("submit", (event) => {
    routeRevenueDonation(event).catch(() => {});
  });
}
if (els.agentLoungePanel) {
  els.agentLoungePanel.addEventListener("toggle", () => {
    if (els.agentLoungePanel.open) {
      startAgentLoungePolling();
    } else {
      stopAgentLoungePolling();
    }
  });
}
if (els.agentLoungeCommentForm) {
  els.agentLoungeCommentForm.addEventListener("submit", (event) => {
    postAgentLoungeComment(event).catch(() => {});
  });
}
if (els.agentTheaterPanel) {
  els.agentTheaterPanel.addEventListener("toggle", () => {
    if (els.agentTheaterPanel.open) {
      startAgentTheaterPolling();
    } else {
      stopAgentTheaterPolling();
    }
  });
}
if (els.agentMemberSelect) {
  els.agentMemberSelect.addEventListener("change", () => updateAgentSkillSelect());
}
if (els.agentDispatchForm) {
  els.agentDispatchForm.addEventListener("submit", (event) => {
    dispatchAgentTask(event).catch(() => {});
  });
}
if (els.agentChainSmokeBtn) {
  els.agentChainSmokeBtn.addEventListener("click", () => {
    dispatchAgentChainSmoke().catch(() => {});
  });
}
if (els.kgcPanel) {
  els.kgcPanel.addEventListener("toggle", () => {
    if (els.kgcPanel.open) {
      startKgcPolling();
      loadSovereignPanel().catch(() => {});
    } else {
      stopKgcPolling();
    }
  });
}
if (els.kgcPruneBtn) {
  els.kgcPruneBtn.addEventListener("click", () => {
    pruneKgcFleet().catch(() => {});
  });
}
if (els.sovereignCloneBtn) {
  els.sovereignCloneBtn.addEventListener("click", () => {
    cloneSovereignSession().catch(() => {});
  });
}
if (els.sovereignBundleBtn) {
  els.sovereignBundleBtn.addEventListener("click", () => {
    downloadSovereignBundle().catch(() => {});
  });
}
if (els.sovereignFleetBackupBtn) {
  els.sovereignFleetBackupBtn.addEventListener("click", () => {
    downloadSovereignFleetBackup().catch(() => {});
  });
}
if (els.sovereignImportInput) {
  els.sovereignImportInput.addEventListener("change", () => {
    const file = els.sovereignImportInput.files?.[0];
    if (file) importSovereignSession(file).catch(() => {});
  });
}
if (els.sovereignPolicySaveBtn) {
  els.sovereignPolicySaveBtn.addEventListener("click", () => {
    saveSovereignPolicies().catch(() => {});
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

if (els.disconnectBtn) {
  els.disconnectBtn.addEventListener("click", disconnect);
}
if (els.clearHistoryBtn) {
  els.clearHistoryBtn.addEventListener("click", clearHistory);
}
if (els.sendBtn) {
  els.sendBtn.addEventListener("click", () => {
    const prompt = els.promptInput.value.trim();
    if (!prompt) return;
    els.promptInput.value = "";
    perform(prompt);
  });
}

if (els.promptInput) {
  els.promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    els.sendBtn?.click();
  }
  });
}

if (els.milestoneOverlayDismiss) {
  els.milestoneOverlayDismiss.addEventListener("click", dismissMilestoneOverlay);
}
if (els.milestoneOverlay) {
  els.milestoneOverlay.addEventListener("click", (event) => {
    if (event.target === els.milestoneOverlay || event.target.classList.contains("milestone-overlay-backdrop")) {
      dismissMilestoneOverlay();
    }
  });
}

try {
  initVoiceInput();
} catch (e) {
  console.warn("Voice input setup failed", e);
}

if (els.milestoneOverlay) {
  els.milestoneOverlay.hidden = true;
}

setLog("Loading ProCharacters…");
resetTranscript();
updateMetrics();
updateMemoryIndicator();
updateBondMeter(0);
updateSendButtonState();
updateSovereignControls();
wireExamplePrompts();
initInnovationLanesDock();

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

async function fetchWithTimeout(url, options = {}, timeoutMs = 12000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function bootstrap() {
  if (state.bootstrapped) return;
  state.bootstrapped = true;

  setLog("Loading companion catalog…");
  await loadCatalog();
  await refreshProviderStatus();
  startProviderStatusPolling();

  try {
    const res = await fetchWithTimeout(`${API}/health`);
    if (!res.ok) throw new Error(`health ${res.status}`);
    const health = await res.json();
    state.appVersion = health.version || null;
    updateVersionBadge(state.appVersion);
    setLog(`${health.service} v${health.version} · pipeline ready`);
  } catch (e) {
    console.warn("Health check failed", e);
    setLog("API unreachable — start the server: uvicorn app.main:app --reload --port 8000");
    showToast("Server not reachable. Start uvicorn on port 8000.", true);
    return;
  }

  startServerMetricsPolling();
  await Promise.allSettled([
    refreshActiveSessions().catch((e) => {
      console.warn("Session list fetch failed", e);
    }),
    loadMilestones(),
    loadPresenceConfig(),
  ]);

  try {
    const last = localStorage.getItem("prochar_last_session_id");
    if (last && els.resumeInput && !els.resumeInput.value) {
      els.resumeInput.value = last;
      if (els.resumeBtn) els.resumeBtn.disabled = false;
    }
  } catch (_) {}

  // Auto-resume in background so the UI stays interactive.
  attemptAutoResumeOnLoad()
    .then((resumed) => {
      if (resumed) setLog("Auto-resumed last session.");
    })
    .catch((e) => console.warn("Auto-resume on load failed", e));
}

bootstrap().catch((e) => {
  console.error("Bootstrap failed", e);
  setLog("Bootstrap failed — check console and ensure the API server is running.");
  showToast("App failed to start — see log footer.", true);
});