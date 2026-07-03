const API = "/api/v1";

const state = {
  sessionId: null,
  pc: null,
  connected: false,
  performing: false,
  metrics: { tokens: 0, audio: 0, frames: 0 },
  statsInterval: null,
  lastPrompt: null,
  connectionMode: 'new', // 'new' | 'resumed'
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
};

const DEFAULT_ICE_SERVERS = [{ urls: "stun:stun.l.google.com:19302" }];

function setStatus(text, live = false) {
  els.statusText.textContent = text;
  els.statusDot.classList.toggle("live", live);
  const pill = els.statusText ? els.statusText.parentElement : null;
  if (pill) pill.title = text;
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

function resetTranscript() {
  els.transcript.innerHTML = "";
  addBubble("system", "Connect to start. Badge click copies ID (toggles full view). Use ↻ for active sessions + Resume (works after reload).");
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

/**
 * Soft reconnect / renegotiate using existing PC (no full new RTCPeerConnection).
 * Useful for ICE blips or "disconnected" without page reload or full restart.
 * If iceRestart, requests ICE restart (new candidates/ufrags).
 * Falls back to full connect() if no usable PC.
 * Guidance: window.renegotiate(true) from console for manual soft reconnect.
 */
async function renegotiate(iceRestart = false) {
  if (!state.pc || !state.sessionId) {
    setLog("No active PC; falling back to full connect/resume.");
    return connect(state.sessionId || null);
  }
  const mode = iceRestart ? "ICE restart" : "renegotiate";
  setLog(`Starting soft ${mode} (re-using PC)...`);
  try {
    const offerOpts = iceRestart ? { iceRestart: true } : {};
    const offer = await state.pc.createOffer(offerOpts);
    await state.pc.setLocalDescription(offer);
    await waitForIceGathering(state.pc);

    const offerRes = await fetch(`${API}/webrtc/offer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: state.sessionId,
        type: "offer",
        sdp: state.pc.localDescription.sdp,
      }),
    });
    if (!offerRes.ok) {
      let d = "";
      try { d = (await offerRes.json()).detail || ""; } catch (_) {}
      throw new Error(`Renegotiate failed: ${offerRes.status} ${d}`);
    }
    const answer = await offerRes.json();
    if (answer.session_id && answer.session_id !== state.sessionId) {
      state.sessionId = answer.session_id;
      if (els.resumeInput) els.resumeInput.value = state.sessionId;
      setupSessionBadgeCopy(state.sessionId);
    }
    await state.pc.setRemoteDescription({ type: "answer", sdp: answer.sdp });
    setLog(`Soft ${mode} complete.`);
    showToast(iceRestart ? "ICE restart done" : "Renegotiated");
    // re-arm auto attempt flag
    state.reconnectAttempted = false;
  } catch (e) {
    console.warn("Soft reconnect failed:", e);
    setLog("Soft reconnect failed: " + (e.message || e) + ". Use Resume after reload or Connect.");
    showToast("Soft reconnect failed", true);
    // do not auto disconnect; let user decide or connection may recover
  }
}

async function connect(resumeSessionId = null) {
  if (state.connected) return;

  const isResume = !!resumeSessionId;
  state.connectionMode = isResume ? "resumed" : "new";
  setStatus(isResume ? "Resuming…" : "Connecting…");
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
    state.reconnectAttempted = false;
    // Soft reconnect support + guidance (no full new PC if possible):
    // Call window.renegotiate() or window.renegotiate(true) from console for ICE restart without reload.
    try { window.renegotiate = renegotiate; window.__pc = pc; window.__sessionId = state.sessionId; } catch (_) {}

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

    // Track ICE state separately for richer display
    let currentIceState = pc.iceConnectionState || "new";
    function updateConnLabel() {
      els.connectionLabel.textContent = `${pc.connectionState}/ice:${currentIceState}`;
    }
    updateConnLabel();

    // Click ICE label to attempt soft reconnect (re-uses PC) when stuck disconnected
    if (els.connectionLabel) {
      els.connectionLabel.style.cursor = "pointer";
      els.connectionLabel.title = "Click to attempt soft reconnect (ICE restart) if disconnected";
      els.connectionLabel.onclick = () => {
        if (state.pc && !state.connected) {
          renegotiate(true).catch(() => {});
        } else {
          setLog("Soft reconnect: only useful when disconnected but session active. Or use Resume after reload.");
        }
      };
    }

    pc.onconnectionstatechange = () => {
      updateConnLabel();
      if (pc.connectionState === "connected") {
        state.connected = true;
        state.reconnectAttempted = false;
        const statusText = state.connectionMode === "resumed" ? "Resumed" : "Live";
        setStatus(statusText, true);
        setLog(
          state.connectionMode === "resumed"
            ? "WebRTC resumed and connected."
            : "WebRTC connected. Send a prompt to perform."
        );
        startStatsPolling();
        try {
          localStorage.setItem("prochar_last_session_id", state.sessionId);
        } catch (_) {}
        if (els.resumeInput) els.resumeInput.value = state.sessionId;
      } else if (["failed", "closed", "disconnected"].includes(pc.connectionState)) {
        const wasPerforming = state.performing;
        state.connected = false;
        const isResumedMode = state.connectionMode === "resumed";
        let label = pc.connectionState === "disconnected" && isResumedMode
          ? "Resumed but disconnected"
          : (pc.connectionState === "disconnected" ? "Disconnected" : "Failed");
        setStatus(label);
        if (wasPerforming) {
          setLog("Connection lost during stream. Last partial response kept.");
          showToast("Disconnected during stream", true);
        } else if (isResumedMode && pc.connectionState === "disconnected") {
          setLog("Resumed but disconnected (ICE or network). Use soft reconnect or re-Resume after reload.");
        }
        stopStatsPolling();
      }
    };

    pc.oniceconnectionstatechange = () => {
      currentIceState = pc.iceConnectionState || currentIceState;
      updateConnLabel();
      if ((pc.iceConnectionState === "failed" || pc.iceConnectionState === "disconnected") && state.pc === pc) {
        if (!state.reconnectAttempted) {
          state.reconnectAttempted = true;
          setLog("ICE " + pc.iceConnectionState + " — attempting soft reconnect (re-use PC)...");
          // auto soft attempt (non blocking)
          setTimeout(() => {
            if (state.pc === pc && !state.connected) {
              renegotiate(true).catch(() => {});
            }
          }, 800);
        } else {
          setStatus(state.connectionMode === "resumed" ? "Resumed but disconnected" : "Disconnected");
        }
      }
    };

    pc.onicegatheringstatechange = () => {
      // optional: could surface but conn/ice label sufficient
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
      let detail = "";
      try {
        const errBody = await offerRes.json();
        detail = errBody && errBody.detail ? errBody.detail : "";
      } catch (_) {}
      if (isResume) {
        // Better handling for resume offer fail e.g. session gone/closed on server.
        const msg = `Resume failed (${offerRes.status}): ${detail || "session not found"}`;
        setLog(msg);
        showToast("Resume failed — session gone?", true);
        addBubble("system", "Resume offer rejected (session may be gone/expired). Click Connect for a fresh session. ID cleared.");
        // partial cleanup; leave resumeInput for user, do NOT full disconnect or throw (prevents losing UI)
        if (pc) {
          try { pc.close(); } catch (_) {}
        }
        state.pc = null;
        state.sessionId = null;
        state.connected = false;
        state.connectionMode = "new";
        els.connectBtn.disabled = false;
        if (els.disconnectBtn) els.disconnectBtn.disabled = true;
        if (els.sendBtn) els.sendBtn.disabled = true;
        if (els.resumeBtn) els.resumeBtn.disabled = !!(els.resumeInput && els.resumeInput.value.trim());
        if (els.sessionsSelect) els.sessionsSelect.disabled = false;
        // keep resume input value so user can see what failed or try list again
        return;
      }
      throw new Error(detail || "SDP offer exchange failed.");
    }

    const answer = await offerRes.json();

    // Always adopt server's session id (handles any internal recreate/aliasing)
    if (answer && answer.session_id) {
      const returnedId = answer.session_id;
      if (returnedId !== state.sessionId) {
        const prev = state.sessionId;
        state.sessionId = returnedId;
        setupSessionBadgeCopy(state.sessionId);
        if (els.resumeInput) els.resumeInput.value = state.sessionId;
        if (isResume) {
          setLog(`Adopted server session id ${returnedId.slice(0,8)} (was ${prev ? prev.slice(0,8) : "new"})`);
        }
      }
    }

    await pc.setRemoteDescription({ type: "answer", sdp: answer.sdp });
    els.avatarVideo.muted = false;

    els.disconnectBtn.disabled = false;
    els.sendBtn.disabled = false;
    if (els.resumeBtn) els.resumeBtn.disabled = true;
    if (els.sessionsSelect) els.sessionsSelect.disabled = false;

    const resumeTargetMatch = isResume && resumeSessionId && state.sessionId === resumeSessionId;
    if (isResume) {
      state.connectionMode = "resumed";
      setStatus("Resumed (connecting…)");
      addBubble("system", resumeTargetMatch ? "Session resumed." : "Resume adopted different/new session id.");
      setLog("Resume signaling complete. Waiting for connection (ICE may still negotiate).");
    } else {
      addBubble("system", "Session ready. Avatar tracks attached.");
      setLog("WebRTC signaling complete. Copy badge ID to test resume after reload.");
    }
  } catch (error) {
    console.error(error);
    await disconnect();
    setStatus("Error");
    setLog(error.message || "Connection failed.");
    showToast(error.message || "Connection failed.", true);
    els.connectBtn.disabled = false;
    if (els.resumeBtn) els.resumeBtn.disabled = !!(els.resumeInput && els.resumeInput.value.trim());
    if (els.sessionsSelect) els.sessionsSelect.disabled = false;
  }
}

async function disconnect() {
  els.disconnectBtn.disabled = true;
  els.sendBtn.disabled = true;
  els.connectBtn.disabled = false;

  stopStatsPolling();

  if (state.sessionId) {
    // Leave the server session alive so it can be resumed (paste the ID shown in the badge).
    // Use the DELETE /webrtc/session/{id} explicitly or refresh server to end it.
    console.debug("Leaving session alive for potential resume:", state.sessionId);
  }

  if (state.pc) {
    state.pc.getSenders().forEach((sender) => sender.track?.stop());
    state.pc.close();
  }

  state.pc = null;
  state.sessionId = null;
  state.connected = false;
  state.performing = false;
  state.connectionMode = "new";
  state.reconnectAttempted = false;
  state.metrics = { tokens: 0, audio: 0, frames: 0 };
  updateMetrics();
  if (els.webrtcStats) els.webrtcStats.textContent = "WebRTC: —";

  els.avatarVideo.srcObject = null;
  els.sessionLabel.textContent = "—";
  els.sessionLabel.title = "";
  els.sessionLabel.style.cursor = "";
  els.sessionLabel.onclick = null;
  _fullIdVisible = false;
  els.connectionLabel.textContent = "idle";
  setStatus("Idle");
  setLog("Disconnected. (server session may still be resumable)");
  if (els.resumeBtn) els.resumeBtn.disabled = !(els.resumeInput && els.resumeInput.value.trim());
  if (els.connectBtn) els.connectBtn.disabled = false;
  if (els.sessionsSelect) els.sessionsSelect.disabled = false;
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