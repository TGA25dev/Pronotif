import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.9.0/firebase-app.js';
import { getMessaging, getToken } from 'https://www.gstatic.com/firebasejs/10.9.0/firebase-messaging.js';

// Custom debug logger
const originalConsole = {
    log: console.log.bind(console),
    error: console.error.bind(console),
    warn: console.warn.bind(console),
    info: console.info.bind(console)
};

const debugLogger = {
    logs: [],
    maxLogs: 100,
    
    formatTime() {
        const now = new Date();
        return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}.${now.getMilliseconds().toString().padStart(3, '0')}`;
    },
    
    formatMessage(message) {
        if (message === undefined) return 'undefined';
        if (message === null) return 'null';
        
        // Better error handling
        if (message instanceof Error || 
           (typeof message === 'object' && message.message && message.stack)) {
            return `Error: ${message.message}\n${message.stack || ''}`;
        }
        
        if (typeof message === 'object') {
            try {
                return JSON.stringify(message, null, 2);
            } catch (e) {
                return String(message);
            }
        }
        return String(message);
    },
    
    log(message, ...args) {
        const logEntry = {
            time: this.formatTime(),
            type: 'log',
            message: this.formatMessage(message),
            args: args.map(arg => this.formatMessage(arg))
        };
        this.logs.push(logEntry);
        this.trimLogs();
        originalConsole.log(`[${logEntry.time}]`, message, ...args);
        this.updateDebugPanel();
    },
    
    error(message, ...args) {
        const logEntry = {
            time: this.formatTime(),
            type: 'error',
            message: this.formatMessage(message),
            args: args.map(arg => this.formatMessage(arg))
        };
        this.logs.push(logEntry);
        this.trimLogs();
        originalConsole.error(`[${logEntry.time}]`, message, ...args);
        this.updateDebugPanel();
    },
    
    warn(message, ...args) {
        const logEntry = {
            time: this.formatTime(),
            type: 'warn',
            message: typeof message === 'object' ? JSON.stringify(message) : message,
            args: args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : arg)
        };
        this.logs.push(logEntry);
        this.trimLogs();
        originalConsole.warn(`[${logEntry.time}]`, message, ...args);
        this.updateDebugPanel();
    },
    
    info(message, ...args) {
        const logEntry = {
            time: this.formatTime(),
            type: 'info',
            message: typeof message === 'object' ? JSON.stringify(message) : message,
            args: args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : arg)
        };
        this.logs.push(logEntry);
        this.trimLogs();
        originalConsole.info(`[${logEntry.time}]`, message, ...args);
        this.updateDebugPanel();
    },
    
    trimLogs() {
        if (this.logs.length > this.maxLogs) {
            this.logs = this.logs.slice(-this.maxLogs);
        }
    },
    
    clear() {
        this.logs = [];
        this.updateDebugPanel();
    },
    
    updateDebugPanel() {
        const logContainer = document.getElementById('logContainer');
        if (!logContainer) return;
        
        logContainer.innerHTML = '';
        this.logs.forEach(log => {
            const entry = document.createElement('div');
            entry.className = `log-entry ${log.type}`;
            entry.textContent = `[${log.time}] ${log.type.toUpperCase()}: ${log.message} ${log.args.length ? log.args.join(' ') : ''}`;
            logContainer.appendChild(entry);
        });
        
        // Auto scroll to bottom
        logContainer.scrollTop = logContainer.scrollHeight;
    },
    
    getDeviceInfo() {
        const APP_VERSION = '0.8.0';
        const API_VERSION = 'v1';
        const API_BASE_URL = 'https://api.pronotif.tech';
        const VAPID_KEY = 'BMwPi20UcpJRPkeiE1ktEjuv2tNPHhMmc1M-xvIWXSuAEVmU0ct96APLCXDl51f_iWevhdrewii6No6QJ3OYcgY';
        
        const info = {
            app: {
                version: APP_VERSION,
                buildTime: new Date().toISOString(),
                debug: true,
                api: {
                    version: API_VERSION,
                    baseUrl: API_BASE_URL,
                    status: navigator.onLine ? 'connected' : 'offline'
                }
            },
            fcm: {
                vapidKey: `${VAPID_KEY.substring(0, 10)}...`,
                token: localStorage.getItem('fcmToken') || 'Not set',
                permission: Notification.permission,
                available: 'Notification' in window,
                serviceWorker: 'serviceWorker' in navigator,
                messaging: typeof firebase !== 'undefined' && firebase.messaging ? 'available' : 'not initialized'
            },
            device: {
                platform: /iPhone|iPad|iPod/.test(navigator.userAgent) ? 'iOS' : 
                         /Android/.test(navigator.userAgent) ? 'Android' : 'other',
                screen: {
                    width: window.innerWidth,
                    height: window.innerHeight,
                    dpr: window.devicePixelRatio,
                    orientation: window.screen.orientation?.type || 'unknown'
                },
                features: {
                    serviceWorker: 'serviceWorker' in navigator,
                    notifications: 'Notification' in window,
                    camera: 'mediaDevices' in navigator,
                    storage: 'storage' in navigator && 'estimate' in navigator.storage
                }
            },
            connection: navigator.connection ? {
                type: navigator.connection.effectiveType,
                speed: `${navigator.connection.downlink}Mbps`,
                saveData: navigator.connection.saveData
            } : 'Not available',
            storage: {
                quota: 'Checking...',
                usage: 'Checking...'
            }
        };

        // Add FCM token age if available
        const tokenTimestamp = localStorage.getItem('fcmTokenTimestamp');
        if (tokenTimestamp) {
            const age = Math.round((Date.now() - parseInt(tokenTimestamp)) / 1000 / 60);
            info.fcm.tokenAge = `${age} minutes`;
        }

        // Add service worker status
        if (navigator.serviceWorker) {
            navigator.serviceWorker.ready.then(registration => {
                info.fcm.swState = registration.active ? registration.active.state : 'no active worker';
                const deviceInfoEl = document.getElementById('deviceInfo');
                if (deviceInfoEl) {
                    deviceInfoEl.innerText = JSON.stringify(info, null, 2);
                }
            });
        }
        
        // Update storage info if available
        if (info.device.features.storage) {
            navigator.storage.estimate().then(({usage, quota}) => {
                info.storage = {
                    quota: `${Math.round(quota / 1024 / 1024)} MB`,
                    usage: `${Math.round(usage / 1024 / 1024)} MB`,
                    percentage: `${Math.round((usage / quota) * 100)}%`
                };
                
                const deviceInfoEl = document.getElementById('deviceInfo');
                if (deviceInfoEl) {
                    deviceInfoEl.innerText = JSON.stringify(info, null, 2);
                }
            });
        }
        
        return info;
    }
};

// Override console methods to capture logs
console.log = function(message, ...args) {
    if (message instanceof Error) {
        message = {
            message: message.message,
            stack: message.stack
        };
    }
    debugLogger.log(message, ...args);
};

console.error = function(message, ...args) {
    if (message instanceof Error) {
        message = {
            message: message.message,
            stack: message.stack
        };
    }
    debugLogger.error(message, ...args);
};

console.warn = function(message, ...args) {
    debugLogger.warn(message, ...args);
};

console.info = function(message, ...args) {
    debugLogger.info(message, ...args);
};

// Add network error interceptor
const originalFetch = window.fetch;
window.fetch = async function(...args) {
    const startTime = Date.now();
    try {
        const response = await originalFetch(...args);
        const endTime = Date.now();
        
        console.info(`[Network] ${args[0]} - ${response.status} (${endTime - startTime}ms)`);
        
        if (!response.ok) {
            console.error(`[Network Error] ${args[0]} - ${response.status} ${response.statusText}`);
        }
        return response;
    } catch (error) {
        console.error('[Network Error]', {
            url: args[0],
            error: error.message,
            stack: error.stack
        });
        throw error;
    }
};

async function initializeFirebase() {
    try {
        const response = await fetch('https://api.pronotif.tech/v1/app/firebase-config', {
            credentials: 'include',
            cache: 'no-store'
        });
        
        if (!response.ok) {
            const error = new Error('Authentication required');
            error.status = response.status;
            throw error;
        }
        
        const firebaseConfig = await response.json();
        console.log('Firebase config loaded successfully');
        
        // Validate config has required fields
        const requiredFields = ['apiKey', 'authDomain', 'projectId', 'messagingSenderId', 'appId'];
        for (const field of requiredFields) {
            if (!firebaseConfig[field]) {
                throw new Error(`Missing Firebase config value: "${field}"`);
            }
        }
        
        return initializeApp(firebaseConfig);
    } catch (error) {
        console.error('Failed to initialize Firebase:', {
            message: error.message,
            status: error.status,
            stack: error.stack
        });
        return null;
    }
}

document.addEventListener('DOMContentLoaded', async () => {

    if (!localStorage.getItem('notificationPermission')) {
        localStorage.setItem('notificationPermission', Notification.permission);
    }

    // Initialize Firebase
    const app = await initializeFirebase();
    let messaging = null;
    
    if (app) {
        try {
            messaging = getMessaging(app);
        } catch (error) {
            console.error("Failed to initialize messaging:", error);
        }
    } else {
        console.error("Firebase initialization failed - notifications will not work");
    }
    
    // Setup debug mode
    let tapCount = 0;
    const debugTrigger = document.getElementById('debugTrigger');
    const debugPanel = document.getElementById('debugPanel');
    const closeDebug = document.getElementById('closeDebug');
    const copyLogs = document.getElementById('copyLogs');
    const clearLogs = document.getElementById('clearLogs');
    const appVersionEl = document.querySelector('.app-version');
    
    // Initialize device info
    const deviceInfo = document.getElementById('deviceInfo');
    if (deviceInfo) {
        deviceInfo.innerText = JSON.stringify(debugLogger.getDeviceInfo(), null, 2);
    }
    
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('app-version')) {
            e.preventDefault();
            tapCount++;
            
            if (tapCount === 1) {
                setTimeout(() => {
                    tapCount = 0;
                }, 3000);
            }
            
            if (tapCount >= 5) {
                tapCount = 0;
                toggleDebugPanel();
            }
        }
    });
    
    function toggleDebugPanel() {
        debugPanel.classList.toggle('hidden');
        debugPanel.classList.toggle('visible');
        debugLogger.updateDebugPanel();
    }
    
    if (closeDebug) {
        closeDebug.addEventListener('click', toggleDebugPanel);
    }
    
    if (copyLogs) {
        copyLogs.addEventListener('click', () => {
            const logText = debugLogger.logs.map(log => 
                `[${log.time}] ${log.type.toUpperCase()}: ${log.message} ${log.args.join(' ')}`
            ).join('\n');
            
            navigator.clipboard.writeText(logText)
                .then(() => {
                    console.info('Logs copied to clipboard');
                    copyLogs.textContent = 'Copied!';
                    setTimeout(() => {
                        copyLogs.textContent = 'Copy Logs';
                    }, 2000);
                })
                .catch(err => {
                    console.error('Failed to copy logs:', err);
                });
        });
    }
    
    if (clearLogs) {
        clearLogs.addEventListener('click', () => {
            debugLogger.clear();
            console.info('Logs cleared');
        });
    }

    // Global functions
    function showFeedback(message, type) {
        const feedbackEl = document.getElementById('feedbackMessage');
        if (!feedbackEl) return;
        
        feedbackEl.innerHTML = message;
        feedbackEl.className = 'feedback-message';
        feedbackEl.classList.add(type);
        feedbackEl.style.display = 'block';
    }

    function hideFeedback() {
        const feedbackEl = document.getElementById('feedbackMessage');
        if (feedbackEl) feedbackEl.style.display = 'none';
    }
    
    // Function to show login view
    function showLoginView() {
        return new Promise((resolve) => {
            // Hide all views except loading
            document.querySelectorAll('.view:not(#loadingView)').forEach(view => {
                view.classList.add('hidden');
            });
    
            const loadingView = document.getElementById('loadingView');
            const loginView = document.getElementById('loginView');
            const spinner = document.getElementById('spinner');
    
            if (loadingView) {
                // First make it absolute positioned but still visible
                loadingView.classList.add('animating-out'); 
                // Then add the fade-out animation
                loadingView.classList.add('fade-out');
                
                setTimeout(() => {
                    // After animation completes, actually hide it
                    loadingView.classList.add('hidden');
                    loadingView.classList.remove('animating-out');
                    if (loginView) {
                        loginView.classList.remove('hidden');
                        loginView.classList.add('fade-in');
                    }
                    if (spinner) spinner.style.display = 'none';
                    resolve();
                }, 400);
            } else {
                // If no loading view, show login immediately
                if (loginView) {
                    loginView.classList.remove('hidden');
                    loginView.classList.add('fade-in');
                }
                if (spinner) spinner.style.display = 'none';
                resolve();
            }
        });
    }
    // Initialize DOM elements
    const cameraButton = document.getElementById('cameraButton');
    const cameraView = document.getElementById('cameraView');
    const feedbackMessage = document.getElementById('feedbackMessage');
    const spinner = document.getElementById('spinner');
    const infosQR = document.getElementById('infosQR');
    const welcomeGreeting = document.getElementById('welcomeGreeting');
    const allowNotifButton = document.getElementById('allowNotifButton');

    // Update checkExistingSession with better error handling
    function checkExistingSession() {
        if (!navigator.onLine) {
            console.warn('[Auth] Device is offline, showing login view');
            setTimeout(() => showLoginView(), 1000);
            return;
        }
    
        console.info('[Auth] Checking session...');
        fetch('https://api.pronotif.tech/v1/app/auth/refresh', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            signal: AbortSignal.timeout(2000),
            cache: 'no-store'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Auth refresh failed: ${response.status} ${response.statusText}`);
            }
            return response.json();
        })
        .then(() => {
            console.info('[Auth] Session refreshed successfully');
            setTimeout(() => showDashboard(), 1000);
        })
        .catch(error => {
            console.warn('[Auth] Session check failed:', error.message);
            setTimeout(() => showLoginView(), 1000);
        });
    }

    async function fetchFirebaseConfig() {
        const response = await fetch('https://api.pronotif.tech/v1/app/firebase-config', {
            credentials: 'include',
            cache: 'no-store'
        });
        
        if (!response.ok) throw new Error('Failed to get Firebase config');
        return response.json();
    }

    async function checkNotifEnabled() {
        if (!('Notification' in window)) {
            console.warn('This browser does not support notifications !');
            allowNotifButton.style.display = 'none';
            return false;
        }
        if (Notification.permission === 'granted') {
            allowNotifButton.style.display = 'none';
            
            try {
                if (!app) return false;

                // Get the Firebase config
                const firebaseConfig = await fetchFirebaseConfig();
                
                // Wait for service worker to be fully registered and active
                const swRegistration = await navigator.serviceWorker.ready;
                
                // Pass Firebase config to service worker
                swRegistration.active.postMessage({
                    type: 'FIREBASE_CONFIG',
                    config: firebaseConfig
                });
                
                console.log('[PWA] Firebase config sent to service worker');
                
                // Wait a moment for the service worker to process the config
                await new Promise(resolve => setTimeout(resolve, 500));
                
                const messaging = getMessaging(app);
                const vapidKey = 'BMwPi20UcpJRPkeiE1ktEjuv2tNPHhMmc1M-xvIWXSuAEVmU0ct96APLCXDl51f_iWevhdrewii6No6QJ3OYcgY';
                
                // Get the token
                const currentToken = await getToken(messaging, { 
                    vapidKey, 
                    serviceWorkerRegistration: swRegistration 
                });
    
                if (currentToken) {
                    console.log('FCM Registration Token:', currentToken);
                    sendFCMTokenToServer(currentToken);
                    return true;
                } else {
                    console.warn('No registration token available');
                    return false;
                }
                
            } catch (error) {
                console.error('Error getting FCM token:', error);
                return false;
            }
        }    

        if (Notification.permission !== 'denied' || Notification.permission === 'default') {
            allowNotifButton.style.display = 'block';
        }

        console.log('Notification permission:', Notification.permission);
        return false;
    }

    // Show only loading view initially
    document.querySelectorAll('.view').forEach(view => {
        view.classList.add('hidden');
    });
    document.getElementById('loadingView').classList.remove('hidden');
    
    // check session
    checkExistingSession();

    // Check for notifications permission
    checkNotifEnabled();

    // Ntification permission button
    if (allowNotifButton) {
        allowNotifButton.addEventListener('click', async () => {
            const permission = await Notification.requestPermission();
            console.info("Requesting notification permission...");
            if (permission === 'granted') {
                console.log('Notification permission granted!');
                allowNotifButton.style.display = 'none';
                
                try {
                    // Get the Firebase config
                    const firebaseConfig = await fetchFirebaseConfig();
                    
                    // Wait for service worker to be fully registered and active
                    const swRegistration = await navigator.serviceWorker.ready;
                    
                    // Pass Firebase config to service worker
                    swRegistration.active.postMessage({
                        type: 'FIREBASE_CONFIG',
                        config: firebaseConfig
                    });
                    
                    console.log('[PWA] Firebase config sent to service worker');
                    
                    // Wait a moment for the service worker to process the config
                    await new Promise(resolve => setTimeout(resolve, 500));
                    
                    const messaging = getMessaging(app);
                    const vapidKey = 'BMwPi20UcpJRPkeiE1ktEjuv2tNPHhMmc1M-xvIWXSuAEVmU0ct96APLCXDl51f_iWevhdrewii6No6QJ3OYcgY';
                    
                    // Get the token
                    const currentToken = await getToken(messaging, { 
                        vapidKey, 
                        serviceWorkerRegistration: swRegistration 
                    });
                    
                    if (currentToken) {
                        console.log('FCM Registration Token:', currentToken);
                        sendFCMTokenToServer(currentToken);
                    } else {
                        console.warn('No registration token available');
                    }
                    
                } catch (error) {
                    console.error('Error getting FCM token after permission granted:', error);
                }
            } else {
                console.log('Notification permission denied');
            }
        });
    }

    function isImageTooDark(imageData) {
        const data = imageData.data;
        let brightness = 0;
        
        // Sample every 20th pixel
        for (let i = 0; i < data.length; i += 80) {
            brightness += (data[i] + data[i + 1] + data[i + 2]) / 3;
        }
        
        const averageBrightness = brightness / (data.length / 80);
        return averageBrightness < 30; // Threshold
    }

    // Check if device is mobile
    function isMobileDevice() {
        const checks = {
            userAgent: /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent),
            touchPoints: navigator.maxTouchPoints > 2,
            platform: navigator.userAgentData?.platform ? /Android|iOS|iPhone|iPad/i.test(navigator.userAgentData.platform) : /Android|iOS|iPhone|iPad/i.test(navigator.userAgent),
            screenSize: window.innerWidth <= 1024 && window.innerHeight <= 1366,
            orientation: 'orientation' in window
        };
        
        console.log('Mobile device checks:', Object.values(checks).filter(Boolean).length, '/', Object.keys(checks).length);
        return Object.values(checks).filter(Boolean).length >= 4;

    }

    if (!isMobileDevice()) {
        document.body.innerHTML = '<div class="device-error">Désolé mais l\'application est uniquement disponible sur mobile... 😐</div>';
        console.warn('The device is not mobile, stopping PWA initialization.');
        return;
    }

    // Service Worker Registration
    if ('serviceWorker' in navigator) {
        
        const SW_VERSION = '1.0.1'; 
        const swUrl = `sw.js?v=${SW_VERSION}`;
        
        navigator.serviceWorker.register(swUrl, {
            scope: './'
        }).then(registration => {
            console.log('[PWA] Service worker registered');
            
            // Check for updates but don't force them
            registration.addEventListener('updatefound', () => {
                const newWorker = registration.installing;
                console.log('[PWA] New service worker installing');
                
                newWorker.addEventListener('statechange', () => {
                    console.log('[PWA] Service worker state:', newWorker.state);
                    
                    if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                        // New service worker available, but let's not force activation immediately
                        console.log('[PWA] New service worker available. Refresh to update.');
                        // add toast message for new update ?
                    }
                });
            });
        }).catch(error => {
            console.error('[PWA] Service worker registration failed:', error);
        });
    }

    // Show dashboard
    function showDashboard() {
        console.log('[UI] Starting dashboard transition');
        // Hide the spinner when showing dashboard
        const spinner = document.getElementById('spinner');
        if (spinner) spinner.style.display = 'none';
        // Get the login view and loading view
        const loginView = document.getElementById('loginView');
        const loadingView = document.getElementById('loadingView');

        if (dashboardView) {
            dashboardView.classList.add('hidden');
            dashboardView.classList.remove('fade-in');
        }

        if (loginView && !loginView.classList.contains('hidden')) {
            loginView.classList.add('animating-out');
            loginView.classList.add('fade-out');
            console.log('[UI] Fading out login view');
        }

        if (loadingView && !loadingView.classList.contains('hidden')) {
            loadingView.classList.add('animating-out');
            loadingView.classList.add('fade-out');
            console.log('[UI] Fading out loading view');
        }

        setTimeout(() => {
            console.log('[UI] Animation complete, showing dashboard');
            
            // Hide all views
            document.querySelectorAll('.view').forEach(view => {
                view.classList.add('hidden');
                view.classList.remove('animating-out');
                view.classList.remove('fade-out');
                view.classList.remove('fade-in');
            });
            
            // Show dashboard with animation
            if (dashboardView) {
                dashboardView.classList.remove('hidden');
                dashboardView.classList.add('fade-in');
            }
            
            // Start loading dashboard data
            initializeDashboard();
        }, 400);
    }

    // Dashboard initialization
    function initializeDashboard() {
        fetch("https://api.pronotif.tech/v1/app/fetch", {
            method: 'GET',
            headers: { 
                'Content-Type': 'application/json',
            },
            credentials: 'include', // Send cookies
            signal: AbortSignal.timeout(2000)
        })
        .then(response => response.json())
        .then(data => {
            console.log('Dashboard data:', data);

            const studentFirstName = data.data?.student_firstname;
            const welcomeElement = document.getElementById('welcomeGreeting');
            
            // Update the welcome message
            if (welcomeElement && studentFirstName) {
                welcomeElement.textContent = `Bonjour ${studentFirstName} !`;
            }
            
            // Check if notification permission was revoked
            checkNotificationPermissionChange();
        })
        .catch(error => {
            console.error('Dashboard data fetch failed:', error);
            showFeedback('Unable to load dashboard. Please try again.', 'error');
        });
    }
    
    // Check if notification permission has change
    function checkNotificationPermissionChange() {
        const currentPermission = Notification.permission;
        const storedPermission = localStorage.getItem('notificationPermission');
        
        // Update stored permission
        localStorage.setItem('notificationPermission', currentPermission);
        
        // If permission was previously granted but is now denied or default (revoked)
        if (storedPermission === 'granted' && currentPermission !== 'granted') {
            console.log('[Notifications] Permission was revoked, removing FCM token');
            revokeFCMToken();
        }
        
        // Update notification button visibility
        if (allowNotifButton) {
            if (currentPermission === 'granted') {
                allowNotifButton.style.display = 'none';
            } else if (currentPermission === 'default') {
                allowNotifButton.style.display = 'block';
            }
        }
    }
    
    // Revoke FCM token on the server
    async function revokeFCMToken() {
        const token = localStorage.getItem('fcmToken');
        if (!token) {
            console.log('[Notifications] No token to revoke');
            return;
        }
        
        try {
            const response = await fetch('https://api.pronotif.tech/v1/app/revoke-fcm-token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fcm_token: token }),
                credentials: 'include'
            });
            
            if (response.ok) {
                console.log('[Notifications] FCM token revoked successfully');
                localStorage.removeItem('fcmToken');
                localStorage.removeItem('fcmTokenTimestamp');
                
                // Update debug panel
                const deviceInfoEl = document.getElementById('deviceInfo');
                if (deviceInfoEl) {
                    deviceInfoEl.innerText = JSON.stringify(debugLogger.getDeviceInfo(), null, 2);
                }
            } else {
                console.error('[Notifications] Failed to revoke FCM token:', response.status);
            }
        } catch (error) {
            console.error('[Notifications] Error revoking FCM token:', error);
        }
    }

    // Camera Permission
    cameraButton.addEventListener('click', async () => {
        try {
            console.info('Requesting camera access...');
            // Try back camera first
            const constraints = {
                video: {
                    facingMode: { exact: 'environment' },
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                },
                audio: false
            };

            let stream;
            try {
                stream = await navigator.mediaDevices.getUserMedia(constraints); //Get the stream (camera)
                console.log('Camera access granted!');
                const errorDiv = document.querySelector('.camera-error');
                if (errorDiv) errorDiv.remove();

            } catch (backCameraError) {
                console.log('Back camera not available, trying front camera');
                stream = await navigator.mediaDevices.getUserMedia({ //Fallback to front camera
                    video: { facingMode: 'user' }
                });
            }

            cameraView.srcObject = stream;
            cameraView.style.display = 'block';
            cameraButton.style.display = 'none';
            infosQR.style.display = 'block';

            // Start QR code scanning
            function startQRScanning() {
                console.log('Starting QR code scanning...');
                const canvasElement = document.getElementById('canvas');
                const ctx = canvasElement.getContext('2d', { willReadFrequently: true });
                let isProcessing = false;
                let lastScanTime = 0;
                const scanInterval = 100;

                const scan = () => {
                    const now = Date.now();
                    if (now - lastScanTime < scanInterval) {
                        requestAnimationFrame(scan);
                        return;
                    }

                    if (cameraView.readyState === cameraView.HAVE_ENOUGH_DATA && !isProcessing) {
                        lastScanTime = now;
                        canvasElement.width = cameraView.videoWidth;
                        canvasElement.height = cameraView.videoHeight;
                        ctx.drawImage(cameraView, 0, 0, canvasElement.width, canvasElement.height);
                        const imageData = ctx.getImageData(0, 0, canvasElement.width, canvasElement.height);
                        
                        // Skip processing if the image is too dark
                        if (isImageTooDark(imageData)) {
                            requestAnimationFrame(scan);
                            return;
                        }
                        
                        const code = jsQR(imageData.data, canvasElement.width, canvasElement.height);

                        if (code) {
                            try {
                                // Verify if the data looks like a valid QR code string
                                if (!code.data || typeof code.data !== 'string' || code.data.trim() === '') {
                                    showFeedback('QR code invalide (empty data)', 'error');
                                    console.warn('Invalid QR code data:', code.data);
                                    setTimeout(() => {
                                        hideFeedback();
                                    }, 3000);
                                    requestAnimationFrame(scan);
                                    return;
                                }

                                // Try to parse as JSON
                                let qrData;
                                try {
                                    qrData = JSON.parse(code.data);
                                } catch (parseError) {
                                    showFeedback('Ce QR code n\'est pas un QR code Pronot\'if valide', 'error');
                                    console.warn('QR code parse error:', parseError);
                                    setTimeout(() => {
                                        hideFeedback();
                                    }, 3000);
                                    requestAnimationFrame(scan);
                                    return;
                                }
                                
                                // Verify if the parsed data
                                if (!qrData.session_id || !qrData.token) {
                                    showFeedback('QR code invalide', 'error');
                                    console.warn('Invalid QR code format:', qrData);
                                    setTimeout(() => {
                                        hideFeedback();
                                    }, 3000);
                                    requestAnimationFrame(scan);
                                    return;
                                }

                                console.log('Raw QR data:', qrData);

                                // Convert None values to "0"strings
                                const convertToString = (value) => {
                                    if (value === "None") return "0";
                                    return value;
                                };

                                // Map the data
                                const mappedData = {
                                    session_id: qrData.session_id,
                                    token: qrData.token,
                                    login_page_link: qrData.login_page_link,
                                    student_username: qrData.student_username,
                                    student_password: qrData.student_password,
                                    student_fullname: qrData.student_fullname,
                                    student_firstname: qrData.student_firstname,
                                    student_class: qrData.student_class,
                                    ent_used: convertToString(qrData.ent_used),
                                    lunch_times: convertToString(qrData.lunch_times),
                                    qr_code_login: convertToString(qrData.qr_code_login),
                                    uuid: qrData.uuid === "None" ? "00000000-0000-0000-0000-000000000000" : qrData.uuid,
                                    topic_name: qrData.topic_name,
                                    timezone: qrData.timezone,
                                    notification_delay: qrData.notification_delay,
                                    evening_menu: convertToString(qrData.evening_menu),
                                    unfinished_homework_reminder: convertToString(qrData.unfinished_homework_reminder),
                                    get_bag_ready_reminder: convertToString(qrData.get_bag_ready_reminder)
                                };


                                isProcessing = true;
                                cameraView.classList.add('loading');
                                
                                // Create overlay with spinner
                                const overlay = document.createElement('div');
                                overlay.className = 'overlay';
                                const loadingSpinner = document.createElement('div');
                                loadingSpinner.className = 'spinner-large';
                                overlay.appendChild(loadingSpinner);
                                document.body.appendChild(overlay);
                                
                                document.body.style.opacity = '0.7';
                                showFeedback('QR code detected, processing...', 'info');

                                console.log('Sending data to API...');

                                fetch('https://api.pronotif.tech/v1/app/qrscan', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify(mappedData),
                                    credentials: 'include',
                                    signal: AbortSignal.timeout(2000)

                                    
                                })
                                .then(async response => {
                                    if (!response.ok) {
                                        let errorMessage;
                                        switch (response.status) {
                                            case 429:
                                                errorMessage = 'Too many attempts. Please wait a moment.';
                                                break;
                                            case 400:
                                                const serverResponse = await response.text();
                                                errorMessage = `Invalid request: ${serverResponse}`;
                                                break;
                                            case 401:
                                                errorMessage = 'Invalid or expired session.';
                                                break;
                                            case 500:
                                                errorMessage = 'Server error. Please try again later.';
                                                break;
                                            default:
                                                errorMessage = `Server error (${response.status})`;
                                        }
                                        throw new Error(errorMessage);
                                    }
                                    return response.json();
                                })
                                .then(apiResponse => { // Successfully logged in 
                                    console.log('QR scan API response:', apiResponse);
                                    
                                    setTimeout(() => {
                                        // Remove overlay
                                        const overlay = document.querySelector('.overlay');
                                        if (overlay) overlay.remove();
                                        
                                        document.body.style.opacity = '1';
                                        isProcessing = false;
                                        cameraView.classList.remove('loading');
                                        hideFeedback();
                                        showDashboard();
                                    }, 3000);
                                })
                                .catch(error => {
                                    console.error('Error:', error);
                                    document.body.style.opacity = '1';
                                    showFeedback(error.message || 'Error processing QR code. Please try again.', 'error');
                                    
                                    // Remove overlay
                                    const overlay = document.querySelector('.overlay');
                                    if (overlay) overlay.remove();
                                    
                                    setTimeout(() => {
                                        isProcessing = false;
                                        cameraView.classList.remove('loading');
                                        hideFeedback();
                                        spinner.style.display = 'none';
                                    }, 3000);
                                });

                            } catch (parseError) {
                                console.error('QR code parse error:', parseError);
                                showFeedback('Invalid QR code format', 'error');
                                setTimeout(() => {
                                    isProcessing = false;
                                    cameraView.classList.remove('loading');
                                    hideFeedback();
                                    spinner.style.display = 'none';
                                }, 3000);
                            }
                        } else {
                            // Don't show spinner when no QR code is detected
                            spinner.style.display = 'none';
                        }
                    }
                    requestAnimationFrame(scan);
                };

                scan();
            }
            startQRScanning();

        } catch (err) {
            console.error('Camera access denied:', err);
            
            // Check if error message already exists
            if (!document.querySelector('.camera-error')) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'camera-error';
                
                if (err.name === 'NotAllowedError') {
                    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
                    const isAndroid = /Android/.test(navigator.userAgent);

                    let settingsUrl = '';
                    let message = '';

                    if (isIOS) {
                        settingsUrl = '';
                        message = 'Accès à la caméra refusé 😔<br>Impossible de continuer...';

                    } else if (isAndroid) {
                        settingsUrl = "intent://#Intent;action=android.settings.SETTINGS;category=android.intent.category.DEFAULT;end;";
                        message = 'Accès à la caméra refusé 😔<br>Ouvrez les paramètres pour continuer.';

                    } else {
                        message = 'Accès à la caméra refusé 😔<br>Ouvrez les paramètres pour autoriser l\'accès à la caméra';
                    }

                    errorDiv.innerHTML = `
                        <div class="error-message">
                            ${message}
                            ${!isIOS ? `
                            <button class="settings-button" onclick="${isAndroid ? `window.location.href='${settingsUrl}'` : 'window.location.reload()'}">
                                ${isAndroid ? '⚙️ Ouvrir les paramètres' : '🔄 Réessayer'}
                            </button>
                            ` : ''}
                        </div>
                    `;
                } else {
                    errorDiv.innerHTML = `
                        Impossible d'accéder à la caméra 😔
                        <button class="settings-button" onclick="window.location.reload()">
                            🔄 Réessayer
                        </button>
                    `;
                }
                
                cameraButton.parentNode.insertBefore(errorDiv, cameraButton.nextSibling);
            }
        }
    });

    // Send FCM token to server
    async function sendFCMTokenToServer(token) {
        try {
            const response = await fetch('https://api.pronotif.tech/v1/app/fcm-token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fcm_token: token }),
                credentials: 'include'
            });
            
            const data = await response.json();
            if (data.status === 200) {
                console.log('FCM token saved on server successfully');
                localStorage.setItem('fcmToken', token);
                localStorage.setItem('fcmTokenTimestamp', Date.now().toString());
                // Update debug panel
                const deviceInfoEl = document.getElementById('deviceInfo');
                if (deviceInfoEl) {
                    deviceInfoEl.innerText = JSON.stringify(debugLogger.getDeviceInfo(), null, 2);
                }
            } else {
                console.error('Failed to save FCM token on server:', data.error);
            }
        } catch (error) {
            console.error('Error sending FCM token to server:', error);
        }
    }

    // Handle FCM token registration when notifications are enabled
    async function registerFCMToken() {
        if (!app || !messaging) {
            console.error('Firebase not initialized');
            return null;
        }

        try {
            const swRegistration = await navigator.serviceWorker.ready;
            const vapidKey = 'BMwPi20UcpJRPkeiE1ktEjuv2tNPHhMmc1M-xvIWXSuAEVmU0ct96APLCXDl51f_iWevhdrewii6No6QJ3OYcgY';
            
            const currentToken = await getToken(messaging, { 
                vapidKey, 
                serviceWorkerRegistration: swRegistration 
            });

            if (currentToken) {
                console.log('FCM token acquired');
                localStorage.setItem('fcmToken', currentToken);
                await sendFCMTokenToServer(currentToken);
                return currentToken;
            } else {
                console.warn('No FCM token available');
                return null;
            }
        } catch (error) {
            console.error('Error getting FCM token:', error);
            return null;
        }
    }

    // Set up a listener for service worker messages about token refresh
    if (navigator.serviceWorker) {
        navigator.serviceWorker.addEventListener('message', event => {
            if (event.data && event.data.type === 'TOKEN_REFRESH') {
                console.log('Token refresh event received');
                if (app) {  // Check if Firebase app exists before proceeding
                    registerFCMToken().then(token => {
                        if (token) {
                            sendFCMTokenToServer(token);
                        }
                    });
                } else {
                    console.warn('Cannot refresh token: Firebase not initialized');
                }
            }
        });
    }
});