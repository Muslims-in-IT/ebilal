/* ============================================================
   eBilal web player — talks to the eBilal FastAPI backend.
   API contract preserved from the original:
     GET  /api/favourites            -> {favourites: [...]}
     POST /api/favourites            <- {favourites: [...]}
     GET  /api/volume                -> {volume: int}
     POST /api/volume?volume=N       -> {volume: int}
     GET  /api/player                -> {status, mount?}
     GET  /api/player/play/{mount}   -> {status, mount}
     GET  /api/player/stop           -> {status}
   Live stream list comes from Livemasjid's Icecast status JSON.
   ============================================================ */

const apiurl = "/api/";
const casturl = "https://www.livemasjid.com/api/status-json.xsl";

let favourites = [];
let livemounts = [];
let state = { status: "starting" };
let filter = "all"; // "all" | "fav"

const $ = (id) => document.getElementById(id);

/* ---------- Status pill ---------- */
function renderStatus() {
  const dot = $("status-dot");
  const label = $("status");
  dot.className = "dot";
  if (state.status === "playing") {
    dot.classList.add("is-playing");
    label.textContent = "playing";
  } else if (state.status === "connected") {
    dot.classList.add("is-live");
    label.textContent = "connected";
  } else if (state.status === "stopped") {
    dot.classList.add("is-live");
    label.textContent = "idle";
  } else {
    dot.classList.add("is-off");
    label.textContent = state.status || "offline";
  }
}

/* ---------- Now playing ---------- */
function renderNowPlaying() {
  const np = $("now-playing");
  if (state.status === "playing" && state.mount) {
    np.hidden = false;
    $("np-mount").textContent = prettyName(state.mount) || state.mount;
  } else {
    np.hidden = true;
  }
}

/* ---------- Favourites ---------- */
function getFavourites() {
  return fetch(apiurl + "favourites")
    .then((r) => r.json())
    .then((obj) => {
      favourites = obj.favourites || [];
      renderStations();
    })
    .catch((err) => console.log("favourites:", err));
}

function setFavourites(list) {
  return fetch(apiurl + "favourites", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ favourites: list }),
  })
    .then((r) => r.json())
    .then((obj) => {
      favourites = obj.favourites || list;
      renderStations();
    })
    .catch((err) => console.log("setFavourites:", err));
}

function toggleFav(mount) {
  if (favourites.includes(mount)) {
    setFavourites(favourites.filter((m) => m !== mount));
  } else {
    setFavourites([...favourites, mount]);
  }
}

/* ---------- Volume ---------- */
function getVolume() {
  return fetch(apiurl + "volume")
    .then((r) => r.json())
    .then((obj) => setVolumeUI(obj.volume))
    .catch((err) => console.log("volume:", err));
}

function setVolumeUI(v) {
  const slider = $("volume");
  slider.value = v;
  $("vol-val").textContent = v;
  const pct = Math.max(0, Math.min(100, v));
  slider.style.background =
    `linear-gradient(to right, var(--accent) 0%, var(--accent) ${pct}%, var(--card-border) ${pct}%, var(--card-border) 100%)`;
}

function onVolumeInput(v) {
  setVolumeUI(v); // instant visual feedback while dragging
}

function setVolume(v) {
  fetch(apiurl + "volume?volume=" + encodeURIComponent(v), { method: "POST" })
    .then((r) => r.json())
    .then((obj) => setVolumeUI(obj.volume))
    .catch((err) => console.log("setVolume:", err));
}

/* ---------- Player ---------- */
function getPlayerState() {
  return fetch(apiurl + "player")
    .then((r) => r.json())
    .then((obj) => {
      state = obj;
      renderStatus();
      renderNowPlaying();
      renderStations();
    })
    .catch((err) => console.log("player:", err));
}

async function play(mount) {
  try {
    const r = await fetch(apiurl + "player/play/" + encodeURIComponent(mount));
    state = await r.json();
  } catch (err) {
    console.log("play:", err);
  }
  renderStatus();
  renderNowPlaying();
  renderStations();
}

async function stop() {
  try {
    const r = await fetch(apiurl + "player/stop");
    state = await r.json();
  } catch (err) {
    console.log("stop:", err);
  }
  renderStatus();
  renderNowPlaying();
  renderStations();
}

function togglePlay(mount) {
  if (state.status === "playing" && state.mount === mount) {
    stop();
  } else {
    play(mount);
  }
}

/* ---------- Live streams ---------- */
function mountFromListenUrl(url) {
  const parts = (url || "").split("/");
  return parts[3] || url;
}

function prettyName(mount) {
  const m = livemounts.find((x) => mountFromListenUrl(x.listenurl) === mount);
  return m ? cleanName(m.server_name, mount) : null;
}

