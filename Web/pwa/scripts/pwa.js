import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.9.0/firebase-app.js';
import { getMessaging, getToken } from 'https://www.gstatic.com/firebasejs/10.9.0/firebase-messaging.js';
const VAPID_KEY = 'BMwPi20UcpJRPkeiE1ktEjuv2tNPHhMmc1M-xvIWXSuAEVmU0ct96APLCXDl51f_iWevhdrewii6No6QJ3OYcgY';

const nativeFetch = window.fetch.bind(window);

let app = null;
let messaging = null;

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
        const APP_VERSION = '0.8.1';
        const API_VERSION = 'v1';
        const API_BASE_URL = 'https://api.pronotif.tech';
        
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

window.fetch = async function(...args) {
    const start = performance.now();
    try {
        const res = await nativeFetch(...args);  // was __nativeFetch
        console.info(`[Network] ${args[0]} - ${res.status} (${Math.round(performance.now() - start)}ms)`);
        if (!res.ok) console.error(`[Network Error] ${args[0]} - ${res.status} ${res.statusText}`);
        return res;
    } catch (e) {
        console.error('[Network Error]', { url: args[0], error: e.message });
        throw e;
    }
};

function getCookie(name) {
    return document.cookie
        .split(';')
        .map(c => c.trim())
        .filter(c => c.startsWith(name + '=' ))
        .map(c => decodeURIComponent(c.substring(name.length + 1)))[0] || null;
}

async function ensureCsrfToken() {
    if (!getCookie('csrf_token')) {
        try {
            await fetch('https://api.pronotif.tech/ping', {
                credentials: 'include',
                cache: 'no-store'
            });
        } catch(e) {
            console.warn('Failed to prefetch CSRF token:', e);
        }
    }
    return getCookie('csrf_token');
}

//wrapper that auto‑adds X-CSRF-Token
async function wrapFetch(url, options = {}) {
    const method = (options.method || 'GET').toUpperCase();
    if (['POST','PUT','PATCH','DELETE'].includes(method)) {
        const token = await ensureCsrfToken();
        options.headers = options.headers || {};
        if (token) {
            options.headers['X-CSRF-Token'] = token;
        } else {
            console.warn('[CSRF] Missing token for', url);
        }
    }
    return nativeFetch(url, options);
}

function getGreeting() {
    const now = new Date();
    const hour = now.getHours();
    const minute = now.getMinutes();

    //time based greetings
    if (hour >= 5 && hour < 18) {
        return "Bonjour";
    } else if (hour >= 18 && hour < 22) {
        return "Bonsoir";
    } else {
        return "Bonne nuit";
    }
}

function getTimeEmoji() {
    const now = new Date();
    const hour = now.getHours();
    const day = now.getDay(); // 0 = Sunday, 6 = Saturday
    const isWeekend = day === 0 || day === 6;

    // Weekend variations
    if (isWeekend) {
        if (hour >= 8 && hour < 12) return "☕";
        if (hour >= 12 && hour < 14) return "🍽️";
        if (hour >= 14 && hour < 17) return "🏖️";
        if (hour >= 17 && hour < 22) return "🎮";
    }

    if (hour >= 5 && hour < 9) {
        return "🌅";
    } else if (hour >= 9 && hour < 18) {
        return "👋";
    } else if (hour >= 18 && hour < 23) {
        return "🌙";
    } else {
        return "🌃";
    }
}

function getSubtitle() {
    const now = new Date();
    const hour = now.getHours();
    const day = now.getDay(); // 0 = Sunday, 6 = Saturday
    const isWeekend = day === 0 || day === 6;
    
    let subtitles = [];
    
    if (isWeekend) {
        // Weekend subtitles
        subtitles = [
            "Profitez de votre temps libre",
            "Une pause bien méritée",
            "C'est le week-end !",
            "C’est enfin le week-end",
        ];

    } else {
        // Weekday subtitles
        if (hour >= 5 && hour < 8) {
            subtitles = [
                "Une nouvelle journée commence",
                "Courage pour cette journée",
                "Prêt·e pour aujourd’hui ?",
                "Bien réveillé.e ?",
            ];
        } else if (hour >= 8 && hour < 12) {
            subtitles = [
                "Voici un rapide aperçu de votre journée",
                "Votre matinée en un clin d'œil",
            ];
        } else if (hour >= 12 && hour < 14) {
            subtitles = [
                "C'est l'heure du déjeuner",
                "Bon appétit !",
                "Profitez de votre pause déjeuner",
            ];
        } else if (hour >= 14 && hour < 17) {
            subtitles = [
                "Plus que quelques heures",
                "Vous y êtes presque",
                "Passez une bonne après midi"
            ];
        } else if (hour >= 17 && hour < 22) {
            subtitles = [
                "Reposez vous bien",
                "Prenez un moment pour souffler",
                "Fin de journée en vue",
            ];
        } else {
            subtitles = [
                "Il est temps de se reposer",
                "Préparez vous pour demain",
                "Récupérez bien",
                "À demain pour une nouvelle journée !"
            ];
        }
    }
    
    // Return a random subtitle from the appropriate array
    return subtitles[Math.floor(Math.random() * subtitles.length)];
}

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

