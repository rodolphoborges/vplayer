/**
 * Auto-Stream Valorant Clean Player
 * Continuous playback engine, YouTube IFrame API integration, and interactive timeline.
 */

// Application State
const state = {
  player: null,
  isPlayerReady: false,
  isYouTubeAPIReady: false,
  isPlaying: false,
  autoSkipEnabled: true,
  matchData: null,
  currentMapIndex: 0,
  currentRoundIndex: 0,
  monitorTimer: null,
  isSeeking: false,
  lastSkipTime: 0,
};

// Win Type Icons Map
const WIN_ICONS = {
  elim: "⚔️",
  defuse: "🛡️",
  detonation: "💥",
  time: "⏱️"
};

// Format seconds to MM:SS or HH:MM:SS
function formatTime(seconds) {
  if (isNaN(seconds) || seconds < 0) return "00:00";
  const s = Math.floor(seconds);
  const hrs = Math.floor(s / 3600);
  const mins = Math.floor((s % 3600) / 60);
  const secs = s % 60;
  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

// Convert MM:SS or seconds string to integer seconds
function parseTimeToSeconds(timeStr) {
  if (typeof timeStr === "number") return timeStr;
  if (!timeStr) return 0;
  const parts = timeStr.toString().trim().split(":").map(Number);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return Number(timeStr) || 0;
}

// Extract YouTube ID from string
function extractYouTubeId(urlOrId) {
  if (!urlOrId) return "B5G9Qpv31_o";
  const str = urlOrId.trim();
  if (/^[a-zA-Z0-9_-]{11}$/.test(str)) return str;
  const match = str.match(/(?:v=|\/)([a-zA-Z0-9_-]{11})(?:[&?]|$)/);
  return match ? match[1] : str;
}

// ---------------------------------------------------------------------------
// YouTube IFrame API Initialization
// ---------------------------------------------------------------------------
window.onYouTubeIframeAPIReady = function() {
  state.isYouTubeAPIReady = true;
  if (state.matchData) {
    const videoId = extractYouTubeId(state.matchData.video_id || state.matchData.video_url || "B5G9Qpv31_o");
    const firstRound = getCurrentRound();
    const startSec = firstRound ? firstRound.start : 0;
    createOrUpdatePlayer(videoId, startSec);
  }
};

function createOrUpdatePlayer(videoId, startSeconds = 0) {
  if (!window.YT || typeof YT.Player !== "function") {
    console.warn("YouTube API not ready yet, will initialize on callback.");
    return;
  }

  if (state.player && typeof state.player.loadVideoById === "function") {
    try {
      state.player.loadVideoById({
        videoId: videoId,
        startSeconds: startSeconds
      });
      return;
    } catch (e) {
      console.warn("loadVideoById error:", e);
    }
  }

  try {
    state.player = new YT.Player("player", {
      height: "100%",
      width: "100%",
      videoId: videoId,
      playerVars: {
        autoplay: 0,
        controls: 1,
        modestbranding: 1,
        rel: 0,
        start: startSeconds,
        enablejsapi: 1
      },
      events: {
        onReady: onPlayerReady,
        onStateChange: onPlayerStateChange,
        onError: onPlayerError
      }
    });
  } catch (err) {
    console.error("Error instantiating YT.Player:", err);
  }
}

function onPlayerReady(event) {
  state.isPlayerReady = true;
  startPlaybackMonitor();
  updateUI();
  
  // Jump to first round start
  const currentRound = getCurrentRound();
  if (currentRound && currentRound.start) {
    try {
      state.player.seekTo(currentRound.start, true);
    } catch (e) {}
  }
}

function updatePlayPauseIcon(isPlaying) {
  const playIcon = document.querySelector(".icon-play");
  const pauseIcon = document.querySelector(".icon-pause");
  if (playIcon && pauseIcon) {
    playIcon.style.display = isPlaying ? "none" : "block";
    pauseIcon.style.display = isPlaying ? "block" : "none";
  }
}

function onPlayerStateChange(event) {
  if (event.data === YT.PlayerState.PLAYING) {
    state.isPlaying = true;
    updatePlayPauseIcon(true);
  } else if (event.data === YT.PlayerState.PAUSED || event.data === YT.PlayerState.ENDED) {
    state.isPlaying = false;
    updatePlayPauseIcon(false);
  }
}

function onPlayerError(event) {
  console.warn("YouTube Player error:", event.data);
}

// ---------------------------------------------------------------------------
// Continuous Playback Loop & Auto-Skip Engine
// ---------------------------------------------------------------------------
function startPlaybackMonitor() {
  if (state.monitorTimer) clearInterval(state.monitorTimer);

  // Run at 60ms interval for precision
  state.monitorTimer = setInterval(() => {
    if (!state.isPlayerReady || !state.player || typeof state.player.getCurrentTime !== "function") {
      return;
    }

    try {
      const currentTime = state.player.getCurrentTime();
      updateScrubberAndTimer(currentTime);

      if (!state.autoSkipEnabled || state.isSeeking) return;

      const currentRound = getCurrentRound();
      if (!currentRound) return;

      // Only trigger round end if player is actually inside or past this round
      if (currentTime >= currentRound.start && currentTime >= currentRound.end - 0.2) {
        handleRoundEnd(currentRound, currentTime);
      } else if (currentTime < currentRound.start - 5) {
        syncCurrentRoundToTime(currentTime);
      }
    } catch (e) {
      // Ignored during buffering
    }
  }, 60);
}

function handleRoundEnd(currentRound, currentTime) {
  const mapObj = getCurrentMap();
  if (!mapObj) return;

  const now = Date.now();
  if (now - state.lastSkipTime < 800) return;
  state.lastSkipTime = now;

  const rounds = mapObj.rounds || [];
  const nextRoundIndex = state.currentRoundIndex + 1;

  if (nextRoundIndex < rounds.length) {
    // Jump to next round in same map
    const nextRound = rounds[nextRoundIndex];
    showSkipToast(`Pulando pausa → Round ${nextRound.round} (${nextRound.winner || ""})`);
    
    state.currentRoundIndex = nextRoundIndex;
    state.isSeeking = true;
    state.player.seekTo(nextRound.start, true);
    
    setTimeout(() => {
      state.isSeeking = false;
      updateUI();
    }, 400);

  } else {
    // End of current map -> Check if there is a next map
    const nextMapIndex = state.currentMapIndex + 1;
    if (state.matchData.maps && nextMapIndex < state.matchData.maps.length) {
      const nextMap = state.matchData.maps[nextMapIndex];
      showSkipToast(`Fim do Mapa ${mapObj.map_name}! Iniciando Mapa ${nextMap.map_name} → Round 1`);
      
      state.currentMapIndex = nextMapIndex;
      state.currentRoundIndex = 0;
      const firstRound = nextMap.rounds[0];
      
      state.isSeeking = true;
      if (firstRound) {
        state.player.seekTo(firstRound.start, true);
      }
      
      setTimeout(() => {
        state.isSeeking = false;
        renderMapTabs();
        renderRoundsList();
        renderScrubberSegments();
        updateUI();
      }, 500);

    } else {
      showSkipToast("🏆 Fim da Série de Partidas!");
    }
  }
}

function syncCurrentRoundToTime(time) {
  const mapObj = getCurrentMap();
  if (!mapObj || !mapObj.rounds) return;

  const roundIdx = mapObj.rounds.findIndex(r => time >= r.start && time <= r.end);
  if (roundIdx !== -1 && roundIdx !== state.currentRoundIndex) {
    state.currentRoundIndex = roundIdx;
    updateUI();
  }
}

function showSkipToast(message) {
  const toast = document.getElementById("skip-notification");
  const msgEl = document.getElementById("skip-message");
  if (!toast || !msgEl) return;

  msgEl.textContent = message;
  toast.classList.add("visible");

  setTimeout(() => {
    toast.classList.remove("visible");
  }, 2500);
}

// ---------------------------------------------------------------------------
// Helpers for State Data
// ---------------------------------------------------------------------------
function getCurrentMap() {
  if (!state.matchData || !state.matchData.maps || state.matchData.maps.length === 0) {
    return null;
  }
  return state.matchData.maps[state.currentMapIndex] || state.matchData.maps[0];
}

function getCurrentRound() {
  const mapObj = getCurrentMap();
  if (!mapObj || !mapObj.rounds || mapObj.rounds.length === 0) {
    return null;
  }
  return mapObj.rounds[state.currentRoundIndex] || mapObj.rounds[0];
}

// ---------------------------------------------------------------------------
// UI Rendering & Updates
// ---------------------------------------------------------------------------
function updateUI() {
  updateHUD();
  highlightActiveRound();
  updateCalibrationInputs();
}

function updateHUD() {
  if (!state.matchData) return;

  const info = state.matchData.match_info || {};
  const t1 = info.team1 || { name: "LOUD", logo: "" };
  const t2 = info.team2 || { name: "MIBR", logo: "" };

  const t1Name = document.getElementById("team1-name");
  const t2Name = document.getElementById("team2-name");
  const scoreBadge = document.getElementById("match-score-badge");
  const eventTitle = document.getElementById("match-event-title");

  if (t1Name) t1Name.textContent = t1.name || "Time 1";
  if (t2Name) t2Name.textContent = t2.name || "Time 2";
  if (scoreBadge) scoreBadge.textContent = info.score || "0 : 0";
  if (eventTitle) eventTitle.textContent = info.event || "VCT Match";

  const t1Fallback = document.getElementById("team1-logo-fallback");
  const t2Fallback = document.getElementById("team2-logo-fallback");

  if (t1Fallback) {
    if (t1.logo && t1Fallback.tagName !== "IMG") {
      const img = document.createElement("img");
      img.src = t1.logo;
      img.className = "team-logo";
      img.id = "team1-logo-fallback";
      img.alt = t1.name || "Team 1";
      img.onerror = () => {
        img.outerHTML = `<div class="team-logo-fallback" id="team1-logo-fallback">${(t1.name || 'T1').substring(0, 2).toUpperCase()}</div>`;
      };
      t1Fallback.replaceWith(img);
    } else if (!t1.logo && t1Fallback.tagName === "DIV") {
      t1Fallback.textContent = (t1.name || "T1").substring(0, 2).toUpperCase();
    }
  }

  if (t2Fallback) {
    if (t2.logo && t2Fallback.tagName !== "IMG") {
      const img = document.createElement("img");
      img.src = t2.logo;
      img.className = "team-logo";
      img.id = "team2-logo-fallback";
      img.alt = t2.name || "Team 2";
      img.onerror = () => {
        img.outerHTML = `<div class="team-logo-fallback" id="team2-logo-fallback">${(t2.name || 'T2').substring(0, 2).toUpperCase()}</div>`;
      };
      t2Fallback.replaceWith(img);
    } else if (!t2.logo && t2Fallback.tagName === "DIV") {
      t2Fallback.textContent = (t2.name || "T2").substring(0, 2).toUpperCase();
    }
  }

  const mapObj = getCurrentMap();
  const scrubberMap = document.getElementById("scrubber-map-title");
  if (scrubberMap && mapObj) {
    scrubberMap.textContent = `[Mapa ${mapObj.map_number}: ${mapObj.map_name}]`;
  }
}

function renderMapTabs() {
  const container = document.getElementById("map-tabs");
  if (!container || !state.matchData || !state.matchData.maps) return;

  container.innerHTML = "";
  state.matchData.maps.forEach((mapObj, idx) => {
    const btn = document.createElement("button");
    btn.className = `map-tab ${idx === state.currentMapIndex ? "active" : ""}`;
    btn.innerHTML = `
      <span>${mapObj.map_name}</span>
      <span class="map-score-pill">${mapObj.score || ""}</span>
    `;
    btn.onclick = () => selectMap(idx);
    container.appendChild(btn);
  });
}

function renderRoundsList() {
  const container = document.getElementById("rounds-grid");
  const countEl = document.getElementById("map-rounds-count");
  const mapObj = getCurrentMap();

  if (!container || !mapObj) return;

  const rounds = mapObj.rounds || [];
  if (countEl) {
    countEl.textContent = `${rounds.length} rounds`;
  }

  container.innerHTML = "";
  const t1Name = (state.matchData.match_info?.team1?.name || "Team 1").toLowerCase();

  rounds.forEach((r, idx) => {
    const card = document.createElement("div");
    const isWinnerT1 = r.winner && r.winner.toLowerCase() === t1Name;
    const dotClass = isWinnerT1 ? "team-1" : "team-2";
    const roundNumStr = String(r.round).padStart(2, '0');

    card.className = `round-card ${idx === state.currentRoundIndex ? "active" : ""}`;
    card.id = `round-card-${idx}`;
    card.innerHTML = `
      <div class="round-card-left">
        <span class="round-num">${roundNumStr}</span>
        <span class="round-winner-dot ${dotClass}" title="${r.winner || ''}"></span>
        <div>
          <span class="round-winner-label">${r.winner || "Round " + r.round}</span>
          <span class="round-win-type">${r.win_type || 'elim'}</span>
        </div>
      </div>
      <div class="round-card-right">
        <span class="round-score">${r.score_display || r.score || ""}</span>
        <span class="round-timestamps">${formatTime(r.start)} - ${formatTime(r.end)}</span>
        <span class="round-dur-tag">${r.duration || (r.end - r.start)}s</span>
      </div>
    `;

    card.onclick = () => jumpToRound(idx);
    container.appendChild(card);
  });
}

function renderScrubberSegments() {
  const bar = document.getElementById("scrubber-bar");
  const mapObj = getCurrentMap();
  if (!bar || !mapObj || !mapObj.rounds || mapObj.rounds.length === 0) return;

  const playhead = document.getElementById("scrubber-playhead");
  bar.innerHTML = "";
  if (playhead) bar.appendChild(playhead);

  const rounds = mapObj.rounds;
  const totalDuration = rounds.reduce((acc, r) => acc + (r.end - r.start), 0);
  const t1Name = (state.matchData.match_info?.team1?.name || "Team 1").toLowerCase();

  const totalEl = document.getElementById("clean-time-total");
  if (totalEl) totalEl.textContent = formatTime(totalDuration);

  rounds.forEach((r, idx) => {
    const dur = Math.max(1, r.end - r.start);
    const widthPct = totalDuration > 0 ? (dur / totalDuration) * 100 : 0;
    const isWinnerT1 = r.winner && r.winner.toLowerCase() === t1Name;
    const teamClass = isWinnerT1 ? "team-1" : "team-2";

    const seg = document.createElement("div");
    seg.className = `scrubber-segment ${teamClass} ${idx === state.currentRoundIndex ? "current" : ""}`;
    seg.style.width = `${widthPct}%`;
    seg.dataset.roundIndex = idx;

    seg.onmouseenter = (e) => showScrubberTooltip(e, r);
    seg.onmouseleave = hideScrubberTooltip;
    seg.onclick = () => jumpToRound(idx);

    bar.appendChild(seg);
  });
}

function updateScrubberAndTimer(vodCurrentTime) {
  const rawVodEl = document.getElementById("raw-vod-time");
  if (rawVodEl) rawVodEl.textContent = formatTime(vodCurrentTime);

  const mapObj = getCurrentMap();
  if (!mapObj || !mapObj.rounds || mapObj.rounds.length === 0) return;

  const rounds = mapObj.rounds;
  let elapsedClean = 0;
  let totalClean = 0;

  for (let i = 0; i < rounds.length; i++) {
    const r = rounds[i];
    const dur = Math.max(1, r.end - r.start);
    totalClean += dur;

    if (i < state.currentRoundIndex) {
      elapsedClean += dur;
    } else if (i === state.currentRoundIndex) {
      const withinRound = Math.max(0, Math.min(dur, vodCurrentTime - r.start));
      elapsedClean += withinRound;
    }
  }

  const elapsedEl = document.getElementById("clean-time-elapsed");
  if (elapsedEl) elapsedEl.textContent = formatTime(elapsedClean);

  const playhead = document.getElementById("scrubber-playhead");
  if (playhead && totalClean > 0) {
    const pct = Math.min(100, Math.max(0, (elapsedClean / totalClean) * 100));
    playhead.style.left = `${pct}%`;
  }
}

function showScrubberTooltip(e, roundObj) {
  const tooltip = document.getElementById("scrubber-tooltip");
  if (!tooltip) return;

  const icon = WIN_ICONS[roundObj.win_type] || "⚔️";
  tooltip.textContent = `Round ${roundObj.round} | ${roundObj.winner || ""} ${icon} (${formatTime(roundObj.start)} - ${formatTime(roundObj.end)})`;
  
  const rect = e.target.getBoundingClientRect();
  const barRect = document.getElementById("scrubber-bar").getBoundingClientRect();
  const centerPos = rect.left - barRect.left + (rect.width / 2);
  
  tooltip.style.left = `${centerPos}px`;
  tooltip.classList.add("visible");
}

function hideScrubberTooltip() {
  const tooltip = document.getElementById("scrubber-tooltip");
  if (tooltip) tooltip.classList.remove("visible");
}

function highlightActiveRound() {
  document.querySelectorAll(".round-card").forEach((c, idx) => {
    c.classList.toggle("active", idx === state.currentRoundIndex);
  });
  document.querySelectorAll(".scrubber-segment").forEach((s, idx) => {
    s.classList.toggle("current", idx === state.currentRoundIndex);
  });

  const activeCard = document.getElementById(`round-card-${state.currentRoundIndex}`);
  if (activeCard) {
    activeCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

// ---------------------------------------------------------------------------
// Actions & Navigation
// ---------------------------------------------------------------------------
function selectMap(mapIdx) {
  if (mapIdx === state.currentMapIndex) return;
  state.currentMapIndex = mapIdx;
  state.currentRoundIndex = 0;

  renderMapTabs();
  renderRoundsList();
  renderScrubberSegments();
  updateUI();

  const round = getCurrentRound();
  if (round && state.player && typeof state.player.seekTo === "function") {
    state.player.seekTo(round.start, true);
  }
}

function jumpToRound(roundIdx) {
  const mapObj = getCurrentMap();
  if (!mapObj || !mapObj.rounds || !mapObj.rounds[roundIdx]) return;

  state.currentRoundIndex = roundIdx;
  updateUI();

  const round = mapObj.rounds[roundIdx];
  if (state.player && typeof state.player.seekTo === "function") {
    state.isSeeking = true;
    state.player.seekTo(round.start, true);
    setTimeout(() => { state.isSeeking = false; }, 1000);
  }
}

function nextRound() {
  const mapObj = getCurrentMap();
  if (!mapObj || !mapObj.rounds) return;
  if (state.currentRoundIndex < mapObj.rounds.length - 1) {
    jumpToRound(state.currentRoundIndex + 1);
  }
}

function prevRound() {
  if (state.currentRoundIndex > 0) {
    jumpToRound(state.currentRoundIndex - 1);
  }
}

function replayCurrentRound() {
  const round = getCurrentRound();
  if (round && state.player && typeof state.player.seekTo === "function") {
    state.player.seekTo(round.start, true);
  }
}

function togglePlayPause() {
  if (!state.player || typeof state.player.playVideo !== "function") return;
  if (state.isPlaying) {
    state.player.pauseVideo();
  } else {
    state.player.playVideo();
  }
}

function toggleAutoSkip() {
  state.autoSkipEnabled = !state.autoSkipEnabled;
  const toggleBtn = document.getElementById("toggle-autoskip");
  if (toggleBtn) {
    toggleBtn.classList.toggle("active", state.autoSkipEnabled);
  }
  showSkipToast(state.autoSkipEnabled ? "⚡ Auto-Skip de Pausas ATIVADO" : "⏸️ Auto-Skip de Pausas DESATIVADO");
}

// ---------------------------------------------------------------------------
// Producer & Calibration Mode
// ---------------------------------------------------------------------------
function updateCalibrationInputs() {
  const round = getCurrentRound();
  const mapObj = getCurrentMap();
  if (!round || !mapObj) return;

  const labelEl = document.getElementById("cal-active-round-label");
  if (labelEl) {
    labelEl.textContent = `Round ${round.round} (${mapObj.map_name}) - Placar: ${round.score_display || ""}`;
  }

  const startInput = document.getElementById("cal-round-start");
  const endInput = document.getElementById("cal-round-end");

  if (startInput && document.activeElement !== startInput) startInput.value = formatTime(round.start);
  if (endInput && document.activeElement !== endInput) endInput.value = formatTime(round.end);
}

function adjustCurrentRoundOffset(field, deltaSeconds) {
  const round = getCurrentRound();
  if (!round) return;

  round[field] = Math.max(0, round[field] + deltaSeconds);
  round.duration = round.end - round.start;

  updateCalibrationInputs();
  renderRoundsList();
  renderScrubberSegments();
  updateUI();
}

function setCurrentPlayerTimeAsOffset(field) {
  if (!state.player || typeof state.player.getCurrentTime !== "function") return;
  const cur = Math.floor(state.player.getCurrentTime());
  const round = getCurrentRound();
  if (!round) return;

  round[field] = cur;
  round.duration = round.end - round.start;

  updateCalibrationInputs();
  renderRoundsList();
  renderScrubberSegments();
  updateUI();
  showSkipToast(`📍 ${field.toUpperCase()} definido para ${formatTime(cur)}`);
}

function quickMarkEndAndNext() {
  if (!state.player || typeof state.player.getCurrentTime !== "function") return;
  const cur = Math.floor(state.player.getCurrentTime());
  const round = getCurrentRound();
  if (!round) return;

  round.end = cur;
  round.duration = round.end - round.start;

  showSkipToast(`🏁 Fim do Round ${round.round} marcado (${formatTime(cur)})! Avançando...`);
  
  const mapObj = getCurrentMap();
  if (mapObj && mapObj.rounds && state.currentRoundIndex < mapObj.rounds.length - 1) {
    state.currentRoundIndex += 1;
    const nextR = mapObj.rounds[state.currentRoundIndex];
    if (nextR.start <= cur) {
      nextR.start = cur + 30;
      nextR.end = nextR.start + 85;
      nextR.duration = nextR.end - nextR.start;
    }
  }

  updateCalibrationInputs();
  renderRoundsList();
  renderScrubberSegments();
  updateUI();
}

function nudgeEntireMap(deltaSeconds) {
  const mapObj = getCurrentMap();
  if (!mapObj || !mapObj.rounds) return;

  mapObj.rounds.forEach(r => {
    r.start = Math.max(0, r.start + deltaSeconds);
    r.end = Math.max(0, r.end + deltaSeconds);
  });

  updateCalibrationInputs();
  renderRoundsList();
  renderScrubberSegments();
  updateUI();
  showSkipToast(`⏱️ Mapa deslocado em ${deltaSeconds > 0 ? "+" : ""}${deltaSeconds}s`);
}

async function saveCalibrationToServer() {
  if (!state.matchData) return;

  try {
    const res = await fetch("/api/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: state.matchData })
    });
    const json = await res.json();
    if (json.success) {
      showSkipToast("✅ Alterações salvas em timestamps.json!");
    } else {
      alert("Erro ao salvar: " + (json.detail || json.message));
    }
  } catch (e) {
    showSkipToast("💾 Baixando timestamps.json...");
    exportJSONToFile();
  }
}

function exportJSONToFile() {
  if (!state.matchData) return;
  const blob = new Blob([JSON.stringify(state.matchData, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "timestamps.json";
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// API & Data Fetching
// ---------------------------------------------------------------------------
async function loadInitialData() {
  try {
    const res = await fetch("/api/timestamps");
    if (res.ok) {
      const data = await res.json();
      loadMatchPayload(data);
      return;
    }
  } catch (e) {
    console.warn("Could not load /api/timestamps:", e);
  }
  
  openModal("loader-modal");
}

function loadMatchPayload(data) {
  if (!data) return;

  // Reconstruct maps if data is a flat timeline or maps is empty
  if (!data.maps || data.maps.length === 0) {
    if (data.timeline && data.timeline.length > 0) {
      const mapGroups = {};
      data.timeline.forEach(r => {
        const mNum = r.map || 1;
        if (!mapGroups[mNum]) {
          mapGroups[mNum] = {
            map_number: mNum,
            map_name: r.map_name || `Map ${mNum}`,
            score: "",
            rounds_count: 0,
            rounds: []
          };
        }
        mapGroups[mNum].rounds.push(r);
        mapGroups[mNum].rounds_count++;
      });
      data.maps = Object.values(mapGroups);
    }
  }

  state.matchData = data;
  state.currentMapIndex = 0;
  state.currentRoundIndex = 0;

  renderMapTabs();
  renderRoundsList();
  renderScrubberSegments();
  updateUI();

  const videoId = extractYouTubeId(data.video_id || data.video_url || "B5G9Qpv31_o");
  const firstRound = getCurrentRound();
  const startSec = firstRound ? firstRound.start : 0;

  createOrUpdatePlayer(videoId, startSec);
}

async function processNewMatch() {
  const ytUrl = document.getElementById("input-youtube-url").value.trim();
  const vlrUrl = document.getElementById("input-vlr-url").value.trim();
  const anchor = document.getElementById("input-anchor").value.trim();
  const preBuffer = parseInt(document.getElementById("input-pre-buffer").value) || 8;
  const btn = document.getElementById("btn-process-match");
  const btnText = document.getElementById("btn-process-text");

  if (!ytUrl || !vlrUrl) {
    alert("Por favor, preencha a URL do YouTube e a URL do VLR.gg.");
    return;
  }

  btn.disabled = true;
  btnText.innerHTML = `<span class="spinner"></span> Processando VLR...`;

  try {
    const res = await fetch("/api/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        vlr_url: vlrUrl,
        youtube_url: ytUrl,
        anchor_seconds: parseTimeToSeconds(anchor),
        pre_buffer_seconds: preBuffer,
        post_buffer_seconds: 5
      })
    });

    const json = await res.json();
    if (json.success && json.data) {
      loadMatchPayload(json.data);
      closeModal("loader-modal");
      showSkipToast("🚀 Partida sincronizada com sucesso!");
    } else {
      alert("Erro ao processar: " + (json.detail || "Falha na extração."));
    }
  } catch (e) {
    alert("Erro na requisição: " + e.message);
  } finally {
    btn.disabled = false;
    btnText.textContent = "🚀 Processar & Sincronizar";
  }
}

// ---------------------------------------------------------------------------
// Modals & UI Event Listeners
// ---------------------------------------------------------------------------
function openModal(modalId) {
  const m = document.getElementById(modalId);
  if (m) m.classList.add("open");
}

function closeModal(modalId) {
  const m = document.getElementById(modalId);
  if (m) m.classList.remove("open");
}

// ---------------------------------------------------------------------------
// Visual Calibration Studio (Interactive Thumbnails Wizard)
// ---------------------------------------------------------------------------
state.studioMapIndex = 0;
state.studioRoundIndex = 0;
state.studioWindowSec = 45;

function openStudioModal() {
  state.studioMapIndex = state.currentMapIndex;
  state.studioRoundIndex = state.currentRoundIndex;
  renderStudioMapSelector();
  renderStudioRoundPills();
  updateStudioRoundDisplay();
  loadStudioThumbnails();
  openModal("studio-modal");
}

function closeStudioModal() {
  closeModal("studio-modal");
  renderRoundsList();
  renderScrubberSegments();
  updateUI();
}

function renderStudioMapSelector() {
  const container = document.getElementById("studio-map-selector");
  if (!container || !state.matchData || !state.matchData.maps) return;

  container.innerHTML = "";
  state.matchData.maps.forEach((m, idx) => {
    const btn = document.createElement("button");
    btn.className = `btn btn-sm ${idx === state.studioMapIndex ? "btn-primary" : "btn-secondary"}`;
    btn.textContent = `Mapa ${m.map_number}: ${m.map_name}`;
    btn.onclick = () => {
      state.studioMapIndex = idx;
      state.studioRoundIndex = 0;
      renderStudioMapSelector();
      renderStudioRoundPills();
      updateStudioRoundDisplay();
      loadStudioThumbnails();
    };
    container.appendChild(btn);
  });
}

function renderStudioRoundPills() {
  const container = document.getElementById("studio-round-pills");
  const mapObj = state.matchData?.maps?.[state.studioMapIndex];
  if (!container || !mapObj) return;

  container.innerHTML = "";
  mapObj.rounds.forEach((r, idx) => {
    const pill = document.createElement("div");
    pill.className = `studio-pill ${idx === state.studioRoundIndex ? "active" : ""}`;
    pill.textContent = `R${r.round}`;
    pill.onclick = () => {
      state.studioRoundIndex = idx;
      renderStudioRoundPills();
      updateStudioRoundDisplay();
      loadStudioThumbnails();
      if (state.player && typeof state.player.seekTo === "function") {
        state.player.seekTo(r.start, true);
      }
    };
    container.appendChild(pill);
  });
}

function getStudioActiveRound() {
  const mapObj = state.matchData?.maps?.[state.studioMapIndex];
  if (!mapObj || !mapObj.rounds) return null;
  return mapObj.rounds[state.studioRoundIndex] || mapObj.rounds[0];
}

function updateStudioRoundDisplay() {
  const round = getStudioActiveRound();
  const mapObj = state.matchData?.maps?.[state.studioMapIndex];
  if (!round || !mapObj) return;

  const numEl = document.getElementById("studio-active-round-num");
  const winEl = document.getElementById("studio-active-winner");
  const scoreEl = document.getElementById("studio-active-score");
  const startEl = document.getElementById("studio-display-start");
  const endEl = document.getElementById("studio-display-end");
  const durEl = document.getElementById("studio-display-dur");

  if (numEl) numEl.textContent = `Round ${round.round} (${mapObj.map_name})`;
  if (winEl) winEl.textContent = `${round.winner || ""} (${round.win_type || "elim"})`;
  if (scoreEl) scoreEl.textContent = round.score_display || "";
  if (startEl) startEl.textContent = formatTime(round.start);
  if (endEl) endEl.textContent = formatTime(round.end);
  if (durEl) durEl.textContent = round.duration || (round.end - round.start);
}

async function loadStudioThumbnails(windowDelta = 45) {
  const grid = document.getElementById("studio-thumbnails-grid");
  const round = getStudioActiveRound();
  if (!grid || !round || !state.matchData) return;

  grid.innerHTML = `<div class="studio-loading"><span class="spinner"></span> Carregando miniaturas visuais do YouTube...</div>`;

  const videoUrl = state.matchData.video_url || state.matchData.video_id || "B5G9Qpv31_o";
  const startWindow = Math.max(0, round.start - windowDelta);
  const endWindow = Math.max(startWindow + 30, round.end + windowDelta);

  try {
    const res = await fetch("/api/thumbnails", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        youtube_url: videoUrl,
        start_seconds: startWindow,
        end_seconds: endWindow,
        step_seconds: 10
      })
    });

    const json = await res.json();
    if (json.success && json.thumbnails && json.thumbnails.length > 0) {
      renderStudioThumbnailsGrid(json.thumbnails, round);
    } else {
      grid.innerHTML = `<div class="studio-loading">⚠️ Não foi possível carregar miniaturas para esta janela de tempo.</div>`;
    }
  } catch (e) {
    grid.innerHTML = `<div class="studio-loading">⚠️ Erro ao carregar miniaturas: ${e.message}</div>`;
  }
}

