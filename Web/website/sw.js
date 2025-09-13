const CACHE_NAME = 'pronotif-v4';
const ASSETS_TO_CACHE = [
  '/download.html',
  '/scripts/download.js',
  '/styles/download-style.css',
  '../images/Website/Icons/Dark/share_icon_darkm.png',
  '../images/Website/Icons/Light/share_icon.png',
  '/manifest.json'
];

// Install event
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Attempting to cache assets...');
        
        // Cache assets individually to identify which ones fail
        return Promise.all(
          ASSETS_TO_CACHE.map(url => {
            return fetch(url)
              .then(response => {
                if (!response.ok) {
                  throw new Error(`Failed to fetch: ${url}, status: ${response.status}`);
                }
                return cache.put(url, response);
              })
              .then(() => {
                console.log(`Successfully cached: ${url}`);
              })
              .catch(error => {
                console.error(`Failed to cache: ${url}`, error);
                // Don't reject the promise, just log the error and continue
                // Return null to indicate this item failed but don't stop the overall process
                return null;
              });
          })
        ).then(results => {
          const failedCount = results.filter(result => result === null).length;
          if (failedCount > 0) {
            console.warn(`Completed with ${failedCount} failed items out of ${ASSETS_TO_CACHE.length}`);
          } else {
            console.log('All assets successfully cached!');
          }
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