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
     GET  /api/pinned                -> {pinned: [...]}
     POST /api/pinned                <- {pinned: [...]}
   Live stream list comes from Livemasjid's Icecast status JSON.
   ============================================================ */

const apiurl = "/api/";
const casturl = "https://www.livemasjid.com/api/status-json.xsl";

let favourites = [];
let pinned = [];
let livemounts = [];  // Icecast sources: live right now, with names/descriptions
let knownmounts = {}; // every mount eBilal has heard of over MQTT -> "started"/"stopped"
let reachable = true;
let state = { status: "starting" };
let filter = "online"; // "online" | "offline" | "all"
let query = "";

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

/* ---------- Autoplay (stored as "favourites") ----------
   Autoplay feeds are the ones the eBilal device plays by itself when they go live.
   Stored on the Pi as settings.toml "mounts". */
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

/* ---------- Pinned feeds ----------
   Pinning only arranges the web UI (it does not change what auto-plays). Pins
   are stored on the Pi so every phone sees the same layout. Quraan recitation
   ("activestream") is pinned by default and can be unpinned. */
function getPinned() {
  return fetch(apiurl + "pinned")
    .then((r) => r.json())
    .then((obj) => {
      pinned = obj.pinned || [];
      renderStations();
    })
    .catch((err) => console.log("pinned:", err));
}

function setPinned(list) {
  pinned = list; // optimistic, so the UI responds instantly
  renderStations();
  return fetch(apiurl + "pinned", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pinned: list }),
  })
    .then((r) => r.json())
    .then((obj) => {
      pinned = obj.pinned || list;
      renderStations();
    })
    .catch((err) => console.log("setPinned:", err));
}

function togglePin(mount) {
  if (pinned.includes(mount)) {
    setPinned(pinned.filter((m) => m !== mount));
  } else {
    setPinned([...pinned, mount]);
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
      setReachable(true);
      renderStatus();
      renderNowPlaying();
      renderStations();
    })
    .catch((err) => {
      console.log("player:", err);
      setReachable(false);
    });
}

