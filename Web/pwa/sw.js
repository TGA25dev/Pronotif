const CACHE_NAME = 'pronotif-pwa-v13';

// Add this at the very top to force update
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
      self.skipWaiting();
    }
  });

const ASSETS_TO_CACHE = [
    './',
    './index.htm',
    './offline.htm',
    './styles/pwa-style.css',
    './styles/fonts.css',
    './styles/offline.css',
    './fonts/FixelVariable.ttf',
    './fonts/FixelVariableItalic.ttf',
    './scripts/pwa.js',
    './scripts/jsQR.js',
    './sw.js',
    '../Website/manifest.json',
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

// Activate event - Clean up old caches and take control of all clients
self.addEventListener('activate', (event) => {
    event.waitUntil(
        Promise.all([
            // Clean up old cache versions
            caches.keys().then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((cacheName) => {
                        if (cacheName !== CACHE_NAME) {
                            console.log('[PWA] Removing old cache:', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            }),
            // Take control of all clients ASAP
            self.clients.claim()
        ])
    );
});

// Helper function to check if we're actually online
function isOnline() {
    // Try to make a lightweight HEAD request to detect real connectivity
    return new Promise(resolve => {
        // Use Date.now() to prevent caching
        fetch('https://api.pronotif.tech/ping?' + Date.now(), { 
            method: 'HEAD',
            mode: 'no-cors',
            cache: 'no-store'
        })
        .then(() => resolve(true))
        .catch(() => resolve(false));
    }).catch(() => {
        // Fallback to navigator.onLine if the fetch fails
        return navigator.onLine;
    });
}

// Helper function to check if a request is for a font file
function isFontRequest(url) {
    return url.includes('/fonts/') || 
           url.endsWith('.ttf');
}

// Helper function to normalize URL paths for cache matching
function getCacheKey(request) {
    const url = new URL(request.url);
    
    // Handle font files specially
    if (isFontRequest(url.pathname)) {
        // Extract just the filename from the path
        const pathParts = url.pathname.split('/');
        const filename = pathParts[pathParts.length - 1];
        return `./fonts/${filename}`;
    }
    
    return request;
}

self.addEventListener('fetch', (event) => {

    console.log('[PWA] Fetch request for:', event.request.url, 'Online status:', isOnline());
    
    // Special handling for font requests
    if (isFontRequest(event.request.url)) {
        event.respondWith(
            // Try to match with normalized path
            caches.match(getCacheKey(event.request))
                .then(cachedResponse => {
                    if (cachedResponse) {
                        console.log('[PWA] Serving font from cache:', event.request.url);
                        return cachedResponse;
                    }
                    
                    console.log('[PWA] Font not found in cache with normalized path, trying exact match');
                    return caches.match(event.request)
                        .then(exactMatch => {
                            if (exactMatch) return exactMatch;
                            
                            // If font not in cache and we're online, try to fetch it
                            if (isOnline()) {
                                return fetch(event.request)
                                    .then(response => {
                                        if (!response.ok) return response;
                                        
                                        // Cache for future use with both keys
                                        const responseToCache = response.clone();
                                        caches.open(CACHE_NAME).then(cache => {
                                            cache.put(event.request, responseToCache.clone());
                                            // Also cache with normalized key
                                            cache.put(getCacheKey(event.request), responseToCache);
                                        });
                                        
                                        return response;
                                    });
                            }
                            
                            // If offline and font not cached, use system fonts
                            console.log('[PWA] Font not available offline:', event.request.url);
                            return new Response('', { 
                                status: 404,
                                headers: { 'Content-Type': 'text/plain' }
                            });
                        });
                })
        );
        return;
    }
    
    // Special handling for navigation requests (HTML pages)
    if (event.request.mode === 'navigate') {
        event.respondWith(
            (async () => {
                // Use the improved isOnline function
                const online = await isOnline();
                
                // Check if we're online first
                if (!online) {
                    console.log('[PWA] Offline detected, showing offline page');
                    const offlineResponse = await caches.match('./offline.htm');
                    if (offlineResponse) {
                        return offlineResponse;
                    }
                }    
                
                // Try network first, fall back to offline page
                try {
                    const networkResponse = await fetch(event.request);
                    return networkResponse;
                } catch (error) {
                    console.log('[PWA] Network request failed, showing offline page');
                    const offlineResponse = await caches.match('./offline.htm');
                    if (offlineResponse) {
                        return offlineResponse;
                    }
                    // If offline.htm isn't in cache , return a simple offline message
                    return new Response('Vous êtes hors ligne.<br>Merci de vérifier votre connexion Internet...', {
                        headers: { 'Content-Type': 'text/html' }
                    });
                }
            })()
        );
        return;
    }

    // For non-navigation requests, try cache first
    event.respondWith(
        caches.match(event.request)
            .then(cachedResponse => {
                if (cachedResponse) {
                    return cachedResponse;
                }
                
                // If not in cache and offline, return   fallback
                if (!isOnline()) {
                    console.log('[PWA] Offline and resource not in cache:', event.request.url);
                    if (event.request.destination === 'image') {
                        return new Response('', { status: 404 });
                    }
                    return new Response('Content not available offline');
                }
                
                return fetch(event.request)
                    .then(response => {
                        // Don't cache if response is not ok
                        if (!response.ok) {
                            return response;
                        }
                        
                        // Cache successful responses for static assets
                        if (event.request.url.includes('/fonts/') || 
                            event.request.url.includes('/styles/') || 
                            event.request.url.includes('/scripts/')) {
                            const responseToCache = response.clone();
                            caches.open(CACHE_NAME)
                                .then(cache => cache.put(event.request, responseToCache));
                        }
                        return response;
                    })
                    .catch(() => {
                        console.log('[PWA] Resource fetch failed:', event.request.url);
                        if (event.request.destination === 'image') {
                            return new Response('', { status: 404 });
                        }
                        return new Response('Content not available offline');
                    });
            })
    );
});