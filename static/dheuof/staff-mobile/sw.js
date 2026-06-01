const CACHE = 'dheuof-staff-v1';
const PRECACHE = [
  '/static/dheuof/staff-mobile/index.html',
  '/static/dheuof/staff-mobile/mobile.css',
  '/static/dheuof/staff-mobile/Screens.jsx',
  '/static/dheuof/staff-mobile/ios-frame.jsx',
  '/static/dheuof/staff-mobile/manifest.json',
  '/static/dheuof/colors_and_type.css',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request).then(res => {
      if (res.ok && e.request.url.startsWith(self.location.origin)) {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
      }
      return res;
    }))
  );
});