function setReachable(ok) {
  reachable = ok;
  $("offline-banner").hidden = ok;
  if (!ok) {
    state = { status: "offline" };
    renderStatus();
    renderNowPlaying();
  }
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

/* ---------- Known mounts (online + offline) ---------- */
function getKnownMounts() {
  return fetch(apiurl + "mounts")
    .then((r) => r.json())
    .then((obj) => {
      knownmounts = obj.mounts || {};
      renderStations();
    })
    .catch((err) => console.log("mounts:", err));
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

/* ---------- Render station lists ---------- */
function icon(name, cls) {
  return `<span class="material-symbols-rounded${cls ? " " + cls : ""}">${name}</span>`;
}

const esc = (t) =>
  String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function liveFor(mount) {
  return livemounts.find((x) => mountFromListenUrl(x.listenurl) === mount);
}

function isOnline(mount) {
  return !!liveFor(mount) || /started/.test(knownmounts[mount] || "");
}

function displayName(mount) {
  const m = liveFor(mount);
  return m ? cleanName(m.server_name, mount) : mount;
}

// Every mount we know about, without the ".mp3" transcode twins
function allMounts() {
  const set = new Set(Object.keys(knownmounts));
  livemounts.forEach((m) => set.add(mountFromListenUrl(m.listenurl)));
  return [...set].filter((m) => !(m.endsWith(".mp3") && set.has(m.slice(0, -4))));
}

// One station row. Offline feeds are dimmed but can still be pinned/liked.
function stationRow(mount) {
  const m = liveFor(mount);
  const live = isOnline(mount);
  const isPlaying = state.status === "playing" && state.mount === mount;
  const isFav = favourites.includes(mount);
  const isPinned = pinned.includes(mount);
  const name = esc(displayName(mount));
  const desc = m ? esc(m.server_description || "") : "";
  const extUrl = m && m.server_url ? esc(m.server_url.startsWith("http") ? m.server_url : "https://" + m.server_url) : "";
  const em = esc(mount);
  return `
      <div class="station${isPlaying ? " is-playing" : ""}${live ? "" : " is-offline"}">
        <button class="station-play" data-action="play" data-mount="${em}" ${live ? "" : "disabled"}
          aria-label="${isPlaying ? "Stop" : "Play"} ${name}">
          ${icon(isPlaying ? "stop" : "play_arrow")}
        </button>
        <div class="station-info">
          <div class="station-name">${name}</div>
          ${desc ? `<div class="station-desc">${desc}</div>` : ""}
          <div class="station-mount">${em}${live ? "" : " · offline"}</div>
        </div>
        <div class="station-actions">
          <button class="icon-btn${isPinned ? " pin-on" : ""}" data-action="pin" data-mount="${em}"
            aria-pressed="${isPinned}" aria-label="${isPinned ? "Unpin" : "Pin"} ${name}">${icon("push_pin", isPinned ? "fill" : "")}</button>
          <button class="icon-btn${isFav ? " auto-on" : ""}" data-action="fav" data-mount="${em}"
            aria-pressed="${isFav}" title="${isFav ? "Autoplay on" : "Autoplay off"}"
            aria-label="${isFav ? "Turn off autoplay for" : "Autoplay"} ${name}">${icon("autoplay", isFav ? "fill" : "")}</button>
          ${extUrl ? `<a class="icon-btn" href="${extUrl}" target="_blank" rel="noopener" aria-label="Open stream page">${icon("open_in_new")}</a>` : ""}
        </div>
      </div>`;
}

// Online first, then by name
function byOnlineThenName(a, b) {
  const d = isOnline(b) - isOnline(a);
  return d || displayName(a).localeCompare(displayName(b));
}

function matches(mount) {
  if (!query) return true;
  const m = liveFor(mount);
  const hay = [mount, displayName(mount), m && m.server_description].join(" ").toLowerCase();
  return hay.includes(query);
}

// Cap long lists (800+ offline mounts) so a phone stays responsive
const MAX_ROWS = 150;

function renderStations() {
  // 1. Pinned, in pin order
  $("pinned-section").hidden = pinned.length === 0;
  $("pinned-mounts").innerHTML = pinned.map(stationRow).join("");

  // 2. Autoplay: every autoplay feed, even if it is also pinned
  const auto = favourites.slice().sort(byOnlineThenName);
  $("autoplay-mounts").innerHTML = auto.map(stationRow).join("");
  $("autoplay-empty").hidden = favourites.length > 0;

  // 3. The rest
  const rest = allMounts().filter((m) => !pinned.includes(m) && !favourites.includes(m));
  const online = rest.filter(isOnline);
  $("count-online").textContent = online.length;
  $("count-offline").textContent = rest.length - online.length;
  $("count-all").textContent = rest.length;

  let list = filter === "online" ? online : filter === "offline" ? rest.filter((m) => !isOnline(m)) : rest;
  list = list.filter(matches).sort(byOnlineThenName);

  const host = $("livemounts");
  const empty = $("empty-state");
  if (!list.length) {
    host.innerHTML = "";
    empty.hidden = false;
    $("empty-text").textContent = query
      ? `No streams match "${query}".`
      : filter === "offline"
      ? "Every other stream is live right now."
      : "No other live streams right now.";
    return;
  }
  empty.hidden = true;
  const more = list.length - MAX_ROWS;
  host.innerHTML =
    list.slice(0, MAX_ROWS).map(stationRow).join("") +
    (more > 0 ? `<p class="empty">and ${more} more. Search to narrow the list.</p>` : "");
}

// One delegated listener instead of inline onclick attributes
document.addEventListener("click", (e) => {
  const chip = e.target.closest("[data-filter]");
  if (chip) return setFilter(chip.dataset.filter);
  const btn = e.target.closest("[data-action]");
  if (!btn || btn.disabled) return;
  const mount = btn.dataset.mount;
  if (btn.dataset.action === "play") togglePlay(mount);
  else if (btn.dataset.action === "pin") togglePin(mount);
  else if (btn.dataset.action === "fav") toggleFav(mount);
});

/* ---------- Filter + search ---------- */
function setFilter(f) {
  filter = f;
  document.querySelectorAll("[data-filter]").forEach((c) => {
    const on = c.dataset.filter === f;
    c.classList.toggle("is-active", on);
    c.setAttribute("aria-pressed", on);
  });
  renderStations();
}

let searchTimer = null;
$("stream-search").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    query = e.target.value.trim().toLowerCase();
    renderStations();
  }, 150);
});

/* ---------- Settings panel ---------- */
function toggleSettings() {
  const overlay = $("settings-overlay");
  const gear = $("gear-btn");
  const opening = overlay.hidden;
  overlay.hidden = !opening;
  gear.setAttribute("aria-expanded", opening ? "true" : "false");
  if (opening) {
    getLog();
    getVersion();
  }
}

function getVersion() {
  fetch(apiurl + "version")
    .then((r) => r.json())
    .then((obj) => {
      $("version").textContent = obj.version || "unknown";
    })
    .catch(() => {
      $("version").textContent = "unknown";
    });
}

