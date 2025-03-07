const CACHE_NAME = 'pronotif-pwa-v2';
const ASSETS_TO_CACHE = [
    './',
    './index.htm',
    './styles/pwa-style.css',
    './styles/fonts.css',
    './fonts/FixelVariable.ttf',
    './fonts/FixelVariableItalic.ttf',
    './scripts/pwa.js',
    './scripts/jsQR.js'
];

// Install event - Cache all static assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[PWA] Attempting to cache assets...');
                return Promise.all(
                    ASSETS_TO_CACHE.map(url => {
                        return cache.add(url).catch(error => {
                            console.warn(`[PWA] Failed to cache ${url}:`, error);
                            return Promise.resolve();
                        });
                    })
                );
            })
            .then(() => {
                console.log('[PWA] Assets cached successfully');
                return self.skipWaiting(); // Take control immediately
            })
    );
});

self.addEventListener('fetch', (event) => {
    event.respondWith(
        caches.match(event.request)
            .then(cachedResponse => {
                if (cachedResponse) {
                    return cachedResponse;
                }
                return fetch(event.request)
                    .then(response => {
                        // Don't cache if response is not ok or is a browser-extension request
                        if (!response.ok || event.request.url.startsWith('chrome-extension://')) {
                            return response;
                        }
                        
                        // Cache successful font responses
                        if (event.request.url.includes('/fonts/')) {
                            const responseToCache = response.clone();
                            caches.open(CACHE_NAME)
                                .then(cache => cache.put(event.request, responseToCache));
                        }
                        return response;
                    })
                    .catch(() => {
                        // Offline fallback
                        if (event.request.mode === 'navigate') {
                            return caches.match('./offline.htm');
                        }
                        return new Response('Content not available offline');
                    });
            })
    );
});