function renderStudioThumbnailsGrid(thumbnails, round) {
  const grid = document.getElementById("studio-thumbnails-grid");
  if (!grid) return;

  grid.innerHTML = "";

  thumbnails.forEach(t => {
    const card = document.createElement("div");
    const isStart = Math.abs(t.time - round.start) <= 5;
    const isEnd = Math.abs(t.time - round.end) <= 5;

    card.className = `studio-thumb-card ${isStart ? "is-current-start" : ""} ${isEnd ? "is-current-end" : ""}`;
    card.id = `thumb-card-${t.time}`;

    let badgeHtml = "";
    if (isStart) badgeHtml = `<span class="thumb-candidate-badge badge-start">Início Atual</span>`;
    else if (isEnd) badgeHtml = `<span class="thumb-candidate-badge badge-end">Fim Atual</span>`;
    else if (t.is_start_candidate) badgeHtml = `<span class="thumb-candidate-badge badge-start">Sugestão 1:39</span>`;
    else if (t.is_end_candidate) badgeHtml = `<span class="thumb-candidate-badge badge-end">Sugestão Vitória</span>`;

    card.innerHTML = `
      <div class="thumb-image-wrap" title="Clique para testar este tempo no player">
        <img src="${t.thumbnail}" alt="Thumbnail ${t.formatted}" loading="lazy" />
        <span class="thumb-time-tag">${t.formatted}</span>
        ${badgeHtml}
      </div>
      <div class="thumb-actions">
        <button class="btn-thumb-action btn-set-start" title="Definir como Início do Round ${round.round}">
          📍 Início
        </button>
        <button class="btn-thumb-action btn-set-end" title="Definir como Fim do Round ${round.round}">
          🏁 Fim
        </button>
      </div>
    `;

    // Click image to seek player
    card.querySelector(".thumb-image-wrap").onclick = () => {
      if (state.player && typeof state.player.seekTo === "function") {
        state.player.seekTo(t.time, true);
        showSkipToast(`⏱️ Player posicionado em ${t.formatted}`);
      }
    };

    // Set as start
    card.querySelector(".btn-set-start").onclick = (e) => {
      e.stopPropagation();
      setStudioRoundStart(t.time);
    };

    // Set as end
    card.querySelector(".btn-set-end").onclick = (e) => {
      e.stopPropagation();
      setStudioRoundEnd(t.time);
    };

    grid.appendChild(card);
  });
}

