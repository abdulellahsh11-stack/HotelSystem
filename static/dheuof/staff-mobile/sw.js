/* ============================================================
   Dheuof Staff PWA — Service Worker v3
   استراتيجية: Cache-First للأصول الثابتة، Network-First للـ API
   ============================================================ */
const VER   = 'dheuof-staff-v3';
const SHELL = [
  '/static/dheuof/staff-mobile/index.html',
  '/static/dheuof/staff-mobile/manifest.json',
  '/static/dheuof/staff-mobile/icon-192.svg',
  '/static/dheuof/staff-mobile/icon-512.svg',
];

// ── تثبيت: خزّن shell التطبيق ──────────────────────────────
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(VER)
      .then(c => c.addAll(SHELL))
      .then(() => self.skipWaiting())
  );
});

// ── تفعيل: احذف النسخ القديمة ──────────────────────────────
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== VER).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// ── جلب: استراتيجية مزدوجة ─────────────────────────────────
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;

  // API calls — Network-first مع fallback بسيط
  if (url.pathname.startsWith('/api/')) {
    e.respondWith(
      fetch(e.request).catch(() =>
        new Response(JSON.stringify({ success: false, offline: true }),
          { headers: { 'Content-Type': 'application/json' } })
      )
    );
    return;
  }

  // Shell & assets — Cache-first، ثم شبكة وتخزين
  e.respondWith(
    caches.match(e.request).then(cached => {
      if (cached) return cached;
      return fetch(e.request).then(res => {
        if (res.ok) {
          const clone = res.clone();
          caches.open(VER).then(c => c.put(e.request, clone));
        }
        return res;
      }).catch(() =>
        // Offline fallback — أعد الـ shell
        caches.match('/static/dheuof/staff-mobile/index.html')
      );
    })
  );
});

// ── Background Sync — مزامنة المهام عند عودة الإنترنت ────────
self.addEventListener('sync', e => {
  if (e.tag === 'sync-tasks') {
    e.waitUntil(syncOfflineQueue());
  }
});

async function syncOfflineQueue() {
  // يُرسَل للـ API عند عودة الاتصال (مع queue في IndexedDB مستقبلاً)
  const clients = await self.clients.matchAll();
  clients.forEach(c => c.postMessage({ type: 'SYNC_DONE' }));
}

// ── Push Notifications ────────────────────────────────────────
self.addEventListener('push', e => {
  const data = e.data ? e.data.json() : {};
  const title = data.title || 'ضيوف · تطبيق الموظفين';
  const body  = data.body  || 'لديك إشعار جديد';
  const icon  = '/static/dheuof/staff-mobile/icon-192.svg';
  const badge = '/static/dheuof/staff-mobile/icon-192.svg';
  const tag   = data.tag   || 'dheuof-notif';
  const url   = data.url   || '/static/dheuof/staff-mobile/index.html?tab=tasks';

  e.waitUntil(
    self.registration.showNotification(title, {
      body, icon, badge, tag, dir: 'rtl', lang: 'ar',
      vibrate: [200, 100, 200],
      data: { url },
      actions: [
        { action: 'open',    title: 'فتح التطبيق' },
        { action: 'dismiss', title: 'تجاهل'        }
      ]
    })
  );
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  if (e.action === 'dismiss') return;
  const url = (e.notification.data && e.notification.data.url) ||
              '/static/dheuof/staff-mobile/index.html';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(cs => {
      const match = cs.find(c => c.url === url);
      if (match) return match.focus();
      return clients.openWindow(url);
    })
  );
});

// ── رسائل من التطبيق ─────────────────────────────────────────
self.addEventListener('message', e => {
  if (e.data === 'SKIP_WAITING') self.skipWaiting();
});
