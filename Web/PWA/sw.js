const CACHE_NAME = 'pronotif-pwa-v1';
const ASSETS_TO_CACHE = [
    './',
    './index.html',
    './styles/pwa-style.css',
    './scripts/pwa.js',
];

// Install event - Cache all static assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[PWA] Caching app assets...');
                return cache.addAll(ASSETS_TO_CACHE);
            })
            .then(() => {
                console.log('[PWA] All assets cached successfully.');
            })
            .catch(error => {
                console.error('[PWA] Cache error:', error);
            })
    );
});

// Activate event - Clean up old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((name) => name.startsWith('pronotif-pwa-') && name !== CACHE_NAME)
                    .map((name) => {
                        console.log('[PWA] Removing old cache:', name);
                        return caches.delete(name);
                    })
            );
        })
    );
});

// Fetch event - Network first, falling back to cache
self.addEventListener('fetch', (event) => {
    event.respondWith(
        fetch(event.request)
            .catch(() => {
                return caches.match(event.request)
                    .then(response => {
                        if (response) {
                            return response;
                        }
                        // If the request fails and it's not in cache, try matching without the base path
                        const url = new URL(event.request.url);
                        const path = url.pathname.replace(/^\/Web\/pwa/, '');
                        return caches.match(new Request(path));
                    });
            })
    );
});