function getLiveStreams() {
  return fetch(casturl)
    .then((r) => r.json())
    .then((obj) => {
      let src = (obj.icestats && obj.icestats.source) || [];
      if (!Array.isArray(src)) src = [src]; // Icecast returns an object when only one source

      // Livemasjid publishes a secondary ".mp3" transcode mount alongside each
      // primary stream. These duplicates carry no real name ("Unspecified name"
      // or "/mount.mp3"), so hide them when the primary mount is also live.
      const mounts = src.map((m) => mountFromListenUrl(m.listenurl));
      src = src.filter((m) => {
        const mount = mountFromListenUrl(m.listenurl);
        if (mount.endsWith(".mp3")) {
          const primary = mount.slice(0, -4);
          if (mounts.includes(primary)) return false; // primary exists, drop the .mp3 twin
        }
        return true;
      });

      livemounts = src;
      renderStations();
      renderNowPlaying();
    })
    .catch((err) => {
      console.log("livestreams:", err);
      livemounts = [];
      renderStations();
    });
}

// Tidy a station name: Icecast often returns leading slashes, extra spaces,
// or the literal "Unspecified name" placeholder.
function cleanName(raw, mount) {
  let n = (raw || "").trim();
  if (!n || n === "Unspecified name" || n === "/" + mount || n === mount) {
    return mount; // fall back to the mount id, which is at least meaningful
  }
  return n.replace(/^\/+/, "").trim();
}

/* ---------- Render station list ---------- */
const svgPlay = '<svg viewBox="0 0 24 24" width="20" height="20"><path d="M8 5v14l11-7z"/></svg>';
const svgStop = '<svg viewBox="0 0 24 24" width="18" height="18"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>';
const svgHeart = '<svg viewBox="0 0 24 24" width="20" height="20"><path d="M12 20.3l-1.45-1.32C5.4 14.36 2 11.28 2 7.5 2 4.42 4.42 2 7.5 2c1.74 0 3.41.81 4.5 2.09C13.09 2.81 14.76 2 16.5 2 19.58 2 22 4.42 22 7.5c0 3.78-3.4 6.86-8.55 11.54L12 20.3z"/></svg>';
const svgLink = '<svg viewBox="0 0 24 24" width="18" height="18"><path d="M14 3h7v7h-2V6.4l-9.3 9.3-1.4-1.4L17.6 5H14V3zM5 5h5v2H5v12h12v-5h2v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z"/></svg>';

function renderStations() {
  const host = $("livemounts");
  const empty = $("empty-state");

  let list = livemounts.slice();
  if (filter === "fav") {
    list = list.filter((m) => favourites.includes(mountFromListenUrl(m.listenurl)));
  }

  if (!list.length) {
    host.innerHTML = "";
    empty.hidden = false;
    $("empty-text").textContent =
      filter === "fav" ? "None of your favourites are live right now." : "No live streams right now.";
    return;
  }
  empty.hidden = true;

  host.innerHTML = list
    .map((m) => {
      const mount = mountFromListenUrl(m.listenurl);
      const isPlaying = state.status === "playing" && state.mount === mount;
      const isFav = favourites.includes(mount);
      const desc = (m.server_description || "").replace(/</g, "&lt;");
      const name = cleanName(m.server_name, mount).replace(/</g, "&lt;");
      const extUrl = m.server_url ? (m.server_url.startsWith("http") ? m.server_url : "https://" + m.server_url) : "#";
      return `
      <div class="station${isPlaying ? " is-playing" : ""}">
        <button class="station-play" onclick="togglePlay('${mount}')"
          aria-label="${isPlaying ? "Stop" : "Play"} ${name}">
          ${isPlaying ? svgStop : svgPlay}
        </button>
        <div class="station-info">
          <div class="station-name">${name}</div>
          ${desc ? `<div class="station-desc">${desc}</div>` : ""}
          <div class="station-mount">${mount}</div>
        </div>
        <div class="station-actions">
          <button class="icon-btn${isFav ? " fav-on" : ""}" onclick="toggleFav('${mount}')"
            aria-label="${isFav ? "Remove from" : "Add to"} favourites">${svgHeart}</button>
          <a class="icon-btn" href="${extUrl}" target="_blank" rel="noopener" aria-label="Open stream page">${svgLink}</a>
        </div>
      </div>`;
    })
    .join("");
}

/* ---------- Filter chips ---------- */
function setFilter(f) {
  filter = f;
  $("chip-all").classList.toggle("is-active", f === "all");
  $("chip-fav").classList.toggle("is-active", f === "fav");
  renderStations();
}

/* ---------- Logs ---------- */
function getLog() {
  fetch("/web.log")
    .then((r) => r.text())
    .then((txt) => {
      const el = $("log");
      el.value = txt;
      el.scrollTop = el.scrollHeight;
    })
    .catch(() => {});
}

/* ---------- Init + polling ---------- */
function init() {
  getLiveStreams();
  getFavourites();
  getVolume();
  getPlayerState();
  getLog();
}

init();

setInterval(() => {
  getPlayerState();
  getLiveStreams();
  getFavourites();
  getLog();
}, 30000);
