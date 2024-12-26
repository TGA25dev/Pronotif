const CACHE_NAME = 'pronotif-v1';
const ASSETS_TO_CACHE = [
  '/Website/',
  '/Website/download_page.html',
  '/Website/scripts/download.js',
  '/Website/styles/download-style.css',
  '/Website/images/share_icon.png',
  '/Website/images/share_icon_darkm.png',
  '/Website/manifest.json'
];

// Install event
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        return cache.addAll(ASSETS_TO_CACHE);
      })
  );
});

// Activate event
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    })
  );
});

// Fetch event
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        return response || fetch(event.request);
      })
  );
});
