const API = "/api/v1";

const state = {
  sessionId: null,
  pc: null,
  connected: false,
  performing: false,
  metrics: { tokens: 0, audio: 0, frames: 0 },
  statsInterval: null,
  icePollInterval: null,
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
      } else if (["failed", "closed", "disconnected"].includes(pc.connectionState)) {
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
    await disconnect();
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

async function disconnect() {
  els.disconnectBtn.disabled = true;
  els.sendBtn.disabled = true;
  els.connectBtn.disabled = false;

  stopStatsPolling();
  stopIceCandidatePolling();

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
  state.icePollInterval = null;
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