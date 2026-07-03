const API = "/api/v1";

const state = {
  sessionId: null,
  pc: null,
  connected: false,
  performing: false,
  metrics: { tokens: 0, audio: 0, frames: 0 },
};

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
};

const DEFAULT_ICE_SERVERS = [{ urls: "stun:stun.l.google.com:19302" }];

function setStatus(text, live = false) {
  els.statusText.textContent = text;
  els.statusDot.classList.toggle("live", live);
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
  bubble.textContent = text;
  els.transcript.appendChild(bubble);
  els.transcript.scrollTop = els.transcript.scrollHeight;
  return bubble;
}

function resetTranscript() {
  els.transcript.innerHTML = "";
  addBubble("system", "Connect to start. After connect, copy the ID (or use ↻ + Resume after reload).");
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

async function connect(resumeSessionId = null) {
  if (state.connected) return;

  const isResume = !!resumeSessionId;
  setStatus("Connecting…");
  setLog(isResume ? `Resuming session ${resumeSessionId.slice(0,8)}…` : "Creating WebRTC session…");
  els.connectBtn.disabled = true;
  if (els.resumeBtn) els.resumeBtn.disabled = true;

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
    els.sessionLabel.textContent = state.sessionId.slice(0, 8);
    els.sessionLabel.title = state.sessionId + " (click to copy)";
    els.sessionLabel.style.cursor = "pointer";
    els.sessionLabel.onclick = () => {
      navigator.clipboard.writeText(state.sessionId).then(() => {
        const orig = els.sessionLabel.textContent;
        els.sessionLabel.textContent = "copied!";
        if (els.resumeInput) els.resumeInput.value = state.sessionId;
        setLog("Session ID copied to clipboard. Use it after reload to resume.");
        setTimeout(() => {
          if (els.sessionLabel) els.sessionLabel.textContent = orig;
        }, 1200);
      }).catch(() => {
        // fallback
        if (els.resumeInput) els.resumeInput.value = state.sessionId;
        setLog("Session ID: " + state.sessionId);
      });
    };

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
        setStatus("Live", true);
        setLog("WebRTC connected. Send a prompt to perform.");
      } else if (["failed", "closed", "disconnected"].includes(pc.connectionState)) {
        state.connected = false;
        setStatus("Disconnected");
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

    if (!offerRes.ok) throw new Error("SDP offer exchange failed.");
    const answer = await offerRes.json();

    await pc.setRemoteDescription({ type: "answer", sdp: answer.sdp });
    els.avatarVideo.muted = false;

    els.disconnectBtn.disabled = false;
    els.sendBtn.disabled = false;
    if (els.resumeBtn) els.resumeBtn.disabled = true;
    // Prefill resume field with full ID so it's easy to copy for reload/resume testing
    if (els.resumeInput) {
      els.resumeInput.value = state.sessionId;
    }
    addBubble("system", isResume ? "Session resumed." : "Session ready. Avatar tracks attached.");
    setLog("Waiting for WebRTC connection… Copy the ID above to test resume after reload.");
  } catch (error) {
    console.error(error);
    await disconnect();
    setStatus("Error");
    setLog(error.message || "Connection failed.");
    els.connectBtn.disabled = false;
    if (els.resumeBtn) els.resumeBtn.disabled = false;
  }
}

async function disconnect() {
  els.disconnectBtn.disabled = true;
  els.sendBtn.disabled = true;
  els.connectBtn.disabled = false;

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
  state.metrics = { tokens: 0, audio: 0, frames: 0 };
  updateMetrics();

  els.avatarVideo.srcObject = null;
  els.sessionLabel.textContent = "—";
  els.sessionLabel.title = "";
  els.sessionLabel.style.cursor = "";
  els.sessionLabel.onclick = null;
  els.connectionLabel.textContent = "idle";
  setStatus("Idle");
  setLog("Disconnected.");
  if (els.resumeBtn) els.resumeBtn.disabled = !(els.resumeInput && els.resumeInput.value.trim());
  if (els.connectBtn) els.connectBtn.disabled = false;
}

async function perform(prompt) {
  if (!state.sessionId || state.performing) return;

  state.performing = true;
  state.metrics = { tokens: 0, audio: 0, frames: 0 };
  updateMetrics();
  els.sendBtn.disabled = true;
  addBubble("user", prompt);

  const assistantBubble = addBubble("assistant", "");
  let assistantText = "";

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
      throw new Error("Perform request failed.");
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

        const event = JSON.parse(line.slice(5).trim());
        if (event.type === "token") {
          assistantText += event.content;
          assistantBubble.textContent = assistantText;
          state.metrics.tokens += 1;
        } else if (event.type === "audio") {
          state.metrics.audio += 1;
        } else if (event.type === "video_frame") {
          state.metrics.frames += 1;
        } else if (event.type === "error" || event.type === "tts_error" || event.type === "video_error") {
          setLog(event.message);
        }
        updateMetrics();
      }

      els.transcript.scrollTop = els.transcript.scrollHeight;
    }

    setLog("Perform stream complete.");
  } catch (error) {
    console.error(error);
    assistantBubble.textContent = assistantText || "(no response)";
    setLog(error.message || "Perform failed.");
  } finally {
    state.performing = false;
    if (state.connected) els.sendBtn.disabled = false;
  }
}

els.connectBtn.addEventListener("click", () => connect());

async function refreshActiveSessions() {
  try {
    const res = await fetch(`${API}/webrtc/sessions`);
    if (!res.ok) throw new Error("Failed to list sessions");
    const data = await res.json();
    const list = (data.sessions || []).map(s => s.slice(0,8)).join(", ") || "none";
    setLog(`Active sessions (${data.count}): ${list}`);
    if (els.resumeInput && data.sessions && data.sessions.length && !els.resumeInput.value) {
      els.resumeInput.value = data.sessions[0];
    }
    if (els.resumeBtn) els.resumeBtn.disabled = !(els.resumeInput && els.resumeInput.value.trim());
  } catch (e) {
    setLog("Could not fetch active sessions.");
  }
}

if (els.refreshSessionsBtn) {
  els.refreshSessionsBtn.addEventListener("click", refreshActiveSessions);
}
if (els.resumeBtn) {
  els.resumeBtn.addEventListener("click", () => {
    const id = (els.resumeInput?.value || "").trim();
    if (id) connect(id);
  });
  if (els.resumeInput) {
    els.resumeInput.addEventListener("input", () => {
      els.resumeBtn.disabled = !els.resumeInput.value.trim();
    });
    els.resumeInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const id = els.resumeInput.value.trim();
        if (id) connect(id);
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
fetch(`${API}/health`)
  .then((res) => res.json())
  .then((health) => {
    setLog(`${health.service} v${health.version} · mock pipeline ready`);
    // Try to surface active sessions for easy resume
    if (els.refreshSessionsBtn) refreshActiveSessions();
  })
  .catch(() => setLog("API unreachable."));