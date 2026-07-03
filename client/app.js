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
};

let _fullIdVisible = false;

const els = {
  statusDot: document.getElementById("statusDot"),
  statusText: document.getElementById("statusText"),
  connectBtn: document.getElementById("connectBtn"),
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

function getCompanionConfigPayload() {
  return {
    avatar_id: els.avatarSelect?.value || "default",
    voice: els.voiceSelect?.value || "default",
    system_prompt: (els.systemPromptInput?.value || "").trim() || null,
  };
}

function applyCompanionConfig(config) {
  if (!config) return;
  if (els.avatarSelect && config.avatar_id) els.avatarSelect.value = config.avatar_id;
  if (els.voiceSelect && config.voice) els.voiceSelect.value = config.voice;
  if (els.systemPromptInput && config.system_prompt != null) {
    els.systemPromptInput.value = config.system_prompt;
  }
  if (typeof config.turn_count === "number") {
    state.turnCount = config.turn_count;
    updateMemoryIndicator();
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
  "Connect to start. Badge click copies ID (toggles full view). Use ↻ for active sessions + Resume (works after reload).";

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
  const { autoReconnect = false } = options;
  if (state.connected || (state.reconnecting && !autoReconnect)) return;

  const isResume = !!resumeSessionId;
  if (!autoReconnect) state.manualDisconnect = false;
  state.connectionMode = isResume ? "resumed" : "new";
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
        const statusText = state.connectionMode === "resumed" ? "Resumed" : "Connected";
        setStatus(statusText, true);
        setLog(
          state.connectionMode === "resumed"
            ? "WebRTC resumed. Send a prompt to perform."
            : "WebRTC connected. Send a prompt to perform."
        );
        startStatsPolling();
        try {
          localStorage.setItem("prochar_last_session_id", state.sessionId);
        } catch (_) {}
        if (els.resumeInput) els.resumeInput.value = state.sessionId;
        if (els.clearHistoryBtn) els.clearHistoryBtn.disabled = false;
      } else if (pc.connectionState === "disconnected") {
        const wasPerforming = state.performing;
        state.connected = false;
        stopStatsPolling();
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

  stopStatsPolling();
  stopIceCandidatePolling();

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
    updateMemoryIndicator();
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
    clearTranscriptKeepSystem();
    addBubble("system", "Conversation history cleared.");
    setLog("Server history cleared.");
    showToast("History cleared");
  } catch (e) {
    console.error(e);
    setLog(e.message || "Could not clear history.");
    showToast(e.message || "Could not clear history", true);
  } finally {
    if (state.connected && els.clearHistoryBtn) els.clearHistoryBtn.disabled = false;
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
            if (state.connected && !state.performing) setStatus(state.connectionMode === "resumed" ? "Resumed" : "Connected", true);
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
    if (state.connected) {
      els.sendBtn.disabled = false;
      if (!hadError) setStatus(state.connectionMode === "resumed" ? "Resumed" : "Connected", true);
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
      if (state.connected && !state.performing) {
        // send directly
        perform(p);
      } else {
        els.promptInput.value = p;
        els.promptInput.focus();
        setLog("Connect or resume first, then send (or click example again after).");
      }
    });
  });
}

els.connectBtn.addEventListener("click", () => connect());

async function fetchActiveSessions() {
  const res = await fetch(`${API}/webrtc/sessions`);
  if (!res.ok) throw new Error("Failed to list sessions");
  return await res.json();
}

async function refreshActiveSessions() {
  try {
    const data = await fetchActiveSessions();
    const list = (data.sessions || []).map((s) => s.slice(0, 8)).join(", ") || "none";
    let detailStr = "";
    if (Array.isArray(data.details) && data.details.length) {
      detailStr = " · states:" + data.details.slice(0, 2).map((d) => `${String(d.session_id || "").slice(0,4)}:${d.connection_state || d.ice_connection_state || "?"}`).join(",");
    }
    setLog(`Active sessions (${data.count || 0}): ${list}${detailStr}`);

    // populate dropdown for improved resume UX
    if (els.sessionsSelect) {
      els.sessionsSelect.innerHTML = '<option value="">— active sessions —</option>';
      (data.sessions || []).forEach((id) => {
        const opt = document.createElement("option");
        opt.value = id;
        opt.textContent = `${id.slice(0, 8)}…${id.slice(-4)}`;
        els.sessionsSelect.appendChild(opt);
      });
      els.sessionsSelect.disabled = !data.sessions || data.sessions.length === 0;
    }

    // auto-suggest: prefer stored last, else first
    const lastStored = (() => {
      try { return localStorage.getItem("prochar_last_session_id"); } catch (_) { return null; }
    })();
    if (els.resumeInput) {
      if (lastStored && (data.sessions || []).includes(lastStored)) {
        els.resumeInput.value = lastStored;
        setLog(`Active sessions (${data.count || 0}): ${list} · Last session active — click Resume to continue after reload.`);
      } else if (!els.resumeInput.value && data.sessions && data.sessions.length) {
        els.resumeInput.value = data.sessions[0];
      }
    }
    if (els.resumeBtn) {
      els.resumeBtn.disabled = !(els.resumeInput && els.resumeInput.value.trim());
    }
  } catch (e) {
    setLog("Could not fetch active sessions.");
    if (els.sessionsSelect) els.sessionsSelect.disabled = true;
  }
}

if (els.refreshSessionsBtn) {
  els.refreshSessionsBtn.addEventListener("click", refreshActiveSessions);
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
      // client-side quick check using list (best effort; connect also handles not-found)
      fetchActiveSessions()
        .then((d) => {
          if (d.sessions && !d.sessions.includes(id)) {
            showToast("Session not in active list (may be gone). Will attempt graceful fallback.", true);
          }
          connect(id);
        })
        .catch(() => connect(id)); // proceed anyway, connect detects via returned id
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
wireExamplePrompts();

fetch(`${API}/health`)
  .then((res) => res.json())
  .then((health) => {
    setLog(`${health.service} v${health.version} · mock pipeline ready`);
    // populate active sessions + auto-suggest last for resume after reload
    refreshActiveSessions().then(() => {
      const last = (() => {
        try { return localStorage.getItem("prochar_last_session_id"); } catch (_) { return null; }
      })();
      if (last && els.resumeInput && !els.resumeInput.value) {
        els.resumeInput.value = last;
        if (els.resumeBtn) els.resumeBtn.disabled = false;
      }
    });
  })
  .catch(() => setLog("API unreachable."));

// Bonus: allow re-sending last prompt quickly via console or future UI; also prefill if stored
try {
  const last = localStorage.getItem("prochar_last_session_id");
  if (last && els.resumeInput && !els.resumeInput.value) {
    els.resumeInput.value = last;
    if (els.resumeBtn) els.resumeBtn.disabled = false;
  }
} catch (_) {}