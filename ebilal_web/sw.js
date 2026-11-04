/* eBilal service worker.
 *
 * eBilal is a remote control: the audio plays on the Pi, so there is nothing
 * to "go offline" with. The worker exists to make the app installable and to
 * show the app shell instantly (and a friendly message) when the Pi is
 * unreachable. It deliberately NEVER caches /api/ responses, because stale
 * player state or volume would be worse than an error.
 *
 * Strategy
 *   app shell (same origin)  network-first, fall back to cache
 *   fonts (Google)           stale-while-revalidate
 *   /api/, Livemasjid status straight to the network, never cached
 */
const CACHE = "ebilal-shell-v4";
const SHELL = [
  "/",
  "/css/style.css",
  "/js/ebilal.js",
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/radio.svg",
  "/favicon.ico",
];
const FONT_HOSTS = ["fonts.googleapis.com", "fonts.gstatic.com"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Fonts: serve from cache, refresh in the background
  if (FONT_HOSTS.includes(url.hostname)) {
    event.respondWith(
      caches.open(CACHE).then((cache) =>
        cache.match(req).then((hit) => {
          const net = fetch(req)
            .then((res) => {
              cache.put(req, res.clone());
              return res;
            })
            .catch(() => hit);
          return hit || net;
        })
      )
    );
    return;
  }

  // Everything else cross-origin, the API, and the live log: not ours to cache
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname === "/web.log") return;

  // App shell: network-first so an in-app update shows up on the next load
  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(() =>
        caches.match(req).then((hit) => hit || (req.mode === "navigate" ? caches.match("/") : undefined))
      )
  );
});