// Login functionality handler object
const loginHandler = {
    // City search button handler
    handleCitySearchButtonClick() {
        console.log("[LOGIN DEBUG] Search City button pressed!");

        // Get DOM elements properly
        const loginHeaderAppTitle = document.getElementById('loginHeaderAppTitle');
        const loginHeaderAppSubTitle = document.getElementById('loginHeaderAppSubTitle');
        const loginCardContainerTitle = document.getElementById('loginCardContainerTitle');
        const loginOptionsContainer = document.getElementById('loginOptionsContainer');
        const globalLoginContainerButton = document.getElementById('globalLoginContainerButton');
        const globalLoginContainerInput = document.getElementById('globalLoginContainerInput');

        loginHeaderAppTitle.textContent = "C'est parti !";
        loginHeaderAppSubTitle.textContent = "Etape 1 sur 3";

        loginCardContainerTitle.textContent = "Recherchez votre ville";
        loginOptionsContainer.style.display = "none";

        globalLoginContainerButton.style.display = "block";
        globalLoginContainerInput.style.display = "block";

        globalLoginContainerButton.textContent = "Rechercher";
        globalLoginContainerInput.placeholder = "Entrez le nom de votre ville";
        
        const self = this;
        globalLoginContainerButton.onclick = function() {
            self.handleCitySearch();
        };
    },

    handleManualLink() {
        const globalLoginContainerInput = document.getElementById('globalLoginContainerInput');
        const globalLoginContainerButton = document.getElementById('globalLoginContainerButton');
        
        const manualPronoteLink = globalLoginContainerInput.value.trim();

        if (!manualPronoteLink) {
            console.error("[MANUAL LINK] Error: Empty Pronote link");
            alert("Veuillez entrer le lien Pronote de votre établissement.");
            return;
        }

        console.log(`[MANUAL LINK] Verifying link: "${manualPronoteLink}"`);

        const self = this;
        self.verifyManualPronoteLink(manualPronoteLink)

        .then(result => {
            if (result && result.isValid) {
                const school = { nomEtab: result.nomEtab };
                console.log("[MANUAL LINK] Link verified successfully:", manualPronoteLink);
                self.handleSchoolSelection(school, manualPronoteLink, null, null, null, result.region);
            } else {
                console.error("[MANUAL LINK] Link verification failed or was unverified.");
            }
        })
        .catch(error => {
            console.error("[MANUAL LINK] Verification error:", error);
        })
        .finally(() => {
            // Reset button state
            globalLoginContainerButton.disabled = false;
            globalLoginContainerButton.textContent = "Rechercher";
        });

    },
    
    handleCitySearch() {
        console.log("[SEARCH DEBUG] Search button clicked");
        
        const globalLoginContainerInput = document.getElementById('globalLoginContainerInput');
        const globalLoginContainerButton = document.getElementById('globalLoginContainerButton');
        
        const cityName = globalLoginContainerInput.value.trim();
        
        if (!cityName) {
            console.error("[SEARCH] Error: Empty city name");
            alert("Veuillez entrer le nom de votre ville.");
            return;
        }
        
        // Show loading state
        globalLoginContainerButton.disabled = true;
        globalLoginContainerButton.style.cursor = "not-allowed";
        globalLoginContainerButton.style.opacity = "0.6";
        globalLoginContainerButton.textContent = "Recherche en cours...";
        
        // Prepare API query parameters
        const apiUrl = `https://api.pronotif.tech/v1/login/get_schools?coords=false&city_name=${encodeURIComponent(cityName)}`;
        
        console.log(`[SEARCH] Searching for city: "${cityName}" with URL: ${apiUrl}`);
        
        wrapFetch(apiUrl, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Error ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            // Reset button state
            globalLoginContainerButton.disabled = false;
            globalLoginContainerButton.textContent = "Rechercher";

            globalLoginContainerButton.style.cursor = "pointer";
            globalLoginContainerButton.style.opacity = "1";
            
            console.log("[SEARCH] Results:", data);

            const self = this;
            self.handleScoolResultsDisplay(data);
        })
        .catch(error => {
            console.error("[SEARCH] Search failed:", error);
            alert("Une erreur est survenue lors de la recherche. Veuillez réessayer plus tard.");
        })
        .finally(() => {
            
            // Reset button state
            globalLoginContainerButton.disabled = false;
            globalLoginContainerButton.textContent = "Rechercher";

            globalLoginContainerButton.style.cursor = "pointer";
            globalLoginContainerButton.style.opacity = "1";
        });
    },
    
    // Geolocation button handler
    handleGeolocationButtonClick() {
        console.log("Geolocation button pressed!");
        
        if (!('geolocation' in navigator)) {
            console.error("Geolocation is not supported by this browser.");
            showFeedback("La géolocalisation n'est pas disponible sur cet appareil.", "error");
            return;
        }

        const geolocButton = document.getElementById('loginGeolocButton');
        geolocButton.disabled = true;

        navigator.geolocation.getCurrentPosition(
            position => {
                const { latitude, longitude } = position.coords;
                console.log(`[GEO] Got position: lat=${latitude}, lon=${longitude}`);

                // API call to get schools by coordinates
                const apiUrl = `https://api.pronotif.tech/v1/login/get_schools?coords=true&lat=${latitude}&lon=${longitude}`;
                wrapFetch(apiUrl, {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' }
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`Error ${response.status}: ${response.statusText}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log("[GEO] Results:", data);
                    
                    const self = this;
                    self.handleScoolResultsDisplay(data);
                })
                .catch(error => {
                    console.error("[GEO] Failed getting data:", error);
                })
                .finally(() => {
                    geolocButton.disabled = false;

                });
            },
            error => {
                console.error("[GEO] Geolocation error:", error);

                geolocButton.disabled = false;
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    },

    handleScoolResultsDisplay(data) {
        console.log("[SEARCH DISPLAY] Displaying school results");
        
        // Get DOM elements
        const loginHeaderAppTitle = document.getElementById('loginHeaderAppTitle');
        const loginHeaderAppSubTitle = document.getElementById('loginHeaderAppSubTitle');
        const loginCardContainerTitle = document.getElementById('loginCardContainerTitle');
        const loginOptionsContainer = document.getElementById('loginOptionsContainer');
        const globalLoginContainerButton = document.getElementById('globalLoginContainerButton');
        const globalLoginContainerInput = document.getElementById('globalLoginContainerInput');

        // Update header information
        loginHeaderAppTitle.textContent = "Presque fini !";
        loginHeaderAppSubTitle.textContent = "Etape 2 sur 3";
        loginCardContainerTitle.textContent = "Sélectionnez votre établissement";
        
        // Hide the search input and button
        globalLoginContainerButton.style.display = "none";
        globalLoginContainerInput.style.display = "none";
        
        // Clear existing optons
        loginOptionsContainer.innerHTML = "";
        
        const schoolsContainer = document.createElement('div');
        schoolsContainer.className = 'schools-options-container';
        loginOptionsContainer.appendChild(schoolsContainer);
        
        // Show the options container
        loginOptionsContainer.style.display = "block";
        
        const schools = data.schools.schools || [];
        
        if (schools.length === 0) {
            const noResults = document.createElement('div');
            noResults.className = 'no-results-message';
            noResults.textContent = "Aucun établissement trouvé. Essayez une autre ville.";
            schoolsContainer.appendChild(noResults);

            const backButton = document.createElement('button');
            backButton.className = 'back-button';
            backButton.textContent = "Retour à la recherche";
            backButton.onclick = () => this.handleCitySearchButtonClick();
            schoolsContainer.appendChild(backButton);
            return;
        }
        
        //create school option boxes
        schools.forEach(school => {
            const schoolBox = document.createElement('button');
            schoolBox.className = 'login-option-box school-option';
            
            // Create icon element
            const icon = document.createElement('i');
            icon.className = 'fa-solid fa-school';
            schoolBox.appendChild(icon);
            
            // Create text container
            const textContainer = document.createElement('div');
            textContainer.className = 'option-text-container';
            
            // Add school name
            const schoolName = document.createElement('h2');
            schoolName.className = 'options-button-title';
            schoolName.textContent = school.nomEtab;
            textContainer.appendChild(schoolName);
            
            // Add school address if available
            if (school.cp) {
                const schoolAddress = document.createElement('p');
                schoolAddress.className = 'options-button-subtitle';
                schoolAddress.textContent = school.cp;
                textContainer.appendChild(schoolAddress);
            }
            
            schoolBox.appendChild(textContainer);
            
            // Add click handler for school selection
            schoolBox.addEventListener('click', () => {
                console.log(`[SCHOOL] Selected: ${school.nomEtab}`);
                this.handleSchoolSelection(school, school.url, null, null, null, data.schools.region);
                                        //School name, login_page_link, qrcode_login, qrcode_data, pin, region
            });
            
            schoolsContainer.appendChild(schoolBox);
        });
        
        // Add a back button
        const backButtonContainer = document.createElement('div');
        backButtonContainer.className = 'back-button-container';
        
        const backButton = document.createElement('button');
        backButton.className = 'back-button';
        backButton.textContent = "Retour à la recherche";
        backButton.onclick = () => this.handleCitySearchButtonClick();
        
        backButtonContainer.appendChild(backButton);
        loginOptionsContainer.appendChild(backButtonContainer);
    },

    verifyManualPronoteLink(link) {
        // Call backend API to verify the manual Pronote link
        return wrapFetch('https://api.pronotif.tech/v1/login/verifylink', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                manual_pronote_link: String(link),
            }),
            cache: 'no-store'
        })
        .then(response => response.json())
        .then(data => {
            // Return an object with both the validity and region
            if (data.isValid === true) {
                return {
                    isValid: true,
                    region: data.region || "",
                    nomEtab: data.nomEtab || data.nom_etab || ""
                };
            } else if (data.isValid === false) {
                alert("Le lien Pronote fourni n'est pas valide. Veuillez vérifier et réessayer.", "error");
                return { isValid: false };
            } else {
                alert(data.message || "Erreur de connexion.", "error");
                return { isValid: false };
            }
        })
        .catch(() => {
            alert("Erreur réseau.");
            return { isValid: false };
        });
    },

    async handleSchoolSelection(school, login_page_link, qr_code_login, qrcode_data, pin, region) {
        console.log(`[SCHOOL] Processing selection: ${school.nomEtab}`);
        
        // Store the selected school
        this.selectedSchool = school;
        
        // Update header information
        const loginHeaderAppTitle = document.getElementById('loginHeaderAppTitle');
        const loginHeaderAppSubTitle = document.getElementById('loginHeaderAppSubTitle');
        const loginCardContainerTitle = document.getElementById('loginCardContainerTitle');

        const globalLoginContainerInput = document.getElementById('globalLoginContainerInput');
        const globalLoginContainerButton = document.getElementById('globalLoginContainerButton');

        if (globalLoginContainerInput && globalLoginContainerButton) {
            globalLoginContainerInput.style.display = "none";
            globalLoginContainerButton.style.display = "none";
        }
        
        loginHeaderAppTitle.textContent = "Dernière étape !";
        loginHeaderAppSubTitle.textContent = "Etape 3 sur 3";
        loginCardContainerTitle.textContent = "Entrez vos identifiants Pronote";

        const loginOptionsContainer = document.getElementById('loginOptionsContainer');
        if (loginOptionsContainer) {
            loginOptionsContainer.style.display = "none";
        }
        
        const loginUsernameLabel = document.getElementById('loginUsernameLabel');
        const loginUsernameInput = document.getElementById('loginUsernameInput');
        const loginPasswordLabel = document.getElementById('loginPasswordLabel');
        const loginPasswordInput = document.getElementById('loginPasswordInput');
        const loginSubmitButton = document.getElementById('loginSubmitButton');

        if (loginUsernameLabel && loginUsernameInput && loginPasswordLabel && loginPasswordInput && loginSubmitButton) {
            loginUsernameLabel.style.display = "block";
            loginUsernameInput.style.display = "block";
            loginPasswordLabel.style.display = "block";
            loginPasswordInput.style.display = "block";
            loginSubmitButton.style.display = "block";

            //Submit Handler

            loginSubmitButton.onclick = () => {
                loginSubmitButton.disabled = true;
                loginSubmitButton.style.cursor = "not-allowed";
                loginSubmitButton.style.opacity = "0.6";
                loginSubmitButton.textContent = "Connexion en cours...";

                const student_username = loginUsernameInput.value.trim();
                const student_password = loginPasswordInput.value;

                if (!student_username || !student_password) {
                    alert("Veuillez remplir tous les champs.");

                    loginSubmitButton.disabled = false;
                    loginSubmitButton.style.cursor = "pointer";
                    loginSubmitButton.style.opacity = "1";
                    loginSubmitButton.textContent = "Se connexion";

                    return;
                }
                // Call backend API
                wrapFetch('https://api.pronotif.tech/v1/login/auth', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        student_username: String(student_username),
                        student_password: String(student_password),
                        login_page_link: String(login_page_link),
                        qr_code_login: String(qr_code_login),
                        qrcode_data: String(qrcode_data),
                        pin: String(pin),
                        region: String(region)
                    }),
                    credentials: 'include'
                })
                .then(response => response.json())
                .then(data => {
                    // Handle login response
                    if (data.success) {
                        console.log("Login successful!");

                        loginSubmitButton.disabled = false;
                        loginSubmitButton.style.cursor = "pointer";
                        loginSubmitButton.style.opacity = "1";
                        loginSubmitButton.textContent = "Se connexion";

                        try {
                            showDashboard();
                        } catch(err) {
                            console.error("Error while showing dashboard after login:", err);
                            alert("Une erreur est survenue, veuillez réessayer plus tard.", "error");
                        }

                    } else {
                        alert(data.message || "Erreur de connexion.", "error");

                        loginSubmitButton.disabled = false;
                        loginSubmitButton.style.cursor = "pointer";
                        loginSubmitButton.style.opacity = "1";
                        loginSubmitButton.textContent = "Se connecter";
                    }
                })
                .catch(err => {
                    alert("Erreur réseau.");

                    loginSubmitButton.disabled = false;
                    loginSubmitButton.style.cursor = "pointer";
                    loginSubmitButton.style.opacity = "1";
                    loginSubmitButton.textContent = "Se connecter";
                });
            };
        }

    },
    
    // Direct link button handler
    handleDirectLinkButtonClick() {
        console.log("Direct link button pressed!");

        // Get DOM elements
        const loginHeaderAppTitle = document.getElementById('loginHeaderAppTitle');
        const loginHeaderAppSubTitle = document.getElementById('loginHeaderAppSubTitle');
        const loginCardContainerTitle = document.getElementById('loginCardContainerTitle');
        const loginOptionsContainer = document.getElementById('loginOptionsContainer');
        const globalLoginContainerButton = document.getElementById('globalLoginContainerButton');
        const globalLoginContainerInput = document.getElementById('globalLoginContainerInput');

        loginHeaderAppTitle.textContent = "C'est parti !";
        loginHeaderAppSubTitle.textContent = "Etape 1 sur 3";

        loginCardContainerTitle.textContent = "Entrez le lien de connexion Pronote";
        loginOptionsContainer.style.display = "none";

        globalLoginContainerButton.style.display = "block";
        globalLoginContainerInput.style.display = "block";

        globalLoginContainerButton.textContent = "Recherchez";
        globalLoginContainerInput.placeholder = "Entrez votre lien Pronote";
        
        const self = this;
        globalLoginContainerButton.onclick = function() {
            self.handleManualLink();
        };

        

    },
    
    // Initialize all login buttons and other elements
    init() {
        // City search button
        const citySearchButton = document.getElementById('loginSearchCityButton');
        const geolocButton = document.getElementById('loginGeolocButton');
        const qrCodeButton = document.getElementById('loginQRCodeButton');
        
        this.loginHeaderAppTitle = document.getElementById('loginHeaderAppTitle');
        this.loginHeaderAppSubTitle = document.getElementById('loginHeaderAppSubTitle');
        this.loginCardContainerTitle = document.getElementById('loginCardContainerTitle');
        this.loginOptionsContainer = document.getElementById('loginOptionsContainer');
        this.globalLoginContainerButton = document.getElementById('globalLoginContainerButton');
        this.globalLoginContainerInput = document.getElementById('globalLoginContainerInput');
        
        if (citySearchButton) {
            citySearchButton.addEventListener('click', this.handleCitySearchButtonClick.bind(this));
        }

        if (geolocButton) {
            geolocButton.addEventListener('click', this.handleGeolocationButtonClick.bind(this));
        }

        if (qrCodeButton) {
            qrCodeButton.addEventListener('click', this.handleDirectLinkButtonClick.bind(this));
        }
    }
};

// Dashboard initialization
function initializeDashboard() {
    // Check if we're in demo mode
    if (window.appDemoMode) {
        console.log('[Dashboard] Loading in demo mode with mock data');
        
        // Demo mode
        const welcomeElement = document.getElementById('welcomeGreeting');
        const welcomeSubtitle = document.getElementById('welcomeSubtitle');
        if (welcomeElement) {
            welcomeElement.textContent = `${getGreeting()} Demo ! ${getTimeEmoji()}`;
            welcomeSubtitle.textContent = getSubtitle();
        }
        
        // Add demo mode indicator
        const header = document.querySelector('.dashboard-header');
        if (header) {
            const demoIndicator = document.createElement('div');
            demoIndicator.className = 'demo-mode-indicator';
            demoIndicator.textContent = 'Mode Démo';
            demoIndicator.addEventListener('click', () => {
                localStorage.removeItem('demoMode');
                window.location.reload();
            });
            header.appendChild(demoIndicator);
        }
        
        // Load demo data for all sections
        loadDemoData();
        
        return Promise.resolve();
    }

    // Real mode - fetch data from API
    return fetchDashboardData();
}

// Show dashboard
function showDashboard() {
    console.log('[UI] Starting dashboard transition');
    // Hide the spinner when showing dashboard
    const spinner = document.getElementById('spinner');
    if (spinner) spinner.style.display = 'none';

    const loginView = document.getElementById('loginView');
    const loadingView = document.getElementById('loadingView');
    const skeletonView = document.getElementById('skeletonView');
    const dashboardView = document.getElementById('dashboardView');

    // Start fade-out for login or loading views if they are visible
    let initialFadeOutOccurred = false;
    if (loginView && !loginView.classList.contains('hidden')) {
        loginView.classList.add('animating-out', 'fade-out');
        console.log('[UI] Fading out login view');
        initialFadeOutOccurred = true;
    }
    if (loadingView && !loadingView.classList.contains('hidden')) {
        loadingView.classList.add('animating-out', 'fade-out');
        console.log('[UI] Fading out loading view');
        initialFadeOutOccurred = true;
    }

    const initialFadeOutDuration = initialFadeOutOccurred ? 600 : 0;

    setTimeout(() => {
        // Hide all views
        document.querySelectorAll('.view').forEach(view => {
            view.classList.add('hidden');
            view.classList.remove('animating-out', 'fade-out', 'fade-in');
        });
        console.log('[UI] All previous views hidden.');

        // Initialize dashboard content (demo or real)
        initializeDashboard()
            .then(() => {
                return new Promise((resolve) => {
                    setTimeout(resolve, 400); // Small delay to avoid flicker
                });
            })
            .then(() => {
                console.log('[UI] Data ready');
                setTimeout(() => {
                    console.log('[UI] Showing dashboard view.');

                    // Show the dashboard view (which has been prepared by initializeDashboard)
                    if (dashboardView) {
                        dashboardView.classList.remove('hidden');
                        dashboardView.classList.add('fade-in');
                        console.log('[UI] Dashboard view is now visible.');

                        // Check notifications since dashboard is actually visible
                        setTimeout(() => {
                            checkNotifEnabled();
                        }, 200);
                    }
                }, 600);
            })
            .catch(err => {
                console.error('[UI] Dashboard init failed:', err);
                // Handle error
            });
    }, initialFadeOutDuration);
}


function loadDemoData() {
    // Welcome section
    const welcomeElement = document.getElementById('welcomeGreeting');
    const welcomeSubtitle = document.getElementById('welcomeSubtitle');
    if (welcomeElement) {
        welcomeElement.textContent = `${getGreeting()} Demo ! ${getTimeEmoji()}`;
        welcomeSubtitle.textContent = getSubtitle();
    }

    // Next course card
    const nextCourseCard = document.querySelector('.next-course-card');
    if (nextCourseCard) {
        const courseTitle = nextCourseCard.querySelector('.course-title');
        const courseDetails = nextCourseCard.querySelector('.course-details');
        
        if (courseTitle && courseDetails) {
            courseTitle.textContent = "Mathématiques avec M. Dupont";
            courseDetails.textContent = "Salle 201 · Début à 14:00";
        }
    }

    // Current class card (hide in demo)
    const currentClassCard = document.querySelector('.current-class-card');
    if (currentClassCard) {
        currentClassCard.style.display = 'none';
    }

    // Homework section
    const homeworkList = document.querySelector('.homework-list');
    if (homeworkList) {
        homeworkList.innerHTML = `
            <div class="homework-item">
                <div class="homework-content">
                    <h3 class="homework-subject">Mathématiques</h3>
                    <p class="homework-task">Exercices 5 à 12 page 47</p>
                </div>
                <div class="homework-due">Demain 8h</div>
            </div>
            <div class="homework-item">
                <div class="homework-content">
                    <h3 class="homework-subject">Histoire</h3>
                    <p class="homework-task">Apprendre la leçon sur la Révolution française</p>
                </div>
                <div class="homework-due">Vendredi 10h</div>
            </div>
            <div class="homework-item">
                <div class="homework-content">
                    <h3 class="homework-subject">Anglais</h3>
                    <p class="homework-task">Compléter la fiche de vocabulaire</p>
                </div>
                <div class="homework-due">Lundi 9h</div>
            </div>
        `;
    }
}

async function fetchDashboardData() {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout

        // Fetch student info and Pronote data
        const response = await wrapFetch("https://api.pronotif.tech/v1/app/fetch?fields=student_firstname,next_class_name,next_class_room,next_class_teacher,next_class_start,next_class_end,current_class_name,current_class_room,current_class_teacher,current_class_start,current_class_end", {
            method: 'GET',
            headers: { 
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            signal: controller.signal,
            cache: 'no-store'
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            throw new Error(`Fetch failed: ${response.status} ${response.statusText}`);
        }

        const result = await response.json();
        console.log('Dashboard data received:', result);

        if (result.data) {
            updateDashboardWithData(result.data);
        } else {
            console.warn('No data in API response, using fallback');
            loadFallbackData();
        }

        // Check notification permission
        checkNotificationPermissionChange();

    } catch (error) {
        console.error('Dashboard data fetch failed:', error);
        
        // Always load fallback data if fetch fails
        loadFallbackData();
        
        //error indicator
        showDataFetchError();
    }
}

function updateDashboardWithData(data) {
    console.log('Updating dashboard with data:', data);
    
    // Update welcome section
    const welcomeElement = document.getElementById('welcomeGreeting');
    const welcomeSubtitle = document.getElementById('welcomeSubtitle');
    
    if (welcomeElement) {
        if (data.student_firstname) {
            welcomeElement.textContent = `${getGreeting()} ${data.student_firstname} ! ${getTimeEmoji()}`;
        } else {
            welcomeElement.textContent = `${getGreeting()} ! ${getTimeEmoji()}`;
        }
        if (welcomeSubtitle) {
            welcomeSubtitle.textContent = getSubtitle();
        }
    }

    updateNextCourseCard(data);         
    updateCurrentClassCard(data);
    
    console.log('Dashboard update completed');
}

function updateNextCourseCard(data) {
    const nextCourseCard = document.querySelector('.next-course-card');
    
    if (!nextCourseCard) {
        console.warn('Next course card element not found');
        return;
    }
    
    const courseTitle = nextCourseCard.querySelector('.course-title');
    const courseDetails = nextCourseCard.querySelector('.course-details');
    
    // Remove loading state
    nextCourseCard.classList.remove('loading-data');
    
    // Check if we have valid next class data (not null/undefined/empty string)
    if (data.next_class_name && data.next_class_name !== null && data.next_class_name !== '') {
        let titleText = data.next_class_name;
        if (data.next_class_teacher && data.next_class_teacher !== null && data.next_class_teacher !== '') {
            titleText += ` avec ${data.next_class_teacher}`;
        }
        
        let detailsText = '';
        if (data.next_class_room && data.next_class_room !== null && data.next_class_room !== '') {
            detailsText += `Salle ${data.next_class_room}`;
        }
        if (data.next_class_start && data.next_class_start !== null && data.next_class_start !== '') {
            if (detailsText) detailsText += ' · ';
            detailsText += `Début à ${data.next_class_start}`;
        }
        
        if (courseTitle) courseTitle.textContent = titleText;
        if (courseDetails) courseDetails.textContent = detailsText || 'Informations disponibles';
        
        nextCourseCard.style.display = 'block';
    } else {
        // No next class data available
        if (courseTitle) courseTitle.textContent = "Aucun cours à venir";
        if (courseDetails) courseDetails.textContent = "Profitez de votre temps libre";
        nextCourseCard.style.display = 'block';
    }
}

function updateCurrentClassCard(data) {
    const currentClassCard = document.querySelector('.current-class-card');
    
    if (!currentClassCard) {
        console.warn('Current class card element not found');
        return;
    }
    
    // Check if we have valid current class data (not null/undefined/empty string)
    if (data.current_class_name && data.current_class_name !== null && data.current_class_name !== '') {
        const courseTitle = currentClassCard.querySelector('.course-title');
        const courseDetails = currentClassCard.querySelector('.course-details');
        
        let titleText = data.current_class_name;
        if (data.current_class_teacher && data.current_class_teacher !== null && data.current_class_teacher !== '') {
            titleText += ` avec ${data.current_class_teacher}`;
        }
        
        let detailsText = '';
        if (data.current_class_room && data.current_class_room !== null && data.current_class_room !== '') {
            detailsText += `Salle ${data.current_class_room}`;
        }
        if (data.current_class_end && data.current_class_end !== null && data.current_class_end !== '') {
            if (detailsText) detailsText += ' · ';
            detailsText += `Fin à ${data.current_class_end}`;
        }
        
        // Calculate progress if we have time data
        const progressFill = currentClassCard.querySelector('.progress-fill');
        const progressHandle = currentClassCard.querySelector('.progress-handle');
        
        if (data.current_class_start && data.current_class_end && 
            data.current_class_start !== null && data.current_class_end !== null &&
            data.current_class_start !== '' && data.current_class_end !== '') {
            const now = new Date();
            const startTime = parseTimeString(data.current_class_start);
            const endTime = parseTimeString(data.current_class_end);
            
            if (startTime && endTime) {
                const totalDuration = endTime - startTime;
                const elapsed = now.getTime() - startTime.getTime();
                const progress = Math.max(0, Math.min(100, (elapsed / totalDuration) * 100));
                
                if (progressFill) {
                    progressFill.style.width = `${progress}%`;
                }
                if (progressHandle) {
                    progressHandle.style.left = `${progress}%`;
                }
                
                // Add remaining time to details
                const remainingMinutes = Math.max(0, Math.ceil((endTime - now) / (1000 * 60)));
                if (remainingMinutes > 0) {
                    detailsText += ` | ${remainingMinutes} minutes restantes`;
                }
            }
        }
        
        if (courseTitle) courseTitle.textContent = titleText;
        if (courseDetails) courseDetails.textContent = detailsText || 'Cours en cours...';
        
        currentClassCard.style.display = 'block';
        console.log('Current class card shown:', titleText);
    } else {
        // No current class - hide the card
        currentClassCard.style.display = 'none';
        console.log('Current class card hidden - no current class');
    }
}

function parseTimeString(timeStr) {
    if (!timeStr || typeof timeStr !== 'string') return null;
    
    const [hours, minutes] = timeStr.split(':').map(num => parseInt(num, 10));
    if (isNaN(hours) || isNaN(minutes)) return null;
    
    const now = new Date();
    const timeDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hours, minutes);
    return timeDate;
}

function showDataFetchError() {
    console.warn('[Dashboard] Data fetch error - continuing with fallback');
    
    // Optionally add a small retry button or indicator
    const nextCourseCard = document.querySelector('.next-course-card');
    if (nextCourseCard) {
        const refreshButton = document.createElement('button');
        refreshButton.className = 'refresh-data-btn';
        refreshButton.innerHTML = '🔄';
        refreshButton.title = 'Actualiser les données';
        refreshButton.onclick = () => {
            refreshButton.remove();
            fetchDashboardData();
        };
        nextCourseCard.appendChild(refreshButton);
    }
}

//Generic Feedback function TODO: UPDATE THE FEEDBACK SYSTEM AND THE MESSAGE
function showFeedback(message, type) {
    const feedbackEl = document.getElementById('feedbackMessage');
    if (!feedbackEl) return;
    
    feedbackEl.innerHTML = message;
    feedbackEl.className = 'feedback-message';
    feedbackEl.classList.add(type);
    feedbackEl.style.display = 'block';
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
        const response = await wrapFetch('https://api.pronotif.tech/v1/app/revoke-fcm-token', {
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

// Send FCM token to server
async function sendFCMTokenToServer(token) {
    if (token === lastSentToken) {
        console.log('FCM token already sent, skipping duplicate.');
        return;
    }
    lastSentToken = token;
    try {
        const response = await wrapFetch('https://api.pronotif.tech/v1/app/fcm-token', {
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
        
        const currentToken = await getToken(messaging, { 
            VAPID_KEY, 
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

let lastSentToken = localStorage.getItem('fcmToken') || null;

async function checkNotifEnabled() {
    const notifPrompt = document.querySelector(".notification-prompt");
    const allowNotifButton = document.getElementById('allowNotifButton');
    const infoNotifText = document.getElementById('infoNotifText');
    const infoNotifTitle = document.getElementById('infoNotifTitle');
    const laterButton = document.getElementById('laterButton');

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

            // Get the token
            const currentToken = await getToken(messaging, { 
                VAPID_KEY, 
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

    if (Notification.permission === 'default') {
        console.log('Permission is default, checking if we should show popup...');
        const isDashboard = document.getElementById('dashboardView') && 
                            !document.getElementById('dashboardView').classList.contains('hidden');

        console.log('Dashboard visible:', isDashboard);
        console.log('Notification dismissed cookie:', document.cookie.includes("notifDismissed=true"));
        console.log('Notification prompt element exists:', !!notifPrompt);

        if (isDashboard) {
            // Check if the user has already dismissed the notification
            if (document.cookie.includes("notifDismissed=true")) {
                return; // Don't show the prompt again
            }

            // Show the notification prompt
            notifPrompt.classList.add("visible");

            //"Later" button
            laterButton.addEventListener("click", () => {
                document.cookie = "notifDismissed=true; path=/; max-age=31536000"; // 1 year
                notifPrompt.classList.add("fade-out");
                setTimeout(() => notifPrompt.classList.remove("visible"), 300);
            });
        }
    }

    console.log('Notification permission:', Notification.permission);
    return false;
}

if (allowNotifButton) {
    allowNotifButton.addEventListener('click', async () => {
        const notifPrompt = document.querySelector(".notification-prompt");
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
        await Notification.requestPermission();
        console.info("Requesting notification permission...");

        // Wait until Notification.permission is no longer "default"
        function waitForPermissionChange(resolve) {
            if (Notification.permission !== 'default') {
                resolve(Notification.permission);
            } else {
                setTimeout(() => waitForPermissionChange(resolve), 100);
            }
        }
        const finalPermission = await new Promise(waitForPermissionChange);

        if (finalPermission === 'granted') {
            console.log('Notification permission granted!');
            
            allowNotifButton.style.display = 'none';
            laterButton.style.display = 'none';
            infoNotifTitle.textContent = 'Notifications activées ! 🎉';
            infoNotifText.textContent = 'Vous recevrez maintenant des notifications pour vos cours et devoirs.';
            
            const currentPermission = Notification.permission;

            // Update stored permission
            localStorage.setItem('notificationPermission', currentPermission);

            if (isIOS) {
                console.log('iOS detected, showing success message then reloading');
                infoNotifText.textContent = "L'application va redémarrer pour finaliser l'activation des notifications.";
                // Show success message for 5 seconds and reload
                setTimeout(() => {
                    window.location.reload();
                }, 5000);
                return;
            }

            // For non-iOS: show success message then hide modal
            setTimeout(() => {
                notifPrompt.classList.add("fade-out");
                setTimeout(() => notifPrompt.classList.remove("visible"), 300);
            }, 5000);

            // Non iOS devices, follow as planned
            try {
                // Get the Firebase config
                const firebaseConfig = await fetchFirebaseConfig();
                
                // Wait for service worker to be fully registered and active
                const swRegistration = await navigator.serviceWorker.ready;
                
                // Pass Firebase config to service worker
                if (swRegistration.active) {
                    swRegistration.active.postMessage({
                        type: 'FIREBASE_CONFIG',
                        config: firebaseConfig
                    });
                    console.log('[PWA] Firebase config sent to service worker');
                } else {
                    console.warn('[PWA] No active service worker to send config');
                }
                
                // Wait a moment for the service worker to process the config
                await new Promise(resolve => setTimeout(resolve, 500));
                const messaging = getMessaging(app);
                
                // Get the token
                const currentToken = await getToken(messaging, { 
                    VAPID_KEY, 
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
        } else if (finalPermission === "denied") {
            console.log('Notification permission denied');
            localStorage.setItem('notificationPermission', finalPermission);
            document.cookie = "notifDismissed=true; path=/; max-age=31536000"; // 1 year

            allowNotifButton.style.display = 'none';
            laterButton.style.display = 'none';
            infoNotifTitle.textContent = 'Notifications désactivées ! 😢';
            infoNotifText.textContent = 'Pour les activer à nouveau rendez-vous dans les paramètres de votre appareil.';

            setTimeout(() => {
                //Fade out
                notifPrompt.classList.add("fade-out");
                
                // Hide it 
                setTimeout(() => {
                    notifPrompt.classList.remove("visible");
                }, 500);
            }, 5000);
        }
    });
}

async function fetchFirebaseConfig() {
    // Check for cached config
    const cachedConfig = localStorage.getItem('firebaseConfig');
    const cachedTimestamp = localStorage.getItem('firebaseConfigTimestamp');
    const cacheTTL = 3600 * 1000; // 1 hour cache lifetime
    
    if (cachedConfig && cachedTimestamp && 
        (Date.now() - parseInt(cachedTimestamp) < cacheTTL)) {
        console.log('Using cached Firebase config');
        return JSON.parse(cachedConfig);
    }

    const response = await wrapFetch('https://api.pronotif.tech/v1/app/firebase-config', {
        credentials: 'include'
    });
    
    if (!response.ok) throw new Error('Failed to get Firebase config');
    
    const config = await response.json();

    // Cache the result
    localStorage.setItem('firebaseConfig', JSON.stringify(config));
    localStorage.setItem('firebaseConfigTimestamp', Date.now().toString());
    
    return config;
    return response.json();
}


document.addEventListener('DOMContentLoaded', async () => {

    // Store initial notification permission
    if (!localStorage.getItem('notificationPermission')) {
        localStorage.setItem('notificationPermission', Notification.permission);
    }

    // Initialize Firebase
    app = await initializeFirebase();
    
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
        if (e.target.id === 'debugTrigger' || e.target.classList.contains('login-header-app-name')) {
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
            const loginView = document.getElementById('loginView');
            
            // Then transition from loading to login view
            const loadingView = document.getElementById('loadingView');
            
            if (loadingView && !loadingView.classList.contains('hidden')) {
                // Add fade-out to loading view
                loadingView.classList.add('animating-out', 'fade-out');
                
                setTimeout(() => {
                    // Hide loading view
                    loadingView.classList.add('hidden');
                    loadingView.classList.remove('animating-out', 'fade-out');
                    
                    // Show login view with fade-in
                    if (loginView) {
                        loginView.classList.remove('hidden');
                        loginView.classList.add('fade-in');
                        loginView.style.display = 'flex';
                        
                        // Initialize login buttons
                        loginHandler.init();
                        console.log('[Login] Login view displayed and buttons initialized');
                    }
                    resolve();
                }, 600);
            } else {
                // If loading view is already hidden, just show login view
                if (loginView) {
                    loginView.classList.remove('hidden');
                    loginView.classList.add('fade-in');
                    loginView.style.display = 'flex';
                }
                resolve();
            }
        });
    }

    function checkExistingSession(retryCount = 0) {
        // Check if demo mode is enabled
        const isDemoMode = localStorage.getItem('demoMode') === 'true' || 
                        new URLSearchParams(window.location.search).get('demo') === 'true';
        console.log('Demo mode:', isDemoMode);
        
        if (isDemoMode) {
            console.info('[Auth] Demo mode enabled, bypassing login');
            // Set demo mode flag
            window.appDemoMode = true;
            // Store the demo mode preference if it came from URL
            if (new URLSearchParams(window.location.search).get('demo') === 'true') {
                localStorage.setItem('demoMode', 'true');
            }
            // Go directly to dashboard
            setTimeout(() => showDashboard(), 1000);
            return;
        }

        // Explicitly set demo mode to false if not in demo mode
        window.appDemoMode = false;

        if (!navigator.onLine) {
            console.warn('[Auth] Device is offline, showing login view');
            setTimeout(() => showLoginView(), 1000);
            return;
        }
    
        console.info('[Auth] Checking session...');
        wrapFetch('https://api.pronotif.tech/v1/app/auth/refresh', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            signal: AbortSignal.timeout(10000),
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
            
            // 3 retries
            if (retryCount < 3 && error.message.includes('timed out')) {
                console.info(`[Auth] Retrying session check (${retryCount + 1}/3)...`);
                setTimeout(() => checkExistingSession(retryCount + 1), 1000);
            } else {
                setTimeout(() => showLoginView(), 1000);
            }
        });
    }

    // Show only loading view initially
    document.querySelectorAll('.view').forEach(view => {
        view.classList.add('hidden');
    });
    document.getElementById('loadingView').classList.remove('hidden');
    
    // check session
    checkExistingSession();

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
        const cacheBuster = new Date().getTime();
        const swUrl = `sw.js?v=${cacheBuster}`;
        
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
                        // New service worker available
                        console.log('[PWA] New service worker available. Refresh to update.');
                        // add toast message for new update ?
                    }
                });
            });
        }).catch(error => {
            console.error('[PWA] Service worker registration failed:', error);
        });
    }

});