function checkUpdate() {
  const status = $("update-status");
  const notes = $("update-notes");
  const upgrade = $("btn-upgrade");
  const warn = $("update-warn");
  const check = $("btn-check");
  status.textContent = "Checking…";
  notes.hidden = true;
  upgrade.hidden = true;
  warn.hidden = true;
  check.disabled = true;
  fetch(apiurl + "update/check")
    .then((r) => r.json())
    .then((d) => {
      check.disabled = false;
      $("version").textContent = d.current || "unknown";
      if (d.error) {
        status.textContent = d.error;
        return;
      }
      if (d.update_available) {
        status.textContent = `Update available: ${d.latest} (installed: ${d.current})`;
        if (d.notes) {
          notes.textContent = d.notes;
          notes.hidden = false;
        }
        upgrade.textContent = `Upgrade to ${d.latest}`;
        upgrade.hidden = false;
        warn.hidden = false;
      } else {
        status.textContent = `You are on the latest version (${d.current}).`;
      }
    })
    .catch(() => {
      check.disabled = false;
      status.textContent = "Could not check for updates.";
    });
}

function applyUpdate() {
  if (!confirm("Upgrade eBilal now?\n\nThis pulls the latest release and restarts the player. Playback will stop for a few seconds. Do not power off the Pi during the update.")) {
    return;
  }
  const status = $("update-status");
  const upgrade = $("btn-upgrade");
  upgrade.disabled = true;
  status.textContent = "Upgrading… eBilal will restart shortly.";
  fetch(apiurl + "update/apply", { method: "POST" })
    .then((r) => r.json())
    .then((d) => {
      if (d.ok) {
        status.textContent = `Upgrading to ${d.updating_to}. Reconnecting…`;
        // Poll until the service is back, then reload.
        setTimeout(pollBack, 8000);
      } else {
        upgrade.disabled = false;
        status.textContent = d.error || "Upgrade failed.";
      }
    })
    .catch(() => {
      // The restart kills the connection mid-request; treat as "in progress".
      status.textContent = "Restarting… reconnecting…";
      setTimeout(pollBack, 8000);
    });
}

function pollBack() {
  fetch(apiurl + "version", { cache: "no-store" })
    .then((r) => r.json())
    .then((d) => {
      $("update-status").textContent = `Updated to ${d.version}. Reloading…`;
      setTimeout(() => location.reload(), 1500);
    })
    .catch(() => setTimeout(pollBack, 4000));
}

// Close settings on Escape
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !$("settings-overlay").hidden) toggleSettings();
});

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

/* ---------- PWA: service worker + install ---------- */
// Service workers (and so installability) need a secure context: HTTPS, or
// localhost. If this page was opened over plain http://<ip>, offer the way out.
let deferredInstall = null;

function setupPWA() {
  const isiOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  const block = $("install-block");
  const text = $("install-text");

  if ("serviceWorker" in navigator && window.isSecureContext) {
    navigator.serviceWorker.register("/sw.js").catch((err) => console.log("sw:", err));
  } else if (location.protocol === "http:") {
    upgradeToHttps();
  }

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredInstall = e;
    block.hidden = false;
    $("btn-install").hidden = false;
  });
  window.addEventListener("appinstalled", () => {
    deferredInstall = null;
    block.hidden = true;
  });
  // iOS never fires beforeinstallprompt; show the manual steps instead
  if (isiOS && !standalone && window.isSecureContext) {
    block.hidden = false;
    text.textContent = "On iPhone/iPad: tap the Share button, then \"Add to Home Screen\".";
  }
}

// Opened over plain HTTP. If this device already trusts eBilal's certificate,
// move to HTTPS silently; otherwise point at the one-time setup page.
function upgradeToHttps() {
  const target = "https://" + location.host + location.pathname + location.search;
  fetch("https://" + location.host + "/api/version?probe=" + Date.now(), { mode: "no-cors", cache: "no-store" })
    .then(() => location.replace(target))
    .catch(() => {
      if (localStorage.getItem("ebilal-secure-hint") === "dismissed") return;
      $("secure-hint").hidden = false;
      $("install-block").hidden = false;
      $("install-text").innerHTML =
        'To install eBilal as an app, first <a href="/trust.html">set up a secure connection</a> on this device.';
    });
}

function dismissSecureHint() {
  localStorage.setItem("ebilal-secure-hint", "dismissed");
  $("secure-hint").hidden = true;
}

function installApp() {
  if (!deferredInstall) return;
  deferredInstall.prompt();
  deferredInstall.userChoice.finally(() => {
    deferredInstall = null;
    $("btn-install").hidden = true;
  });
}

/* ---------- Init + polling ---------- */
function init() {
  getLiveStreams();
  getKnownMounts();
  getFavourites();
  getPinned();
  getVolume();
  getPlayerState();
  getLog();
}

setupPWA();
init();

setInterval(() => {
  getPlayerState();
  getLiveStreams();
  getKnownMounts();
  getFavourites();
  getPinned();
  getLog();
}, 30000);

// Refresh straight away when the app returns to the foreground
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) init();
});
