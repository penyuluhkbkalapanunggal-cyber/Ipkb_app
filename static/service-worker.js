const CACHE_NAME = 'ipkb-pwa-v1777570953';
const APP_SHELL = [
  '/', '/dashboard', '/iuran', '/laporan_kegiatan', '/offline',
  '/static/img/logo-title.png'
];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL).catch(()=>{})));
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    fetch(event.request).then(res => {
      const copy = res.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy)).catch(()=>{});
      return res;
    }).catch(() => caches.match(event.request).then(res => res || caches.match('/offline')))
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = event.notification.data && event.notification.data.url ? event.notification.data.url : '/dashboard';
  event.waitUntil(clients.matchAll({type:'window', includeUncontrolled:true}).then(clientList => {
    for (const client of clientList) {
      if ('focus' in client) return client.focus().then(() => client.navigate(url));
    }
    if (clients.openWindow) return clients.openWindow(url);
  }));
});
