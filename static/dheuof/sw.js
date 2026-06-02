/* ضيوف · Service Worker — installable PWA (iOS / Android / Browser) */
const CACHE = 'dheuof-app-v1';

// App shell precached on install (kept small; modules are runtime-cached)
const PRECACHE = [
  '/',
  '/static/dheuof/index.html',
  '/static/dheuof/colors_and_type.css',
  '/static/dheuof/assets/animations.css',
  '/static/dheuof/assets/animations.js',
  '/static/dheuof/shared/sidebar.js',
  '/static/dheuof/shared/chrome.css',
  '/static/dheuof/shared/module.css',
  '/static/dheuof/manifest.json',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE)
      // addAll fails if any single asset 404s — add individually so install never breaks
      .then((c) => Promise.all(PRECACHE.map((u) => c.add(u).catch(() => null))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Never cache API or cross-origin requests — always go to network
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/')) {
    return;
  }

  // Page navigations → network-first (fresh content), fall back to cache, then to launcher
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req)
        .then((res) => {
          const clone = res.clone();
          caches.open(CACHE).then((c) => c.put(req, clone));
          return res;
        })
        .catch(() => caches.match(req).then((r) => r || caches.match('/')))
    );
    return;
  }

  // Static assets → cache-first, then network (and cache the result)
  e.respondWith(
    caches.match(req).then((cached) =>
      cached ||
      fetch(req).then((res) => {
        if (res.ok) {
          const clone = res.clone();
          caches.open(CACHE).then((c) => c.put(req, clone));
        }
        return res;
      }).catch(() => cached)
    )
  );
});