function setStudioRoundStart(timeSec) {
  const round = getStudioActiveRound();
  if (!round) return;

  round.start = timeSec;
  round.duration = round.end - round.start;
  updateStudioRoundDisplay();
  showSkipToast(`📍 Início do Round ${round.round} definido para ${formatTime(timeSec)}`);
  loadStudioThumbnails(30);
}

function setStudioRoundEnd(timeSec) {
  const round = getStudioActiveRound();
  if (!round) return;

  round.end = timeSec;
  round.duration = round.end - round.start;
  updateStudioRoundDisplay();
  showSkipToast(`🏁 Fim do Round ${round.round} definido para ${formatTime(timeSec)}`);
  loadStudioThumbnails(30);
}

function initStudioEvents() {
  document.getElementById("btn-open-studio")?.addEventListener("click", openStudioModal);
  document.getElementById("btn-close-studio")?.addEventListener("click", closeStudioModal);
  document.getElementById("btn-studio-close-footer")?.addEventListener("click", closeStudioModal);

  document.getElementById("btn-studio-prev-round")?.addEventListener("click", () => {
    if (state.studioRoundIndex > 0) {
      state.studioRoundIndex--;
      renderStudioRoundPills();
      updateStudioRoundDisplay();
      loadStudioThumbnails();
      const r = getStudioActiveRound();
      if (r && state.player && typeof state.player.seekTo === "function") state.player.seekTo(r.start, true);
    }
  });

  document.getElementById("btn-studio-next-round")?.addEventListener("click", () => {
    const mapObj = state.matchData?.maps?.[state.studioMapIndex];
    if (mapObj && state.studioRoundIndex < mapObj.rounds.length - 1) {
      state.studioRoundIndex++;
      renderStudioRoundPills();
      updateStudioRoundDisplay();
      loadStudioThumbnails();
      const r = getStudioActiveRound();
      if (r && state.player && typeof state.player.seekTo === "function") state.player.seekTo(r.start, true);
    }
  });

  document.getElementById("btn-studio-refresh")?.addEventListener("click", () => loadStudioThumbnails());
  document.getElementById("btn-studio-scan-wider")?.addEventListener("click", () => loadStudioThumbnails(75));

  document.getElementById("btn-studio-save-all")?.addEventListener("click", async () => {
    await saveCalibrationToServer();
    closeStudioModal();
  });
}

