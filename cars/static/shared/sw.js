/* ============================================================
   سيارتي - Service Worker
   استراتيجية: Network-first مع تخزين مؤقت لكل الردود الناجحة.
   يعمل أوفلاين: عند انقطاع النت تُعرض آخر نسخة محفوظة.
   ============================================================ */

var CACHE_NAME = 'sayarti-v1';
var CORE_ASSETS = [
  '/',
  '/manifest.json',
  '/static/css/style.css',
  '/static/css/home.css',
  '/static/js/main.js',
  '/static/js/home.js',
  '/static/shared/icons/icon-192.png',
  '/static/shared/icons/icon-512.png',
  '/static/shared/icons/icon-maskable-512.png'
];

self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(CORE_ASSETS);
    }).catch(function() {
      /* تجاهل فشل أي عنصر اختياري - لا نريد كسر التثبيت */
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) {
          return k !== CACHE_NAME;
        }).map(function(k) {
          return caches.delete(k);
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', function(event) {
  var request = event.request;
  if (request.method !== 'GET') return;

  var url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).then(function(response) {
        var copy = response.clone();
        caches.open(CACHE_NAME).then(function(cache) {
          cache.put(request, copy);
        });
        return response;
      }).catch(function() {
        return caches.match(request).then(function(cached) {
          return cached || caches.match('/');
        });
      })
    );
    return;
  }

  event.respondWith(
    fetch(request).then(function(response) {
      var copy = response.clone();
      caches.open(CACHE_NAME).then(function(cache) {
        cache.put(request, copy);
      });
      return response;
    }).catch(function() {
      return caches.match(request);
    })
  );
});