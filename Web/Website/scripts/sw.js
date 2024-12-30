const CACHE_NAME = 'pronotif-v1';
const ASSETS_TO_CACHE = [
  './',
  './download_page.html',
  './scripts/download.js',
  './styles/download-style.css',
  '../images/Website/Icons/Dark/share_icon_darkm.png',
  '../images/Website/Icons/Light/share_icon.png',
  './manifest.json'
];

// Install event
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Attempting to cache assets...');
        return cache.addAll(ASSETS_TO_CACHE)
          .then(() => {
            console.log('Assets successfully cached !');
          })
          .catch(error => {
            console.error('Cache addAll error:', error);
            return Promise.reject(error);
          });
      })
      .catch(error => {
        console.error('Service Worker installation failed:', error);
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