function initApp() {
  // Bind Header Buttons
  document.getElementById("btn-open-loader")?.addEventListener("click", () => openModal("loader-modal"));
  document.getElementById("btn-close-modal")?.addEventListener("click", () => closeModal("loader-modal"));
  document.getElementById("btn-open-help")?.addEventListener("click", () => openModal("help-modal"));
  document.getElementById("btn-close-help")?.addEventListener("click", () => closeModal("help-modal"));
  document.getElementById("btn-close-help-confirm")?.addEventListener("click", () => closeModal("help-modal"));
  document.getElementById("btn-export-json")?.addEventListener("click", exportJSONToFile);

  // Studio Events
  initStudioEvents();

  // Calibration Drawer
  const calDrawer = document.getElementById("calibration-drawer");
  document.getElementById("btn-toggle-calibration")?.addEventListener("click", () => {
    calDrawer?.classList.toggle("open");
    updateCalibrationInputs();
  });
  document.getElementById("btn-close-calibration")?.addEventListener("click", () => {
    calDrawer?.classList.remove("open");
  });
  document.getElementById("btn-save-calibration")?.addEventListener("click", saveCalibrationToServer);

  // Rapid Tagger Buttons
  document.getElementById("btn-quick-mark-start")?.addEventListener("click", () => setCurrentPlayerTimeAsOffset("start"));
  document.getElementById("btn-quick-mark-end")?.addEventListener("click", quickMarkEndAndNext);
  document.getElementById("cal-nudge-start-minus1")?.addEventListener("click", () => adjustCurrentRoundOffset("start", -1));
  document.getElementById("cal-nudge-start-plus1")?.addEventListener("click", () => adjustCurrentRoundOffset("start", 1));
  document.getElementById("cal-nudge-end-minus1")?.addEventListener("click", () => adjustCurrentRoundOffset("end", -1));
  document.getElementById("cal-nudge-end-plus1")?.addEventListener("click", () => adjustCurrentRoundOffset("end", 1));

  // Calibration Offset Buttons
  document.getElementById("cal-set-current-start")?.addEventListener("click", () => setCurrentPlayerTimeAsOffset("start"));
  document.getElementById("cal-set-current-end")?.addEventListener("click", () => setCurrentPlayerTimeAsOffset("end"));
  document.getElementById("cal-start-minus5")?.addEventListener("click", () => adjustCurrentRoundOffset("start", -5));
  document.getElementById("cal-start-plus5")?.addEventListener("click", () => adjustCurrentRoundOffset("start", 5));
  document.getElementById("cal-end-minus5")?.addEventListener("click", () => adjustCurrentRoundOffset("end", -5));
  document.getElementById("cal-end-plus5")?.addEventListener("click", () => adjustCurrentRoundOffset("end", 5));
  document.getElementById("cal-map-minus10")?.addEventListener("click", () => nudgeEntireMap(-10));
  document.getElementById("cal-map-minus2")?.addEventListener("click", () => nudgeEntireMap(-2));
  document.getElementById("cal-map-plus2")?.addEventListener("click", () => nudgeEntireMap(2));
  document.getElementById("cal-map-plus10")?.addEventListener("click", () => nudgeEntireMap(10));

  // Manual input field edits
  const startInput = document.getElementById("cal-round-start");
  const endInput = document.getElementById("cal-round-end");

  startInput?.addEventListener("change", (e) => {
    const round = getCurrentRound();
    if (!round) return;
    round.start = parseTimeToSeconds(e.target.value);
    round.duration = round.end - round.start;
    renderRoundsList();
    renderScrubberSegments();
    updateUI();
  });

  endInput?.addEventListener("change", (e) => {
    const round = getCurrentRound();
    if (!round) return;
    round.end = parseTimeToSeconds(e.target.value);
    round.duration = round.end - round.start;
    renderRoundsList();
    renderScrubberSegments();
    updateUI();
  });

  // Playback Controls
  document.getElementById("btn-play-pause")?.addEventListener("click", togglePlayPause);
  document.getElementById("btn-next-round")?.addEventListener("click", nextRound);
  document.getElementById("btn-prev-round")?.addEventListener("click", prevRound);
  document.getElementById("btn-replay-round")?.addEventListener("click", replayCurrentRound);
  document.getElementById("toggle-autoskip")?.addEventListener("click", toggleAutoSkip);

  // Speed Selector
  document.getElementById("select-speed")?.addEventListener("change", (e) => {
    const rate = parseFloat(e.target.value);
    if (state.player && typeof state.player.setPlaybackRate === "function") {
      state.player.setPlaybackRate(rate);
    }
  });

  // Fullscreen
  document.getElementById("btn-fullscreen")?.addEventListener("click", () => {
    const elem = document.querySelector(".video-wrapper");
    if (!elem) return;
    if (!document.fullscreenElement) {
      elem.requestFullscreen().catch(err => alert("Erro ao abrir tela cheia"));
    } else {
      document.exitFullscreen();
    }
  });

  // Process Form
  document.getElementById("btn-process-match")?.addEventListener("click", processNewMatch);
  document.getElementById("btn-load-preset")?.addEventListener("click", () => {
    document.getElementById("input-youtube-url").value = "https://www.youtube.com/watch?v=B5G9Qpv31_o";
    document.getElementById("input-vlr-url").value = "https://www.vlr.gg/734312/loud-vs-mibr-vct-2026-americas-stage-2-lr2";
    document.getElementById("input-anchor").value = "192";
  });

  // Local JSON File Upload
  document.getElementById("input-json-file")?.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const json = JSON.parse(evt.target.result);
        loadMatchPayload(json);
        closeModal("loader-modal");
        showSkipToast("📁 Arquivo JSON carregado!");
      } catch (err) {
        alert("Erro ao ler JSON: " + err.message);
      }
    };
    reader.readAsText(file);
  });

  // Keyboard Shortcuts
  window.addEventListener("keydown", (e) => {
    if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;
    
    switch (e.key) {
      case "1":
        e.preventDefault();
        setCurrentPlayerTimeAsOffset("start");
        break;
      case "2":
        e.preventDefault();
        quickMarkEndAndNext();
        break;
      case " ":
      case "k":
      case "K":
        e.preventDefault();
        togglePlayPause();
        break;
      case "]":
      case "l":
      case "L":
        e.preventDefault();
        nextRound();
        break;
      case "[":
      case "j":
      case "J":
        e.preventDefault();
        prevRound();
        break;
      case "r":
      case "R":
        e.preventDefault();
        replayCurrentRound();
        break;
      case "s":
      case "S":
        e.preventDefault();
        toggleAutoSkip();
        break;
      case "c":
      case "C":
        e.preventDefault();
        calDrawer?.classList.toggle("open");
        updateCalibrationInputs();
        break;
      case "f":
      case "F":
        e.preventDefault();
        document.getElementById("btn-fullscreen")?.click();
        break;
      case "ArrowLeft":
        e.preventDefault();
        if (state.player && typeof state.player.getCurrentTime === "function") {
          state.player.seekTo(Math.max(0, state.player.getCurrentTime() - 5), true);
        }
        break;
      case "ArrowRight":
        e.preventDefault();
        if (state.player && typeof state.player.getCurrentTime === "function") {
          state.player.seekTo(state.player.getCurrentTime() + 5, true);
        }
        break;
    }
  });

  // Load Initial JSON from server
  loadInitialData();
}

// Auto-run initApp on DOM Ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}

