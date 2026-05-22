// Service worker for Clockpapi PWA
// Network-first for app shell (so updates land immediately),
// cache-first for icons/manifest (rarely change),
// pass-through for socket.io and dynamic /decks (never cache).
const CACHE = 'clockpapi-v1';
const STATIC_ASSETS = [
  '/static/manifest.json',
  '/static/icons/icon-192.svg',
  '/static/icons/icon-512.svg',
  '/static/icons/icon-maskable.svg',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC_ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  // Never intercept socket.io polling/websocket or live API endpoints
  if (url.pathname.startsWith('/socket.io') || url.pathname.startsWith('/decks')) return;
  if (e.request.method !== 'GET') return;

  // Cache-first for static icons/manifest
  if (url.pathname.startsWith('/static/')) {
    e.respondWith(
      caches.match(e.request).then(hit => hit || fetch(e.request).then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, copy));
        return res;
      }).catch(() => hit))
    );
    return;
  }

  // Network-first for the app shell ("/", index.html) with offline fallback
  if (url.pathname === '/' || e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request).then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put('/', copy));
        return res;
      }).catch(() => caches.match('/'))
    );
  }
});
