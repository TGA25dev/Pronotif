// Import Firebase scripts
importScripts('https://www.gstatic.com/firebasejs/10.9.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.9.0/firebase-messaging-compat.js');

const CACHE_NAME = 'pronotif-pwa-v25';

// Global variable to store Firebase Messaging instance
let messaging = null;
let firebaseInitialized = false;


self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
      self.skipWaiting();
    } else if (event.data && event.data.type === 'FIREBASE_CONFIG') {
      const firebaseConfig = event.data.config;
      
      try {
        // Only initialize Firebase once
        if (!firebaseInitialized) {
          // Initialize Firebase with the received config
          firebase.initializeApp(firebaseConfig);
          messaging = firebase.messaging();
          
          // Set up background message handler
          messaging.onBackgroundMessage((payload) => {
            console.log('[sw.js] Received background message ', payload);
            
            // Just log the payload for debugging
            console.log('[sw.js] Background message payload:', payload);
          });
          
          firebaseInitialized = true;
          console.log('[Service Worker] Firebase Messaging initialized successfully');
        }
      } catch (error) {
        console.error('[Service Worker] Error initializing Firebase:', error);
      }
    }
});

self.addEventListener('push', function(event) {
  // This will be called when a push notification is received
  console.log('[Service Worker] Push Received:', event);
  
  // If we have payload data, create notification
  if (event.data) {
    try {
      const payload = event.data.json();
      console.log('[Service Worker] Push payload:', payload);
      
      // Avoid showing notification if it's just a data message
      // and we're on iOS (FCM will handle the notification display)
      const isIOSDevice = /iPhone|iPad|iPod/.test(self.navigator?.userAgent || '');
      const isDataOnlyMessage = !payload.notification && payload.data;
      
      if (isIOSDevice && isDataOnlyMessage) {
        console.log('[Service Worker] Skipping notification on iOS for data-only message');
        return;
      }
      
      const deepLink = payload.notification?.data?.deep_link || payload.data?.deep_link || 'https://pronotif.tech/pwa/index.htm';
      event.waitUntil(
          self.registration.showNotification(
              payload.notification?.title || 'Pronot\'if',
              {
                  body: payload.notification?.body || 'Nouvelle notification',
                  icon: '/Web/images/pwa/assets/icon-192x192.png',
                  tag: 'pronotif-notification',
                  renotify: false,
                  data: { deep_link: deepLink },
                  ...payload.notification
              }
          )
      );
    } catch (error) {
      console.error('[Service Worker] Error handling push event:', error);
    }
  }
});

self.addEventListener('pushsubscriptionchange', function(event) {
  console.log('[Service Worker] Push subscription change event received');
  // (Re-subscribe the user to push notifications)
});

self.addEventListener('notificationclick', function(event) {
  console.log('[Service Worker] Notification click received:', event);

  // Close the notification
  event.notification.close();

  // Handle notification click
  event.waitUntil(
    clients.openWindow(event.notification.data?.deep_link || 'https://pronotif.tech/pwa/index.htm')
  );
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
    '../manifest.json',
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
let onlineCheckPromise = null;
let lastOnlineCheck = { timestamp: 0, result: null };

function isOnline() {
    const now = Date.now();
    
    // If we have a recent cached result (within 5 seconds), use it
    if (now - lastOnlineCheck.timestamp < 5000 && lastOnlineCheck.result !== null) {
        return Promise.resolve(lastOnlineCheck.result);
    }
    
    // If there's already a check in progress, return that promise instead of starting a new one
    if (onlineCheckPromise) {
        return onlineCheckPromise;
    }
    
    // Otherwise, start a new check
    onlineCheckPromise = new Promise(resolve => {
        // Use a single timestamp for the check
        const checkTime = now;
        fetch('https://api.pronotif.tech/ping?' + checkTime, { 
            method: 'HEAD',
            mode: 'no-cors',
            cache: 'no-store'
        })
        .then(() => {
            lastOnlineCheck = { timestamp: now, result: true };
            resolve(true);
            // Clear the promise after a delay to allow new checks later
            setTimeout(() => { onlineCheckPromise = null; }, 1000);
        })
        .catch(() => {
            lastOnlineCheck = { timestamp: now, result: false };
            resolve(false);
            // Clear the promise after a delay to allow new checks later
            setTimeout(() => { onlineCheckPromise = null; }, 1000);
        });
    });
    
    return onlineCheckPromise;
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
    // Get the online status first (don't log it yet)
    const onlineStatusPromise = isOnline();
    
    // Log the request using the resolved online status
    onlineStatusPromise.then(isOnline => {
        console.log('[PWA] Fetch request for:', event.request.url, 'Online status:', isOnline);
    });
    
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