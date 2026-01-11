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
    
        if (message instanceof Error || typeof message === 'object') {
            try {
                const plain = {};
                // include own property names (enumerable + non-enumerable)
                Object.getOwnPropertyNames(message).forEach(key => {
                    try { plain[key] = message[key]; } catch(e) { plain[key] = `<<unreadable:${e.message}>>`; }
                });
                // also include symbol keys if any
                Object.getOwnPropertySymbols(message).forEach(sym => {
                    try { plain[sym.toString()] = message[sym]; } catch(e) { plain[sym.toString()] = `<<unreadable:${e.message}>>`; }
                });
                // Ensure common error fields are present
                if ('message' in message && !plain.message) plain.message = message.message;
                if ('code' in message && !plain.code) plain.code = message.code;
                if ('name' in message && !plain.name) plain.name = message.name;
                if ('stack' in message && !plain.stack) plain.stack = message.stack;

                return JSON.stringify(plain, null, 2);
            } catch (e) {
                // Fallback to string conversion
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
        const APP_VERSION = '0.9';
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

// Toast Notification System
class ToastManager {
    constructor() {
        this.container = null;
        this.toasts = [];
        this.maxToasts = 3;
        this.init();
    }
    
    init() {
        // Create toast container
        if (!document.querySelector('.toast-container')) {
            this.container = document.createElement('div');
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        } else {
            this.container = document.querySelector('.toast-container');
        }
    }
    
    show(options = {}) {
        const {
            title = 'Notification',
            message = '',
            type = 'info', // success, error, warning, info
            duration = 5000,
            persistent = false,
            icon = null
        } = options;
        
        // Remove oldest toast if too many
        if (this.toasts.length >= this.maxToasts) {
            this.hide(this.toasts[0]);
        }
        
        const toast = this.createToast({ title, message, type, duration, persistent, icon });
        this.container.appendChild(toast);
        this.toasts.push(toast);
        
        toast.offsetHeight;
        
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                toast.classList.add('show');
            });
        });
        
        // Auto-hide after duration if not persistent
        if (!persistent && duration > 0) {
            setTimeout(() => {
                this.hide(toast);
            }, duration);
        }
        
        return toast;
    }

    
    createToast({ title, message, type, duration, persistent, icon }) {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const defaultIcons = {
            success: 'fa-solid fa-check',
            error: 'fa-solid fa-exclamation-triangle',
            warning: 'fa-solid fa-exclamation',
            info: 'fa-solid fa-info'
        };
        
        const iconClass = icon || defaultIcons[type] || defaultIcons.info;
        
        toast.innerHTML = `
            <div class="toast-icon">
                <i class="${iconClass}"></i>
            </div>
            <div class="toast-content">
                <div class="toast-title">${title}</div>
                ${message ? `<div class="toast-message">${message}</div>` : ''}
            </div>
            <button class="toast-close" aria-label="Fermer la notification">
                <i class="fa-solid fa-times"></i>
            </button>
        `;
        
        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', () => {
            this.hide(toast);
        });
        
        toast.addEventListener('click', (e) => {
            if (!e.target.closest('.toast-close') && !persistent) {
                this.hide(toast);
            }
        });
        
        return toast;
    }
    
    hide(toast) {
        if (!toast || !toast.parentNode) return;
        
        toast.classList.remove('show');
        toast.classList.add('hide');
        
        //Remove from array
        const index = this.toasts.indexOf(toast);
        if (index > -1) {
            this.toasts.splice(index, 1);
        }
        
        //Remove from DOM after animation completes
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 400);
    }
    
    hideAll() {
        this.toasts.forEach(toast => this.hide(toast));
    }
    
    success(title, message, options = {}) {
        return this.show({ ...options, title, message, type: 'success' });
    }
    
    error(title, message, options = {}) {
        return this.show({ ...options, title, message, type: 'error' });
    }
    
    warning(title, message, options = {}) {
        return this.show({ ...options, title, message, type: 'warning' });
    }
    
    info(title, message, options = {}) {
        return this.show({ ...options, title, message, type: 'info' });
    }
}

// Create global toast manager instance
const toast = new ToastManager();

// Make it globally available
window.toast = toast;

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
        return getI18nValue("dashboard.greetingDay");
    } else if (hour >= 18 && hour < 22) {
        return getI18nValue("dashboard.greetingEvening");
    } else {
        return getI18nValue("dashboard.greetingNight");
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
            "Reposez-vous bien",
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

async function updateSettings(settingsObj) {

    //specific handling for telemtry change
    if ('telemetry_consent' in settingsObj) {
        if (settingsObj.telemetry_consent === true) {
            localStorage.setItem('telemetryConsent', 'true');
            console.log('[Settings] Telemetry enabled by user');

            //diags to be enabled on next app start
            toast.info(getI18nValue("toast.telemetryEnabledTitle"), getI18nValue("toast.telemetryEnabledDesc"));
        } else {

            localStorage.setItem('telemetryConsent', 'false');
            console.log('[Settings] Telemetry disabled by user');

            toast.info(getI18nValue("toast.telemetryDisabledTitle"), getI18nValue("toast.telemetryDisabledDesc"));
        }
        return true;
    }

    //send settings to backend
    try {
        const response = await wrapFetch('https://api.pronotif.tech/v1/app/set-settings', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settingsObj)
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log('Settings updated successfully:', result.updated_settings);
            toast.success(getI18nValue("toast.settingsSavedSuccessTitle"), getI18nValue("toast.settingsSavedSuccessDesc"));
            return true;
        } else {
            const error = await response.json();
            console.error('Settings update failed:', error);
            toast.error(getI18nValue("toast.globalErrorTitle"), error.error || getI18nValue("toast.settingsSavedErrorDesc"));
            return false;
        }
    } catch (error) {
        console.error('Network error during settings update:', error);
        toast.error(getI18nValue("toast.networkErrorTitle"), getI18nValue("toast.networkErrorDesc"));
        return false;
    }
}

async function fetchSettings() {
    //fetch all user settings on page loading
    try {
        console.log('[Settings] Fetching user settings from backend...');
        const response = await wrapFetch('https://api.pronotif.tech/v1/app/fetch?fields=class_reminder,lunch_menu,evening_menu,unfinished_homework_reminder,new_grade_notification,unfinished_homework_reminder_time,get_bag_ready_reminder,get_bag_ready_reminder_time,notification_delay,student_firstname,lang', {
            method: 'GET',
            credentials: 'include',
            cache: 'no-store'
        });
        
        if (!response.ok) {
            console.warn('[Settings] Failed to fetch settings:', response.status);
            return null;
        }
        
        const result = await response.json();
        if (result.data) {
            if (result.data.student_firstname) {
                localStorage.setItem('student_firstname', result.data.student_firstname);
                console.log('[Settings] Updated student_firstname in localStorage');
            }
            console.log('[Settings] Settings loaded !');
            populateSettingsUI(result.data);
            return result.data;
        }
    } catch (error) {
        console.error('[Settings] Error fetching settings:', error);
    }
    return null;
}

function populateSettingsUI(settings) {
    console.log('[Settings] Populating UI with settings');
    
    const settingMappings = {
        'class_reminder': 'settingsNotificationsItem',
        'lunch_menu': 'settingsMenuDuMidiItem',
        'evening_menu': 'settingsMenuDuSoirItem',
        'unfinished_homework_reminder': 'settingsHomeworkNotDoneItem',
        'get_bag_ready_reminder': 'settingsPackBackpackItem',
        'new_grade_notification': 'settingsNewGradeItem',
        'lang': "currentLanguageLabel"
    };
    
    // Update toggle switches
    for (const [settingName, itemId] of Object.entries(settingMappings)) {
        if (settingName in settings) {
            const settingsItem = document.getElementById(itemId);
            if (settingsItem) {
                const toggle = settingsItem.querySelector('.settings-toggle-input');
                if (toggle) {
                    const value = settings[settingName];
                    const isChecked = value === true || value === '1' || value === 'true' || value === 1;
                    toggle.checked = isChecked;
                    console.log(`[Settings] Set ${settingName} toggle to ${isChecked}`);
                }
            }
        }
    }

    //Update telemetry toogle
    const telemetryToggle = document.querySelector('#settingsTelemetryConsentItem .settings-toggle-input');
    if (telemetryToggle) {

        const value = localStorage.getItem('telemetryConsent');

        if (value === "true") {
            telemetryToggle.checked = true;

        } else{
            telemetryToggle.checked = false;
        }
        
        console.log(`[Settings] Set telemetry_consent toggle to ${telemetryToggle.checked}`);
    }

    
    //Update notification delay buttons
    if ('notification_delay' in settings) {
        const delayValue = parseInt(settings.notification_delay);
        const delayButtons = document.querySelectorAll('.settings-time-option');
        delayButtons.forEach(button => {
            const btnTime = parseInt(button.getAttribute('data-time'));
            if (btnTime === delayValue) {
                button.classList.add('selected');
                console.log(`[Settings] Set delay to ${delayValue} minutes`);
            } else {
                button.classList.remove('selected');
            }
        });
    }
    
    // Update time pills
    if ('unfinished_homework_reminder_time' in settings && settings.unfinished_homework_reminder_time) {
        const timeStr = settings.unfinished_homework_reminder_time;
        const item = document.querySelector('#settingsHomeworkNotDoneItem');
        if (item && timeStr) {
            const timePill = item.querySelector('.settings-item-time-pill');
            const timeInput = item.querySelector('.settings-time-input');
            
            if (timePill) {
                const [hours, minutes] = timeStr.split(':');
                timePill.textContent = `${hours}h${minutes}`;
            }
            if (timeInput) {
                timeInput.value = timeStr;
            }
            console.log(`[Settings] Set homework reminder time to ${timeStr}`);
        }
    }
    
    if ('get_bag_ready_reminder_time' in settings && settings.get_bag_ready_reminder_time) {
        const timeStr = settings.get_bag_ready_reminder_time;
        const item = document.querySelector('#settingsPackBackpackItem');
        if (item && timeStr) {
            const timePill = item.querySelector('.settings-item-time-pill');
            const timeInput = item.querySelector('.settings-time-input');
            
            if (timePill) {
                const [hours, minutes] = timeStr.split(':');
                timePill.textContent = `${hours}h${minutes}`;
            }
            if (timeInput) {
                timeInput.value = timeStr;
            }
            console.log(`[Settings] Set backpack reminder time to ${timeStr}`);
        }
    }

    //update language label
    if ('lang' in settings) {
        const languageNames = {
            'fr': 'Français',
            'es': 'Español',
            'en': 'English'
        };
        const currentLanguageLabel = document.getElementById('currentLanguageLabel');
        if (currentLanguageLabel && languageNames[settings.lang]) {
            currentLanguageLabel.textContent = languageNames[settings.lang];
            localStorage.setItem('language', settings.lang);
            console.log(`[Settings] Set language to ${settings.lang}`);
        }
    }
}

async function performLogout() {
    try {
        const confirmed = confirm(getI18nValue("toast.logoutConfirmation"));
        if (!confirmed) {
            console.log('User logout cancelled by user');
            return;
        }

        const response = await wrapFetch('https://api.pronotif.tech/v1/app/logout', {
            method: 'POST',
            credentials: 'include'
        });
        
        if (response.ok) {
            console.log('Logged out successfully');
            
            //Save toast to localStorage 
            localStorage.setItem('postReloadToast', JSON.stringify({
                title: getI18nValue("toast.logoutSuccessTitle"),
                message: getI18nValue("toast.logoutSuccessDesc"),
                type: 'success'
            }));
            
            localStorage.clear();
            sessionStorage.clear();
            
            //Re-save after clearing
            localStorage.setItem('postReloadToast', JSON.stringify({
                title: getI18nValue("toast.logoutSuccessTitle"),
                message: getI18nValue("toast.logoutSuccessDesc"),
                type: 'success'
            }));
            
            if ('serviceWorker' in navigator) {
                const registrations = await navigator.serviceWorker.getRegistrations();
                for (const reg of registrations) {
                    await reg.unregister();
                }
            }
            if ('caches' in window) {
                const cacheNames = await caches.keys();
                for (const name of cacheNames) {
                    await caches.delete(name);
                }
            }

            await ScheduleDB.clear(); //Clear the db
            
            //invisible overlay to prevent user interactions
            const overlay = document.createElement('div');
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: transparent;
                z-index: 9999;
                pointer-events: auto;
            `;
            document.body.appendChild(overlay);
            
            window.location.reload();
        } else {
            console.error('Logout failed:', response.statusText);
            toast.error(getI18nValue("toast.logoutFailedTitle"), getI18nValue("toast.logoutFailedDesc"));
        }
    } catch (error) {
        console.error('Network error during logout:', error);
        toast.error(getI18nValue("toast.networkErrorTitle"), getI18nValue("toast.networkErrorDesc"));
    }
}

async function performDeleteAccount() {
    try {
        const confirmed = confirm(getI18nValue("toast.deleteAccountConfirmation"));
        if (!confirmed) {
            console.log('Account deletion cancelled by user');
            return;
        }

        const response = await wrapFetch('https://api.pronotif.tech/v1/app/delete-account', {
            method: 'POST',
            credentials: 'include'
        });
        
        if (response.ok) {
            console.log('Account deleted successfully');
            
            localStorage.setItem('postReloadToast', JSON.stringify({
                title: getI18nValue("toast.deleteAccountSuccessTitle"),
                message: getI18nValue("toast.deleteAccountSuccessDesc"),
                type: 'success'
            }));
            
            localStorage.clear();
            sessionStorage.clear();
            
            localStorage.setItem('postReloadToast', JSON.stringify({
                title: getI18nValue("toast.deleteAccountSuccessTitle"),
                message: getI18nValue("toast.deleteAccountSuccessDesc"),
                type: 'success'
            }));
            
            if ('serviceWorker' in navigator) {
                const registrations = await navigator.serviceWorker.getRegistrations();
                for (const reg of registrations) {
                    await reg.unregister();
                }
            }
            if ('caches' in window) {
                const cacheNames = await caches.keys();
                for (const name of cacheNames) {
                    await caches.delete(name);
                }
            }
            
            const overlay = document.createElement('div');
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: transparent;
                z-index: 9999;
                pointer-events: auto;
            `;
            document.body.appendChild(overlay);
            
            setTimeout(() => window.location.reload(), 2000);
        } else {
            console.error('Account deletion failed:', response.statusText);
            toast.error(getI18nValue("toast.accountRemovalErrorTitle"), getI18nValue("toast.accountRemovalErrorDesc"));
        }
    } catch (error) {
        console.error('Network error during account deletion:', error);
        toast.error(getI18nValue("toast.networkErrorTitle"), getI18nValue("toast.networkErrorDesc"));
    }
}

async function upateDynamicBanner() {
    const bannerText = document.getElementById('bannerText');
    const bannerIcon = document.getElementById('bannerIcon');
    const bannerInfoBtn = document.getElementById('bannerInfoBtn');

    try {
        const response = await wrapFetch("https://api.pronotif.tech/v1/app/dynamic-banner", {
            method: 'GET',
            cache: 'no-store'
        });

        if (!response.ok) {
            throw new Error(`Error ${response.status}`);
        }
        console.log("[BANNER] Fetched dynamic banner data");

        const result = await response.json();
        if (result && result.data.message) {
            console.log("[BANNER] Updating banner message:", result.data.message);

            bannerText.textContent = result.data.message;
            bannerText.style.display = "block";

            // Update icon if provided
            if (result.data.icon) {
                bannerIcon.innerHTML = `<i class="${result.data.icon}"></i>`;
            } else {
                bannerIcon.innerHTML = `<i class="fa-solid fa-info"></i>`;
            }

            // Update button link if provided
            if (result.data.link) {
                bannerInfoBtn.onclick = () => {
                    window.open(result.data.link, '_blank', 'noopener');
                };
            } else {
                bannerInfoBtn.onclick = null;
            }

        } else {
            bannerText.style.display = "none";
        }
    } catch (error) {
        if (bannerText) {
            bannerText.style.display = "none";
        }
        console.error("Failed to update dynamic banner:", error);
    }
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

        loginHeaderAppTitle.textContent = getI18nValue("login.letsgoLabel");

        const stepsTemplate = getI18nValue("login.steps");
        loginHeaderAppSubTitle.textContent = stepsTemplate && stepsTemplate.includes('{current_step}')
            ? stepsTemplate.replace('{current_step}', '1')
            : stepsTemplate || "Etape 1 sur 3";

        loginCardContainerTitle.textContent = getI18nValue("login.searchCityTitle");
        loginOptionsContainer.style.display = "none";

        globalLoginContainerButton.style.display = "block";
        globalLoginContainerInput.style.display = "block";

        globalLoginContainerButton.textContent = getI18nValue("login.globalSearchButtonLabel");
        globalLoginContainerInput.placeholder = getI18nValue("login.globalSearchInputPlaceholder");
        
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
            toast.warning(getI18nValue("toast.missingLinkTitle"), getI18nValue("toast.missingLinkDesc"));
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
            globalLoginContainerButton.textContent = getI18nValue("login.globalSearchButtonLabel");
        });

    },
    
    handleCitySearch() {
        console.log("[SEARCH DEBUG] Search button clicked");
        
        const globalLoginContainerInput = document.getElementById('globalLoginContainerInput');
        const globalLoginContainerButton = document.getElementById('globalLoginContainerButton');
        
        const cityName = globalLoginContainerInput.value.trim();
        
        if (!cityName) {
            console.error("[SEARCH] Error: Empty city name");
            toast.warning(getI18nValue("toast.emptyCityNameTitle"), getI18nValue("toast.emptyCityNameDesc"));
            return;
        }
        
        // Show loading state
        globalLoginContainerButton.disabled = true;
        globalLoginContainerButton.style.cursor = "not-allowed";
        globalLoginContainerButton.style.opacity = "0.6";
        globalLoginContainerButton.textContent = getI18nValue("login.processingSearchButtonLabel");
        
        // Prepare API query parameters
        const apiUrl = `https://api.pronotif.tech/v1/login/get_schools?coords=false&city_name=${encodeURIComponent(cityName)}`;
        
        console.log(`[SEARCH] Searching for city: "${cityName}" with URL: ${apiUrl}`);
        
        wrapFetch(apiUrl, {
            method: 'GET',
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
            globalLoginContainerButton.textContent = getI18nValue("login.globalSearchButtonLabel");

            globalLoginContainerButton.style.cursor = "pointer";
            globalLoginContainerButton.style.opacity = "1";
            
            console.log("[SEARCH] Results:", data);

            const self = this;
            self.handleScoolResultsDisplay(data);
        })
        .catch(error => {
            console.error("[SEARCH] Search failed:", error);
            toast.error(getI18nValue("toast.searchFailedTitle"), getI18nValue("toast.generalErrorDesc"));
        })
        .finally(() => {
            
            // Reset button state
            globalLoginContainerButton.disabled = false;
            globalLoginContainerButton.textContent = getI18nValue("login.globalSearchButtonLabel");

            globalLoginContainerButton.style.cursor = "pointer";
            globalLoginContainerButton.style.opacity = "1";
        });
    },
    
    // Geolocation button handler
    handleGeolocationButtonClick() {
        console.log("Geolocation button pressed!");

        const citySearchButton = document.getElementById('loginSearchCityButton');
        const geolocButton = document.getElementById('loginGeolocButton');
        const directLinkButton = document.getElementById('loginLinkButton');

        const geolocButtonSubtitle = document.getElementById('geolocButtonSubtitle');
        const geolocButtonTitle = document.getElementById('geolocButtonTitle');
        

        const modal = document.getElementById('geolocRationaleModal');
        const proceedBtn = document.getElementById('geolocProceedBtn');
        const cancelBtn = document.getElementById('geolocCancelBtn');

        if (!modal || !proceedBtn || !cancelBtn) {
            console.warn('[GEO] Rationale modal missing, proceeding without it.');
            return startGeolocation.call(this);
        }

        modal.classList.add('show');
        modal.setAttribute('aria-hidden', 'false');

        const closeModal = () => {
            modal.classList.remove('show');
            modal.setAttribute('aria-hidden', 'true');
        };

        if (!modal.dataset.bound) {
            //click outside to cancel
            modal.addEventListener('click', (e) => {
                if (e.target === modal) closeModal();
            });
            modal.dataset.bound = 'true';
        }

        cancelBtn.onclick = () => {
            closeModal();
            console.log('[GEO] User cancelled geolocation rationale.');
        };

        proceedBtn.onclick = () => {
            closeModal();
            startGeolocation.call(this);
        };

        function startGeolocation() {
            //disable primary options
            geolocButton.disabled = true;
            citySearchButton.disabled = true;
            directLinkButton.disabled = true;

            geolocButton.style.cursor = "not-allowed";
            citySearchButton.style.cursor = "not-allowed";
            directLinkButton.style.cursor = "not-allowed";

            citySearchButton.style.opacity = "0.6";
            directLinkButton.style.opacity = "0.6";

            console.log("[GEO] Requesting geolocation...");

            if (!('geolocation' in navigator)) {
                console.error("Geolocation is not supported by this browser.");
                toast.error(getI18nValue("toast.globalErrorTitle"), getI18nValue("toast.geolocUnavailableDesc"));
                resetButtons();
                return;
            }

            geolocButtonTitle.textContent = getI18nValue("login.processingSearchButtonLabel");
            geolocButtonSubtitle.textContent = getI18nValue("dashboard.pleaseWait");
            
            navigator.geolocation.getCurrentPosition(
                position => {
                    const { latitude, longitude } = position.coords;
                    console.log(`[GEO] Got position: lat=${latitude}, lon=${longitude}`);

                // API call to get schools by coordinates
                    const apiUrl = `https://api.pronotif.tech/v1/login/get_schools?coords=true&lat=${latitude}&lon=${longitude}`;
                wrapFetch(apiUrl, {
                    method: 'GET',
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
                    .finally(resetButtons);
                },
                error => {
                    console.error("[GEO] Geolocation error:", error);

                    if (error.message === "User denied Geolocation") {
                        toast.warning(getI18nValue("toast.geolocRequestRefusedTitle"), getI18nValue("toast.geolocRequestRefusedDesc"));
                    } else {
                        toast.error(getI18nValue("toast.geolocRequestErrorTitle"), getI18nValue("toast.geolocRequestErrorDesc"));
                    }

                    resetButtons();
                },
                { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
            );

            function resetButtons() {
                geolocButton.disabled = false;
                citySearchButton.disabled = false;
                directLinkButton.disabled = false;

                geolocButton.style.cursor = "pointer";
                citySearchButton.style.cursor = "pointer";
                directLinkButton.style.cursor = "pointer";

                citySearchButton.style.opacity = "1";
                directLinkButton.style.opacity = "1";

                geolocButtonTitle.textContent = getI18nValue("login.geolocationTitle");
                geolocButtonSubtitle.textContent = getI18nValue("login.geolocationDesc");
            }
        }
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
        loginHeaderAppTitle.textContent = getI18nValue("login.almostDoneLabel");
        
        const stepsTemplate = getI18nValue("login.steps");
        loginHeaderAppSubTitle.textContent = stepsTemplate && stepsTemplate.includes('{current_step}')
            ? stepsTemplate.replace('{current_step}', '2')
            : stepsTemplate || "Etape 2 sur 3";

        loginCardContainerTitle.textContent = getI18nValue("login.selectSchoolLabel");
        
        // Hide the search input and button
        globalLoginContainerButton.style.display = "none";
        globalLoginContainerInput.style.display = "none";
        
        // Clear existing optons
        loginOptionsContainer.innerHTML = "";
        
        const schoolsContainer = document.createElement('div');
        schoolsContainer.className = 'schools-options-container sentry-mask';
        loginOptionsContainer.appendChild(schoolsContainer);
        
        // Show the options container
        loginOptionsContainer.style.display = "block";
        
        const schools = data.schools.schools || [];
        
        if (schools.length === 0 && data.schools.is_international === true) {
            const noResults = document.createElement('div');
            noResults.className = 'no-results-message';
            noResults.innerHTML = `${getI18nValue("login.cityNotInFranceMessage")}<br><br>${getI18nValue("login.useManualLinkMessage")}`;
            schoolsContainer.appendChild(noResults);

            const backButton = document.createElement('button');
            backButton.className = 'back-button';
            backButton.textContent = getI18nValue("login.useManualLinkActionMessage");
            backButton.onclick = () => this.handleDirectLinkButtonClick();
            schoolsContainer.appendChild(backButton);
            return;

        } else if (schools.length === 0) {
            const noResults = document.createElement('div');
            noResults.className = 'no-results-message';
            noResults.innerHTML = `${getI18nValue("login.noSchoolsFoundMessage")}<br><br>${getI18nValue("login.tryAnotherCityMessage")}`;
            schoolsContainer.appendChild(noResults);

            const backButton = document.createElement('button');
            backButton.className = 'back-button';
            backButton.textContent = getI18nValue("login.backToSearchButtonLabel");
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
        backButton.textContent = getI18nValue("login.backToSearchButtonLabel");
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
                toast.warning(getI18nValue("toast.malformedPronoteLinkTitle"), getI18nValue("toast.malformedPronoteLinkDesc"));
                return { isValid: false };
            } else {
                toast.error(data.message || getI18nValue("toast.networkErrorTitle"), getI18nValue("toast.networkErrorDesc"));
                return { isValid: false };
            }
        })
        .catch(() => {
            toast.error(getI18nValue("toast.networkErrorTitle"), getI18nValue("toast.networkErrorDesc"));
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
        
        loginHeaderAppTitle.textContent = getI18nValue("login.lastStepLabel");

        const stepsTemplate = getI18nValue("login.steps");
        loginHeaderAppSubTitle.textContent = stepsTemplate && stepsTemplate.includes('{current_step}')
            ? stepsTemplate.replace('{current_step}', '3')
            : stepsTemplate || "Etape 3 sur 3";

        loginCardContainerTitle.textContent = getI18nValue("login.enterCredentialsLabel");

        const loginOptionsContainer = document.getElementById('loginOptionsContainer');
        if (loginOptionsContainer) {
            loginOptionsContainer.style.display = "none";
        }
        
        const loginUsernameLabel = document.getElementById('loginUsernameLabel');
        const loginUsernameInput = document.getElementById('loginUsernameInput');
        const loginPasswordLabel = document.getElementById('loginPasswordLabel');
        const loginPasswordInput = document.getElementById('loginPasswordInput');
        const loginSubmitButton = document.getElementById('loginSubmitButton');
        const passwordWrapper = document.querySelector('.password-input-wrapper');
        const togglePasswordBtn = document.getElementById('togglePassword');

        if (loginUsernameLabel && loginUsernameInput && loginPasswordLabel && loginPasswordInput && loginSubmitButton) {
            loginUsernameLabel.style.display = "block";
            loginUsernameInput.style.display = "block";
            loginPasswordLabel.style.display = "block";
            loginPasswordInput.style.display = "block";
            loginSubmitButton.style.display = "block";

            if (passwordWrapper) passwordWrapper.style.display = "block";
            if (togglePasswordBtn) togglePasswordBtn.style.display = "inline-flex";

            if (togglePasswordBtn) {
                togglePasswordBtn.style.display = "flex";
            }

            //Submit Handler

            loginSubmitButton.onclick = () => {
                loginSubmitButton.disabled = true;
                loginSubmitButton.style.cursor = "not-allowed";
                loginSubmitButton.style.opacity = "0.6";
                loginSubmitButton.textContent = getI18nValue("login.processingLoginLabel");

                const student_username = loginUsernameInput.value.trim();
                const student_password = loginPasswordInput.value;

                if (!student_username || !student_password) {
                    toast.warning(getI18nValue("toast.fillAllEntriesErrorTitle"), getI18nValue("toast.fillAllEntriesErrorDesc"));

                    loginSubmitButton.disabled = false;
                    loginSubmitButton.style.cursor = "pointer";
                    loginSubmitButton.style.opacity = "1";
                    loginSubmitButton.textContent = getI18nValue("login.loginButtonLabel");
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
                .then(async response => {
                    const data = await response.json().catch(() => ({}));

                    if (response.status === 401) {
                        toast.warning(getI18nValue("toast.wrongCredentialsTitle"), getI18nValue("toast.wrongCredentialsDesc"));
                        console.error("Wrong credentials provided.");

                        loginSubmitButton.disabled = false;
                        loginSubmitButton.style.cursor = "pointer";
                        loginSubmitButton.style.opacity = "1";
                        loginSubmitButton.textContent = getI18nValue("login.loginButtonLabel");

                    } else if (data.success) {
                        console.log("Login successful!");

                        loginSubmitButton.disabled = false;
                        loginSubmitButton.style.cursor = "pointer";
                        loginSubmitButton.style.opacity = "1";
                        loginSubmitButton.textContent = getI18nValue("login.loginButtonLabel");

                        try {
                            showDashboard();
                        } catch(err) {
                            console.error("Error while showing dashboard after login:", err);
                            toast.error(getI18nValue("toast.generalErrorTitle"), getI18nValue("toast.generalErrorDesc"));
                        }

                    } else {
                        toast.error(data.message || getI18nValue("toast.networkErrorTitle"), getI18nValue("toast.networkErrorDesc"));

                        loginSubmitButton.disabled = false;
                        loginSubmitButton.style.cursor = "pointer";
                        loginSubmitButton.style.opacity = "1";
                        loginSubmitButton.textContent = getI18nValue("login.loginButtonLabel");
                    }
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

        globalLoginContainerInput.value = "";

        loginHeaderAppTitle.textContent = getI18nValue("login.letsgoLabel");

        const stepsTemplate = getI18nValue("login.steps");
        loginHeaderAppSubTitle.textContent = stepsTemplate && stepsTemplate.includes('{current_step}')
            ? stepsTemplate.replace('{current_step}', '1')
            : stepsTemplate || "Etape 1 sur 3";

        loginCardContainerTitle.textContent = getI18nValue("login.enterLinkLabel");
        loginOptionsContainer.style.display = "none";

        globalLoginContainerButton.style.display = "block";
        globalLoginContainerInput.style.display = "block";

        globalLoginContainerButton.textContent = getI18nValue("login.globalSearchButtonLabel");
        globalLoginContainerInput.placeholder = getI18nValue("login.enterLinkLabel");
        
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
        const directLinkButton = document.getElementById('loginLinkButton');
        
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

        if (directLinkButton) {
            directLinkButton.addEventListener('click', this.handleDirectLinkButtonClick.bind(this));
        }
    }
};

function updateScheduleHeader(date) {
    const scheduleDateElement = document.querySelector('.schedule-date');
    const scheduleRelativeDateElement = document.querySelector('.schedule-relative-date');
    
    if (!scheduleDateElement || !scheduleRelativeDateElement) return;

    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    const targetDate = new Date(date);
    targetDate.setHours(0, 0, 0, 0);
    
    const diffTime = targetDate - today;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    //Format date : DD Month
    const day = targetDate.getDate().toString().padStart(2, '0');
    const month = targetDate.toLocaleString(getI18nValue("langCode"), { month: 'long' });
    const formattedDate = `${day} ${month.charAt(0).toUpperCase() + month.slice(1)}`;
    
    let relativeText = '';
    if (diffDays === 0) {
        relativeText = getI18nValue("days.today");
    } else if (diffDays === 1) {
        relativeText = getI18nValue("days.tomorrow");
    } else if (diffDays === -1) {
        relativeText = getI18nValue("days.yesterday");
    }

    if (relativeText) {
        scheduleRelativeDateElement.textContent = relativeText;
        scheduleDateElement.textContent = formattedDate;
        scheduleRelativeDateElement.style.display = 'block';
        scheduleDateElement.classList.remove('large-date');
    } else {
        scheduleRelativeDateElement.textContent = formattedDate;
        scheduleRelativeDateElement.style.display = 'block';
        
        if (diffDays > 0) {
            scheduleDateElement.textContent = getI18nValue('schedule.inXDays').replace('{count}', diffDays);
        } else {
            scheduleDateElement.textContent = getI18nValue('schedule.xDaysAgo').replace('{count}', Math.abs(diffDays));
        }
        scheduleDateElement.classList.remove('large-date');
    }
}

let dateSelectorListenerAttached = false;
let isUpdatingDateSelector = false;

function createDateItem(date) {
    const dateItem = document.createElement('div');
    dateItem.className = 'date-item';
    
    const dayName = date.toLocaleDateString((getI18nValue("langCode")), { weekday: 'short' }).replace('.', '').toUpperCase();
    const dayNumber = date.getDate().toString().padStart(2, '0');
    
    dateItem.innerHTML = `
        <span class="date-day">${dayName}</span>
        <span class="date-number">${dayNumber}</span>
        <div class="date-indicator"></div>
    `;
    
    dateItem.dataset.date = date.toISOString();
    
    dateItem.addEventListener('click', function() {
        const clickedDate = new Date(this.dataset.date);
        updateScheduleView(clickedDate);
    });
    
    return dateItem;
}

function handleDateSelectorScroll() {
    if (isUpdatingDateSelector) return;
    
    const selector = document.querySelector('.schedule-date-selector');
    if (!selector) return;

    const scrollLeft = selector.scrollLeft;
    const scrollWidth = selector.scrollWidth;
    const clientWidth = selector.clientWidth;
    const threshold = 100; //px

    //Prepend if near start
    if (scrollLeft < threshold) {
        isUpdatingDateSelector = true;
        const firstItem = selector.firstElementChild;
        if (firstItem) {
            const firstDate = new Date(firstItem.dataset.date);
            const daysToPrepend = 7;
            const oldScrollWidth = selector.scrollWidth;
            
            for (let i = 1; i <= daysToPrepend; i++) { //prepend days
                const newDate = new Date(firstDate);
                newDate.setDate(firstDate.getDate() - i);
                const newItem = createDateItem(newDate);
                selector.insertBefore(newItem, selector.firstElementChild);
            }
            
            //Adjust scroll position
            const newScrollWidth = selector.scrollWidth;
            selector.scrollLeft += (newScrollWidth - oldScrollWidth);
        }
        setTimeout(() => { isUpdatingDateSelector = false; }, 50);
    } 
    //Append if near end
    else if (scrollWidth - (scrollLeft + clientWidth) < threshold) { //if near end and scrolling right
        isUpdatingDateSelector = true;
        const lastItem = selector.lastElementChild;
        if (lastItem) {
            const lastDate = new Date(lastItem.dataset.date);
            const daysToAppend = 7;
            
            for (let i = 1; i <= daysToAppend; i++) {
                const newDate = new Date(lastDate);
                newDate.setDate(lastDate.getDate() + i);
                const newItem = createDateItem(newDate);
                selector.appendChild(newItem);
            }
        }
        setTimeout(() => { isUpdatingDateSelector = false; }, 50); //small delay to prevent rapid re-triggering
    }
}

function generateDateSelector(selectedDate) {
    const selector = document.querySelector('.schedule-date-selector');
    if (!selector) return;
    
    if (!dateSelectorListenerAttached) {
        selector.addEventListener('scroll', handleDateSelectorScroll);
        dateSelectorListenerAttached = true;
    }
    
    const targetDate = new Date(selectedDate);
    targetDate.setHours(0, 0, 0, 0);

    //Check if the date is already in the list
    let dateExists = false;
    if (selector.children.length > 0) { //if in the list no need to regenerate
        const items = selector.querySelectorAll('.date-item');
        items.forEach(item => {
            const itemDate = new Date(item.dataset.date);
            itemDate.setHours(0, 0, 0, 0);
            if (itemDate.getTime() === targetDate.getTime()) {
                dateExists = true;
            }
        });
    }
    
    //If date exists just update selection
    if (dateExists) {
        updateDateSelectorSelection(selectedDate);
        return;
    }
    
    selector.innerHTML = '';
    
    //Generate dates for a range: -14 days to +31 days around the date
    const startDate = new Date(targetDate);
    startDate.setDate(targetDate.getDate() - 14);
    
    const endDate = new Date(targetDate);
    endDate.setDate(targetDate.getDate() + 31);
    
    let currentDate = new Date(startDate);
    
    while (currentDate <= endDate) {
        const dateItem = createDateItem(currentDate);
        selector.appendChild(dateItem);
        currentDate.setDate(currentDate.getDate() + 1);
    }
    
    updateDateSelectorSelection(selectedDate);
}

function updateDateSelectorSelection(date) { // Scroll to selected date
    const selector = document.querySelector('.schedule-date-selector');
    if (!selector) return;
    
    const items = selector.querySelectorAll('.date-item');
    const targetDate = new Date(date);
    targetDate.setHours(0,0,0,0);
    
    items.forEach(item => {
        const itemDate = new Date(item.dataset.date);
        itemDate.setHours(0,0,0,0);
        
        if (itemDate.getTime() === targetDate.getTime()) {
            item.classList.add('selected');
            setTimeout(() => {
                isUpdatingDateSelector = true;
                
                const itemRect = item.getBoundingClientRect();
                const selectorRect = selector.getBoundingClientRect();
                const currentScroll = selector.scrollLeft;
                
                //Calculate position relative to content start
                const itemOffset = itemRect.left - selectorRect.left + currentScroll;
                
                //Target: item at 15% of container width
                const targetScroll = itemOffset - (selector.clientWidth * 0.15);
                
                selector.scrollTo({ left: targetScroll, behavior: 'smooth' });
                
                setTimeout(() => { isUpdatingDateSelector = false; }, 500);
            }, 100);
        } else {
            item.classList.remove('selected');
        }
    });
}


//Schedule caching
const scheduleCache = {}; //Memory Cache

const ScheduleDB = {
    db: null,
    async executeTransaction(mode, callback) {

        if (!this.db) {
            this.db = await new Promise((resolve, reject) => {

                const request = indexedDB.open('PronotifScheduleDB', 1);
                request.onerror = () => reject(request.error);
                request.onsuccess = () => resolve(request.result);
                request.onupgradeneeded = (event) => {
                    event.target.result.createObjectStore('lessons', { keyPath: 'date' });
                };
            });
        }
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction('lessons', mode);
            const store = transaction.objectStore('lessons');
            const request = callback(store);
            
            if (!request) {
                resolve();
                return;
            }
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    },
    
    get(date) { 
        return this.executeTransaction('readonly', store => store.get(date))
            .then(result => result?.data)
            .catch(error => console.error('[ScheduleDB] Get error:', error)); 
    },
    
    save(date, data) { 
        return this.executeTransaction('readwrite', store => store.put({ date, data }))
            .catch(error => console.error('[ScheduleDB] Save error:', error)); 
    },
    
    saveMany(items) {
        if (!items || Object.keys(items).length === 0) return Promise.resolve();
        
        return this.executeTransaction('readwrite', store => {
            let lastRequest;
            for (const [date, data] of Object.entries(items)) {
                lastRequest = store.put({ date, data });
            }
            return lastRequest;
        }).catch(error => console.error('[ScheduleDB] SaveMany error:', error));
    },
    
    clear() { 
        return this.executeTransaction('readwrite', store => store.clear())
            .catch(error => console.error('[ScheduleDB] Clear error:', error)); 
    }
};

async function fetchSchedule(date) {
    const scheduleContainer = document.querySelector('.schedule-list');
    if (!scheduleContainer) return;

    const formatDate = (d) => {
        //If d is a string in YYYY-MM-DD format return it directly to avoid timezone issues
        if (typeof d === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(d)) {
            return d;
        }
        
        const dateObj = new Date(d);
        const year = dateObj.getFullYear();
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        const day = String(dateObj.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    };

    const targetDateStr = formatDate(date);

    //first check memory cache
    if (scheduleCache[targetDateStr]) {
        console.log(`[Schedule] Using memory cache for ${targetDateStr}`);
        renderSchedule(scheduleCache[targetDateStr]);
        return;
    }
    //then check IndexedDB
    const dbCache = await ScheduleDB.get(targetDateStr);
    if (dbCache) {
        console.log(`[Schedule] Using IDB cache for ${targetDateStr}`);
        scheduleCache[targetDateStr] = dbCache; //populate L1
        renderSchedule(dbCache);
        return;
    }

    //Show loading state
    scheduleContainer.innerHTML = '<div class="schedule-loading"><i class="fas fa-spinner fa-spin fa-2x"></i></div>';

    try {
        //fetch window of 14days before and after (28)
        const target = new Date(date);
        const start = new Date(target);
        start.setDate(target.getDate() - 14);
        
        const end = new Date(target);
        end.setDate(target.getDate() + 14);
        
        const startStr = formatDate(start);
        const endStr = formatDate(end);

        console.log(`[Schedule] Fetching from ${startStr} to ${endStr} for target ${targetDateStr}`);

        const response = await wrapFetch(`https://api.pronotif.tech/v1/app/fetch?fields=lessons&start=${startStr}&end=${endStr}`, {
                method: 'GET',
                credentials: 'include',
                cache: 'no-store'
            });
        
        const data = await response.json();
        
        if (data.data && data.data.lessons) {
            //initialize cache for the range
            let curr = new Date(startStr);
            const endDateObj = new Date(endStr);
            
            const lessonsMap = {};
            
            while (curr <= endDateObj) {
                const dStr = formatDate(curr);
                lessonsMap[dStr] = []; //default to empty
                curr.setDate(curr.getDate() + 1);
            }

            data.data.lessons.forEach(lesson => { //populate map with actual lessons
                if (lessonsMap[lesson.date]) {
                    lessonsMap[lesson.date].push(lesson);
                }
            });

            //save to both Cache and IDB 
            Object.assign(scheduleCache, lessonsMap); 
            ScheduleDB.saveMany(lessonsMap); 

            // Render for target date
            const dayLessons = scheduleCache[targetDateStr] || [];
            renderSchedule(dayLessons);
        } else {
            scheduleContainer.innerHTML = '';
            toast.error(getI18nValue("toast.globalErrorTitle"), getI18nValue("toast.failedToGetScheduleDesc"));
        }
    } catch (error) {
        console.error('Error fetching schedule:', error);
        scheduleContainer.innerHTML = '';
        toast.error(getI18nValue("toast.globalErrorTitle"), getI18nValue("toast.errorFetchingScheduleDesc"));
    }
}

function renderSchedule(lessons) {
    const container = document.querySelector('.schedule-list');
    if (!container) return;
    
    //build HTML instead of DOM manipulation for performance
    let html = '';

    if (!lessons || lessons.length === 0) {
        container.innerHTML = `
            <div class="no-results-message" style="margin-top: 2rem;">
                <i class="fas fa-calendar-day" style="font-size: 3rem; margin-bottom: 1rem; color: var(--primary);"></i>
                <p>${getI18nValue("schedule.noClassFoundForDate")}</p>
            </div>
        `;
        return;
    }

    //Sort lessons by start time
    lessons.sort((a, b) => a.start.localeCompare(b.start));

    let lastEndTime = null;

    //helper to parse time strings (HH:MM) to minutes
    const parseTime = (timeStr) => {
        const [h, m] = timeStr.split(':').map(Number);
        return h * 60 + m;
    };

    lessons.forEach(lesson => {
        //Check for gap
        if (lastEndTime) {
            const gapStartMins = parseTime(lastEndTime);
            const currentStartMins = parseTime(lesson.start);
            const gapMinutes = currentStartMins - gapStartMins;

            if (gapMinutes >= 15) { //Only show gaps of more than 15mins
                let durationText = `${gapMinutes} min`;
                if (gapMinutes > 59) {
                    const h = Math.floor(gapMinutes / 60);
                    const m = gapMinutes % 60;
                    durationText = `${h}h${m > 0 ? m.toString().padStart(2, '0') : ''}`;
                }

                html += `
                    <div class="schedule-card empty-slot">
                        <div class="schedule-card-time"></div>
                        <div class="schedule-card-content">
                            <div class="empty-slot-content">
                                <h3 class="schedule-subject"><i class="fa-solid fa-mug-hot"></i> ${getI18nValue("schedule.noClassSlot")}</h3>
                                <span class="schedule-duration">${durationText}</span>
                            </div>
                        </div>
                    </div>
                `;
            }
        }

        const startParts = lesson.start.split(':');
        const endParts = lesson.end.split(':');
        
        const startFormatted = `${parseInt(startParts[0])}:${startParts[1]}`;
        const endFormatted = `${parseInt(endParts[0])}:${endParts[1]}`;

        //Calculate duration
        const startMins = parseTime(lesson.start);
        const endMins = parseTime(lesson.end);
        const diffMinutes = endMins - startMins;
        
        let durationText = `${diffMinutes} min`;
        if (diffMinutes > 59) { //More than an hour
            const h = Math.floor(diffMinutes / 60);
            const m = diffMinutes % 60;
            durationText = `${h}h${m > 0 ? m.toString().padStart(2, '0') : ''}`; //render with hour and mins
        }
        
        const color = lesson.color;
        const isCanceled = lesson.canceled === true;
        const status = lesson.status || (isCanceled ? getI18nValue("schedule.canceledStatus") : null);
        
        const cardClass = isCanceled ? 'schedule-card canceled' : 'schedule-card';

        html += `
            <div class="${cardClass}" style="--course-color: ${color}">
                <div class="schedule-card-time">
                    <span class="start-time">${startFormatted}</span>
                    <span class="end-time">${endFormatted}</span>
                </div>
                <div class="schedule-card-content">
                    <h3 class="schedule-subject">
                        ${lesson.subject}
                        ${status ? `<span class="schedule-status-badge">${status}</span>` : ''}
                    </h3>
                    <div class="schedule-card-details">
                        ${lesson.room ? `
                        <div class="schedule-location">
                            <i class="fa-solid fa-location-dot"></i>
                            <span>${lesson.room}</span>
                        </div>` : ''}
                        ${lesson.teacher ? `
                        <div class="schedule-teacher">
                            <i class="fa-solid fa-user"></i>
                            <span>${lesson.teacher}</span>
                        </div>` : ''}
                        <span class="schedule-duration">${durationText} ${getI18nValue("schedule.durationOfClassText")}</span>
                    </div>
                </div>
            </div>
        `;
        
        lastEndTime = lesson.end;
    });
    
    container.innerHTML = html;
}

function updateScheduleView(date) {
    updateScheduleHeader(date);
    generateDateSelector(date);
    
    //to update hidden date picker value
    const datePicker = document.getElementById('scheduleDatePicker');
    if (datePicker) {
        const d = new Date(date);
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        datePicker.value = `${year}-${month}-${day}`;
    }

    fetchSchedule(date);
}

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

    // Update welcome section
    try {
        const welcomeElement = document.getElementById('welcomeGreeting');
        const welcomeSubtitle = document.getElementById('welcomeSubtitle');
        const studentFirstName = localStorage.getItem('student_firstname') || null; 
        
        if (welcomeElement) {
            if (studentFirstName) {
                welcomeElement.textContent = `${getGreeting()} ${studentFirstName} !`;
            } else {
                welcomeElement.textContent = `${getGreeting()} ! ${getTimeEmoji()}`;
            }
        }
        
        if (welcomeSubtitle) {
            welcomeSubtitle.textContent = `${getSubtitle()} ${getTimeEmoji()}`
        }
        
        // If no cached student data, fetch from API
        if (!studentFirstName) {
            wrapFetch('https://api.pronotif.tech/v1/app/fetch?fields=student_firstname', {
                method: 'GET',
                credentials: 'include',
                cache: 'no-store'
            })
            .then(response => response.json())
            .then(data => {
                if (data && data.data && data.data.student_firstname) {
                    const name = data.data.student_firstname.split(' ')[0];
                    console.log('Fetched student name:', name);
                    localStorage.setItem('student_firstname', name);
                    if (welcomeElement) {
                        welcomeElement.textContent = `${getGreeting()} ${name} !`;
                    }
                }
            })
            .catch(error => {
                console.warn('Failed to fetch student name:', error);
            });
        }
    } catch (error) {
        console.error('Error updating welcome section:', error);
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

    const initialFadeOutDuration = initialFadeOutOccurred ? 400 : 0;

    setTimeout(() => {
        // Hide all views
        document.querySelectorAll('.view').forEach(view => {
            view.classList.add('hidden');
            view.classList.remove('animating-out', 'fade-out', 'fade-in');
        });
        console.log('[UI] All previous views hidden.');

        // Show the dashboard immediately while data is being fetched
        if (dashboardView) {
            dashboardView.classList.remove('hidden');
            dashboardView.classList.add('fade-in');
            console.log('[UI] Dashboard view is now visible.');
        }
        showHomeworkLoadingState();
        showHomeworksPageLoadingState();

        initializeDashboard();
        
        // Initialize telemetry consent screen on dashboard
        telemetryConsentManager.init();

        // Lightweight pre-update
        setTimeout(() => {
            try { checkNotifEnabled(); } catch (e) { /* ignore */ }
            try { upateDynamicBanner(); } catch (e) { /* ignore */ }
            try { fetchSettings(); } catch (e) { console.error('[Settings] Error fetching settings on dashboard load:', e); }
        }, 200);

    }, initialFadeOutDuration);
}

function loadDemoData() {
    // Welcome section
    const welcomeElement = document.getElementById('welcomeGreeting');
    const welcomeSubtitle = document.getElementById('welcomeSubtitle');
    if (welcomeElement) {
        welcomeElement.textContent = `${getGreeting()} Demo ! `;
        welcomeSubtitle.textContent = `${getSubtitle()} ${getTimeEmoji()}`;
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


    // Homework section
    const homeworkList = document.querySelector('.homework-list');
    if (homeworkList) {
        homeworkList.innerHTML = `
            <div class="homework-item pending">
                <div class="homework-status">
                    <i class="fa-regular fa-circle"></i>
                </div>
                <div class="homework-content">
                    <h3 class="homework-subject">Mathématiques</h3>
                    <p class="homework-task">Exercices 5 à 12 page 47</p>
                </div>
                <div class="homework-due">Demain</div>
            </div>
            <div class="homework-item pending">
                <div class="homework-status">
                    <i class="fa-regular fa-circle"></i>
                </div>
                <div class="homework-content">
                    <h3 class="homework-subject">Histoire</h3>
                    <p class="homework-task">Apprendre la leçon sur la Révolution française</p>
                </div>
                <div class="homework-due">Vendredi</div>
            </div>
            <div class="homework-item pending">
                <div class="homework-status">
                    <i class="fa-regular fa-circle"></i>
                </div>
                <div class="homework-content">
                    <h3 class="homework-subject">Anglais</h3>
                    <p class="homework-task">Compléter la fiche de vocabulaire</p>
                </div>
                <div class="homework-due">Lundi</div>
            </div>
        `;
    }
}

async function fetchDashboardData() {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000); // 15 second timeout

        // Fetch student info and Pronote data
        const response = await wrapFetch("https://api.pronotif.tech/v1/app/fetch?fields=next_class_name,next_class_room,next_class_teacher,next_class_start,next_class_end,homeworks", {
            method: 'GET',
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
            window.lastDashboardData = result.data; //ttore for re-rendering on language change
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
    
    updateNextCourseCard(data);
    updateHomeworkSection(data);
    if (data.homeworks) {
        renderHomeworksPage(data.homeworks);
    }
    
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
            titleText += ` ${getI18nValue("dashboard.withWord")} ${data.next_class_teacher}`;
        }
        
        let detailsText = '';
        if (data.next_class_room && data.next_class_room !== null && data.next_class_room !== '') {
            detailsText += `${getI18nValue("dashboard.roomWord")} ${data.next_class_room}`;
        }
        if (data.next_class_start && data.next_class_start !== null && data.next_class_start !== '') {
            if (detailsText) detailsText += ' · ';
            detailsText += `${getI18nValue("dashboard.startAtWord")} ${data.next_class_start}`;
        }
        
        if (courseTitle) courseTitle.textContent = titleText;
        if (courseDetails) courseDetails.textContent = detailsText || 'Informations disponibles';
        
        nextCourseCard.style.display = 'block';
    } else {
        // No next class data available
        if (courseTitle) courseTitle.textContent = getI18nValue('dashboard.noUpcomingClassTitle');
        if (courseDetails) courseDetails.textContent = getI18nValue('dashboard.noUpcomingClassDesc');
        nextCourseCard.style.display = 'block';
    }
}

function showHomeworkLoadingState() {
    const homeworkList = document.querySelector('.homework-list');
    
    if (!homeworkList) {
        console.warn('Homework list element not found');
        return;
    }
    
    homeworkList.innerHTML = `
        <div class="homework-item">
            <div class="homework-status">
                <i class="fa-solid fa-spinner" style="animation: spin 2s linear infinite;"></i>
            </div>
            <div class="homework-content">
                <h3 class="homework-subject">${getI18nValue('dashboard.loading')}</h3>
                <p class="homework-task">${getI18nValue('dashboard.fetchingData')}</p>
            </div>
        </div>
    `;
}

function showHomeworksPageLoadingState() {
    const listTodo = document.getElementById('homeworkListTodo');
    const listDone = document.getElementById('homeworkListDone');
    
    const loadingHtml = `
        <div style="display: flex; justify-content: center; align-items: center; padding: 2rem; min-height: 200px; flex-direction: column;">
            <i class="fa-solid fa-spinner" style="animation: spin 2s linear infinite; font-size: 2.5rem; color: var(--primary); margin-bottom: 1rem;"></i>
            <p style="color: var(--subtitle-dark); margin: 0; font-family: 'Satoshi', sans-serif; font-weight:500">${getI18nValue('dashboard.loading')}</p>
        </div>
    `;

    if (listTodo) listTodo.innerHTML = loadingHtml;
    if (listDone) listDone.innerHTML = loadingHtml;
}

function updateHomeworkSection(data) {
    const homeworkList = document.querySelector('.homework-list');
    
    if (!homeworkList) {
        console.warn('Homework list element not found');
        return;
    }
    
    //Clear existing content
    homeworkList.innerHTML = '';
    
    if (!data.homeworks || !Array.isArray(data.homeworks) || data.homeworks.length === 0) {
        homeworkList.innerHTML = `
            <div class="homework-item empty-state">
                <div class="homework-content">
                    <h3 class="homework-subject">${getI18nValue("dashboard.noHomeworksTitle")}</h3>
                    <p class="homework-task">${getI18nValue("dashboard.noHomeworksDesc")}</p>
                </div>
            </div>
        `;
        return;
    }
    
    //Populate homework items
    data.homeworks.forEach((homework, index) => {
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = renderHomeworkCard(homework);
        const homeworkItem = tempDiv.firstElementChild;
        
        homeworkItem.dataset.homeworkId = homework.id || Math.random();
        homeworkItem.style.animationDelay = `${index * 0.05}s`;
        
        if (homework.done) {
            homeworkItem.classList.add('completed');
        } else {
            homeworkItem.classList.add('pending');
        }
        
        homeworkList.appendChild(homeworkItem);
        
        const swipeHint = document.createElement('div');
        swipeHint.className = `homework-item-swipe-hint ${homework.done ? 'unmark-hint' : 'mark-hint'}`;
        
        if (homework.done) {
            swipeHint.innerHTML = '<i class="fa-solid fa-xmark"></i>';
        } else {
            swipeHint.innerHTML = '<i class="fa-solid fa-check"></i>';
        }
        
        document.body.appendChild(swipeHint);
        
        attachSwipeListeners(homeworkItem, homework, swipeHint);
    });
    
    console.log('Homework section updated with', data.homeworks.length, 'items');
}

function renderHomeworkCard(hw) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const dueDate = new Date(hw.due_date);
    dueDate.setHours(0, 0, 0, 0);
    
    const dayDiff = Math.floor((dueDate - today) / (1000 * 60 * 60 * 24)); //Difference in days
    let dueDateText = '';
    
    if (dayDiff === 0) {
        dueDateText = getI18nValue('days.today');
    } else if (dayDiff === 1) {
        dueDateText = getI18nValue('days.tomorrow');
    } else if (dayDiff > 0) {
        dueDateText = `${getI18nValue('days.inWord')} ${dayDiff} ${getI18nValue('days.daysWord')}`;
    }

    const dateObj = new Date(hw.due_date);
    const day = dateObj.getDate();
    const monthName = dateObj.toLocaleString(getI18nValue("langCode"), { month: 'long' }).toLowerCase();

    const currentLang = localStorage.getItem('language') || 'fr';
    let formattedDate = '';
    
    if (currentLang === 'en') {
        formattedDate = `${day} of ${monthName}`;
    } else if (currentLang === 'es') {
        formattedDate = `${day} de ${monthName}`;
    } else {
        formattedDate = `${day} ${monthName}`;
    }

    return `
        <div class="homework-card" style="--card-color: ${hw.color}">
            <div class="homework-card-strip"></div>
            <div class="homework-card-content">
                <div class="homework-card-header">
                    <div class="homework-icon">${hw.emoji || '📝'}</div>
                    <div class="homework-info">
                        <h3 class="homework-card-title">${hw.subject}</h3>
                        <p class="homework-date-label">${getI18nValue('homework.forThe')} ${formattedDate}</p>
                    </div>
                    ${hw.done ? `<i class="homework-status-icon fa-solid fa-circle-check" style="color: ${hw.color}; font-size: 1.5rem;"></i>` : `<i class="homework-status-icon fa-regular fa-circle" style="color: var(--subtitle-dark); font-size: 1.5rem; opacity: 0.3;"></i>`}
                </div>
                <div class="homework-description">
                    ${hw.description || hw.content}
                </div>
                <div class="homework-footer">
                    <i class="fa-regular fa-calendar"></i>
                    <span>${dueDateText}</span>
                </div>
            </div>
        </div>
    `;
}

function renderHomeworksPage(homeworks) {
    const listTodo = document.getElementById('homeworkListTodo');
    const listDone = document.getElementById('homeworkListDone');
    
    if (!listTodo || !listDone) return;

    //Separate homeworks into todo and done
    const todoHomeworks = homeworks.filter(hw => !hw.done);
    const doneHomeworks = homeworks.filter(hw => hw.done);

    //Render todo homeworks
    if (todoHomeworks.length === 0) {
        listTodo.innerHTML = `
            <div class="homework-content-empty" style="padding: 2rem;">
                <i class="fa-solid fa-clipboard-check" style="font-size: 3rem; color: var(--subtitle-dark); margin-bottom: 1rem;"></i>
                <p>${getI18nValue('homework.noToDo')}</p>
            </div>
        `;
    } else {
        listTodo.innerHTML = '';
        todoHomeworks.forEach((hw, index) => {
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = renderHomeworkCard(hw);
            const homeworkItem = tempDiv.firstElementChild;
            
            homeworkItem.dataset.homeworkId = hw.id || Math.random();
            homeworkItem.classList.add('pending');
            homeworkItem.style.animationDelay = `${index * 0.05}s`;

            homeworkItem.addEventListener('animationend', () => {
                homeworkItem.style.animation = 'none';
                homeworkItem.style.opacity = '1';
            }, { once: true });
            
            listTodo.appendChild(homeworkItem);
            
            const swipeHint = document.createElement('div');
            swipeHint.className = `homework-item-swipe-hint mark-hint`;
            swipeHint.innerHTML = '<i class="fa-solid fa-check"></i>';
            
            document.body.appendChild(swipeHint);
            
            attachSwipeListeners(homeworkItem, hw, swipeHint);
        });
    }

    //Render done homeworks
    if (doneHomeworks.length === 0) {
        listDone.innerHTML = `
            <div class="homework-content-empty" style="padding: 2rem;">
                <i class="fa-solid fa-check-circle" style="font-size: 3rem; color: var(--subtitle-dark); margin-bottom: 1rem;"></i>
                <p>${getI18nValue('homework.noDone')}</p>
            </div>
        `;
    } else {
        listDone.innerHTML = '';
        doneHomeworks.forEach((hw, index) => {
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = renderHomeworkCard(hw);
            const homeworkItem = tempDiv.firstElementChild;
            
            homeworkItem.dataset.homeworkId = hw.id || Math.random();
            homeworkItem.classList.add('completed');
            homeworkItem.style.animationDelay = `${index * 0.05}s`;

            homeworkItem.addEventListener('animationend', () => {
                homeworkItem.style.animation = 'none';
                homeworkItem.style.opacity = '1';
            }, { once: true });
            
            listDone.appendChild(homeworkItem);
            
            const swipeHint = document.createElement('div');
            swipeHint.className = `homework-item-swipe-hint unmark-hint`;
            swipeHint.innerHTML = '<i class="fa-solid fa-xmark"></i>';
            
            document.body.appendChild(swipeHint);
            
            attachSwipeListeners(homeworkItem, hw, swipeHint);
        });
    }
}

function attachSwipeListeners(element, homework, hintElement) {
    let startX = 0;
    let currentX = 0;
    let isDragging = false;
    const threshold = 50; //Minimum swipe distance in pixels
    let elementRectStart = null; //store initial position
    let hasMovedSignificantly = false;

    element.addEventListener('touchstart', (e) => {
        startX = e.touches[0].clientX;
        isDragging = true;
        elementRectStart = element.getBoundingClientRect();
        hasMovedSignificantly = false;
        
        element.classList.remove('swiping-active');

        //force reset animation state
        element.style.animation = 'none'; 
        element.style.opacity = '1';
        
        if (hintElement) {
            hintElement.style.transform = '';
            hintElement.style.transition = '';
        }
        
        document.querySelectorAll('.homework-item-swipe-hint').forEach(hint => {
            if (hint !== hintElement) {
                hint.style.opacity = '0';
            }
        });
    }, false);

    element.addEventListener('touchmove', (e) => {
        if (!isDragging) return;
        
        currentX = e.touches[0].clientX;
        const diff = startX - currentX;
        
        if (diff > 0) {
            if (diff > 5) {
                e.preventDefault();
                document.body.style.overflow = 'hidden';
                document.documentElement.style.overflow = 'hidden';
                document.body.style.touchAction = 'none';
            }
            
            if (diff > 10) {
                hasMovedSignificantly = true;
            }
            
            element.style.transform = `translateX(-${Math.min(diff, 100)}px)`;
            
            if (diff > 10) {
                if (!element.classList.contains('swiping-active')) {
                    element.classList.add('swiping');
                    element.classList.add('swiping-active');
                }
            }
            
            if (hintElement) {
                const currentRect = element.getBoundingClientRect();
                const hintWidth = Math.min(diff, 100);
                
                hintElement.style.height = currentRect.height + 'px';
                hintElement.style.width = hintWidth + 'px';
                
                hintElement.style.left = currentRect.right + 'px';
                hintElement.style.top = currentRect.top + 'px';
                
                if (diff > threshold) {
                    hintElement.style.opacity = '1';
                } else {
                    hintElement.style.opacity = Math.max(0, diff / threshold) * 0.7;
                }
            }
        }
    }, false);

    element.addEventListener('touchend', (e) => {
        if (!isDragging) return;
        
        isDragging = false;
        const diff = startX - currentX;
        
        if (diff > threshold) {
            
            element.classList.remove('swiping');
            element.classList.add('swiping-reset');
            element.style.transform = 'translateX(0)';
            
            const rect = element.getBoundingClientRect();
            
            if (hintElement) {
                hintElement.style.height = rect.height + 'px';
                hintElement.style.left = rect.right + 'px';
                hintElement.style.top = rect.top + 'px';
                hintElement.style.opacity = '0';
                hintElement.style.transform = 'translateX(50px)';
                hintElement.style.transition = 'all 0.3s ease-out';
            }
            
            setTimeout(() => {
                if (homework.done) {
                    homework.done = false;
                    element.classList.remove('completed');
                    element.classList.add('pending');
                    
                    const statusIcon = element.querySelector('.homework-status-icon');
                    if (statusIcon) {
                        statusIcon.className = 'homework-status-icon fa-regular fa-circle';
                        statusIcon.style.color = 'var(--subtitle-dark)';
                        statusIcon.style.opacity = '0.3';
                    }
                    
                    hintElement.className = `homework-item-swipe-hint mark-hint`;
                    hintElement.innerHTML = '<i class="fa-solid fa-check"></i>';
                    
                    // Call unmark
                    unmarkHomeworkAsDone(homework);
                } else {
                    homework.done = true;
                    element.classList.add('completed');
                    element.classList.remove('pending');
                    
                    const statusIcon = element.querySelector('.homework-status-icon');
                    if (statusIcon) {
                        statusIcon.className = 'homework-status-icon fa-solid fa-circle-check';
                        statusIcon.style.color = homework.color;
                        statusIcon.style.opacity = '1';
                    }
                    
                    hintElement.className = `homework-item-swipe-hint unmark-hint`;
                    hintElement.innerHTML = '<i class="fa-solid fa-xmark"></i>';
                    
                    //Done
                    markHomeworkAsDone(homework);
                }
            }, 300);
        } else {
            // Reset position
            element.classList.remove('swiping');
            element.classList.add('swiping-reset');
            element.style.transform = 'translateX(0)';
            
            const rect = element.getBoundingClientRect();
            
            if (hintElement) {
                hintElement.style.height = rect.height + 'px';
                hintElement.style.left = rect.right + 'px';
                hintElement.style.top = rect.top + 'px';
                hintElement.style.opacity = '0';
                hintElement.style.transform = 'translateX(50px)';
                hintElement.style.transition = 'all 0.3s ease-out';
            }
        }
        
        setTimeout(() => {
            element.classList.remove('swiping');
            element.classList.remove('swiping-reset');
            element.classList.remove('swiping-active');
            document.body.style.overflow = '';
            document.documentElement.style.overflow = '';
            document.body.style.touchAction = 'auto';
        }, 300);
    }, false);

    element.addEventListener('touchcancel', () => {
        isDragging = false;
        element.style.transform = 'translateX(0)';
        if (hintElement) {
            hintElement.style.opacity = '0';
        }
        element.classList.remove('swiping');
        document.body.style.overflow = '';
        document.documentElement.style.overflow = '';
        document.body.style.touchAction = 'auto';
    }, false);
}
//TODO: Implement actual API calls to mark/unmark homework
async function markHomeworkAsDone(homework) {
    if (!homework || !homework.id) return;
    console.log('Marking homework as done:', homework.id);
    
    try {
        const response = await wrapFetch('https://api.pronotif.tech/v1/app/homework/set-status', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                id: homework.id,
                done: true,
            }),
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Failed to update status');
        }
    } catch (error) {
        console.error('Error updating homework status:', error);
        toast.error(getI18nValue("toast.globalErrorTitle"), getI18nValue("toast.homeworkStatusUpdateFailedDesc"));
    }
}

async function unmarkHomeworkAsDone(homework) {
    if (!homework || !homework.id) return;
    console.log('Unmarking homework as done:', homework.id);
    
    try {
        const response = await wrapFetch('https://api.pronotif.tech/v1/app/homework/set-status', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                id: homework.id,
                done: false
            }),
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Failed to update status');
        }
    } catch (error) {
        console.error('Error updating homework status:', error);
        toast.error(getI18nValue("toast.globalErrorTitle"), getI18nValue("toast.homeworkStatusUpdateFailedDesc"));
    }
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
            infoNotifTitle.textContent = getI18nValue('toast.enableNotificationSuccessTitle');
            infoNotifText.textContent = getI18nValue('toast.enableNotificationSuccessDesc');
            
            const currentPermission = Notification.permission;

            // Update stored permission
            localStorage.setItem('notificationPermission', currentPermission);

            if (isIOS) {
                console.log('iOS detected, showing success message then reloading');
                infoNotifText.textContent = getI18nValue("toast.iosNotificationsAppRestartMessage");
                // Show success message for 5 seconds and reload
                setTimeout(() => {
                    window.location.reload();
                }, 3000);
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
            infoNotifTitle.textContent = getI18nValue('toast.enableNotificationDeniedTitle');
            infoNotifText.textContent = getI18nValue('toast.enableNotificationDeniedDesc');

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

let currentLanguageData = {};

function getNestedValue(obj, keyPath) {
    return keyPath.split('.').reduce((current, key) => current?.[key], obj);
}

function getI18nValue(keyPath) {
    return getNestedValue(currentLanguageData, keyPath) || keyPath;
}

function attachScheduleSwipeListeners() { //for swipe schedule feature
    const scheduleList = document.querySelector('.schedule-list');
    if (!scheduleList) return;

    let touchStartX = 0;
    let touchStartY = 0;
    
    scheduleList.addEventListener('touchstart', (e) => { //record start position
        touchStartX = e.changedTouches[0].screenX;
        touchStartY = e.changedTouches[0].screenY;
    }, { passive: true });

    scheduleList.addEventListener('touchend', (e) => { //record end position and determine swipe
        const touchEndX = e.changedTouches[0].screenX;
        const touchEndY = e.changedTouches[0].screenY;
        
        const minSwipeDistance = 50;
        const maxVerticalDistance = 50;
        const distanceX = touchEndX - touchStartX;
        const distanceY = touchEndY - touchStartY;

        if (Math.abs(distanceX) > minSwipeDistance && Math.abs(distanceY) < maxVerticalDistance) { //horizontal swipe detected
            const datePicker = document.getElementById('scheduleDatePicker');
            if (!datePicker || !datePicker.value) return;

            const currentDate = new Date(datePicker.value);
            
            if (distanceX > 0) {//swipe right
                currentDate.setDate(currentDate.getDate() - 1);

            } else {//swipe left
                currentDate.setDate(currentDate.getDate() + 1);
            }
            
            updateScheduleView(currentDate);
        }
    }, { passive: true });
}

//Telemetry Consent Screen
const telemetryConsentManager = {
    init() {
        const screen = document.getElementById('telemetryConsentScreen');
        const acceptBtn = document.getElementById('telemetryAcceptBtn');
        const continueBtn = document.getElementById('telemetryContinueBtn');
        
        if (!screen || !acceptBtn || !continueBtn) {
            console.error('[Telemetry] Screen elements not found');
            return;
        }

        //if on dashboard
        const dashboardView = document.getElementById('dashboardView');
        const isOnDashboard = dashboardView && !dashboardView.classList.contains('hidden');
        
        if (!isOnDashboard) {
            console.log('[Telemetry] Not on dashboard view, hiding telemetry consent screen');
            screen.classList.add('hidden');
            return;
        }

        const telemetryConsent = localStorage.getItem('telemetryConsent');
        
        if (telemetryConsent !== null) {
            // User has already made a choice - hide the screen
            screen.classList.add('hidden');
            return;
        }

        //if no choice show it
        screen.classList.remove('hidden');

        acceptBtn.addEventListener('click', () => {
            this.handleConsent(true, screen);
        });

        continueBtn.addEventListener('click', () => {
            this.handleConsent(false, screen);
        });
    },

    handleConsent(enableDiagnostics, screen) {

        localStorage.setItem('telemetryConsent', enableDiagnostics ? 'true' : 'false');
        
        //update the consent flag
        window.sentryConsent = enableDiagnostics;
        
        console.log('[Telemetry] User consent updated:', enableDiagnostics ? 'enabled' : 'disabled');

        //Disable interactions during animation
        screen.style.pointerEvents = 'none';

        screen.classList.add('closing');

        setTimeout(() => {
            screen.classList.add('hidden');
            screen.classList.remove('closing');
        }, 400);
    }
};

document.addEventListener('DOMContentLoaded', async () => {
    // Initialize telemetry consent popup
    telemetryConsentManager.init();
    
    //Initialize schedule swipe listeners
    attachScheduleSwipeListeners();

    async function loadLanguage(languageCode) {
        try {
            console.log(`[i18n] Loading language: ${languageCode}`);
            const response = await fetch(`../locales/${languageCode}.json`, {
                cache: 'no-store'
            });
            
            if (!response.ok) {
                console.error(`[i18n] Failed to load language file for ${languageCode}`);
                return false;
            }
            
            currentLanguageData = await response.json();
            console.log(`[i18n] Language loaded successfully !`);
            applyLanguageToPage();
            return true;
        } catch (error) {
            console.error(`[i18n] Error loading language:`, error);
            return false;
        }
    }

    function applyLanguageToPage() {
        //Find all elements with data-i18n attribute and update their text content
        document.querySelectorAll('[data-i18n]').forEach(element => {
            const key = element.getAttribute('data-i18n');
            const value = getNestedValue(currentLanguageData, key);
            if (value) {
                element.textContent = value;
            }
        });
        
        //Find all elements with data-i18n-placeholder attribute and update their placeholder
        document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
            const key = element.getAttribute('data-i18n-placeholder');
            const value = getNestedValue(currentLanguageData, key);
            if (value) {
                element.placeholder = value;
            }
        });

        //Titles
        document.querySelectorAll('[data-i18n-title]').forEach(element => {
            const key = element.getAttribute('data-i18n-title');
            const value = getNestedValue(currentLanguageData, key);
            if (value) {
                element.title = value;
            }
        });

        //Update date selector items
        document.querySelectorAll('.schedule-date-selector .date-item').forEach(item => {
            const date = new Date(item.dataset.date);
            const dayName = date.toLocaleDateString((getI18nValue("langCode")), { weekday: 'short' }).replace('.', '').toUpperCase();
            const dayNameSpan = item.querySelector('.date-day');
            if (dayNameSpan) {
                dayNameSpan.textContent = dayName;
            }
        });

        //Update schedule header if visible
        const selectedDateItem = document.querySelector('.schedule-date-selector .date-item.selected');
        if (selectedDateItem) {
            const selectedDate = new Date(selectedDateItem.dataset.date);
            updateScheduleHeader(selectedDate);
        }
        
        console.log('[i18n] Language applied to page elements');

        //re render dashboard data if exists
        if (window.lastDashboardData) {
            console.log('[i18n] Re-rendering dashboard data with new language');
            updateDashboardWithData(window.lastDashboardData);
        }
    }

    function updateLanguageOptions() {
        const currentLanguage = localStorage.getItem('language') || 'fr';
        const languageOptions = document.querySelectorAll('.language-option');
        
        languageOptions.forEach(option => {
            const lang = option.getAttribute('data-language');
            if (lang === currentLanguage) {
                option.classList.add('selected');
            } else {
                option.classList.remove('selected');
            }
        });
    }

    let userLanguage = localStorage.getItem('language');
    
    //If no saved language try from browser
    if (!userLanguage) {

        const browserLanguage = navigator.language || navigator.userLanguage;
        const browserLangCode = browserLanguage.split('-')[0].toLowerCase();
        //check if supported, defauult to french
        const supportedLanguages = ['fr', 'en', 'es'];
        userLanguage = supportedLanguages.includes(browserLangCode) ? browserLangCode : 'fr';
        
        console.log('[i18n] Detected browser language:', browserLanguage, '-> Using:', userLanguage);
    } else {
        console.log('[i18n] Using saved language:', userLanguage);
    }
    
    localStorage.setItem('language', userLanguage);
    
    console.log('[i18n] Initializing with language:', userLanguage);
    await loadLanguage(userLanguage);

    //Check for post reload toast
    const postReloadToastData = localStorage.getItem('postReloadToast');
    if (postReloadToastData) {
        try {
            const toastData = JSON.parse(postReloadToastData);
            setTimeout(() => {
                if (toastData.type === 'success') {
                    toast.success(toastData.title, toastData.message);
                } else if (toastData.type === 'error') {
                    toast.error(toastData.title, toastData.message);
                } else {
                    toast.info(toastData.title, toastData.message);
                }
            }, 500);
            localStorage.removeItem('postReloadToast');
        } catch (e) {
            console.error('Failed to parse post-reload toast:', e);
            localStorage.removeItem('postReloadToast');
        }
    }

    function updateCookieContainer() {
        const cookieContainer = document.getElementById('cookieContainer');
        if (cookieContainer) {
            const cookies = document.cookie.split(';').map(c => c.trim()).filter(Boolean);
            if (cookies.length === 0) {
                cookieContainer.textContent = "Aucun cookie trouvé.";
            } else {
                cookieContainer.innerHTML = cookies.map(cookie => {
                    const [key, ...val] = cookie.split('=');
                    return `<div><strong>${key}</strong>: ${decodeURIComponent(val.join('='))}</div>`;
                }).join('');
            }
        }
    }

    function updateLocalStorageContainer() {
        const localStorageContainer = document.getElementById('localStorageContainer');
        if (localStorageContainer) {
            if (localStorage.length === 0) {
                localStorageContainer.textContent = "Aucune donnée localStorage.";
            } else {
                localStorageContainer.innerHTML = Object.keys(localStorage).map(key => {
                    let value = localStorage.getItem(key);
                    
                    try {
                        value = JSON.stringify(JSON.parse(value), null, 2);
                    } catch {}
                    return `<div><strong>${key}</strong>: <pre style="display:inline">${value}</pre></div>`;
                }).join('');
            }
        }
    }

    updateLocalStorageContainer();
    updateCookieContainer();

    const clearCacheBtn = document.getElementById('clearCacheButton');
    if (clearCacheBtn) {
        clearCacheBtn.addEventListener('click', async () => {
            // Remove localStorage and sessionStorage
            localStorage.clear();
            sessionStorage.clear();

            // Unregister all service workers
            if ('serviceWorker' in navigator) {
                const registrations = await navigator.serviceWorker.getRegistrations();
                for (const reg of registrations) {
                    await reg.unregister();
                }
            }

            // Remove all caches
            if ('caches' in window) {
                const cacheNames = await caches.keys();
                for (const name of cacheNames) {
                    await caches.delete(name);
                }
            }

            toast.success('Cache supprimé !', "L'application va redémarrer.");
            window.location.reload();
        });
    }

    const simulateNotifBtn = document.getElementById('simulateNotifButton');
    const simulateNotifButtonSubTitle = document.getElementById('simulateNotifButtonSubTitle');

    if (simulateNotifBtn) {
        simulateNotifBtn.addEventListener('click', async () => {
            simulateNotifBtn.disabled = true;
            simulateNotifButtonSubTitle.textContent = "Envoi en cours...";
            try {
                const response = await wrapFetch('https://api.pronotif.tech/v1/app/send-test-notif', {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();
                if (data.success) {
                    toast.success("Notification de test envoyée !", "Vérifiez que vous l'avez bien reçue.");
                    console.log("Test notification succesfully sent ! ", data.message_id);
                } else {
                    toast.error("Erreur", "Erreur lors de l'envoi de la notification.");
                    console.error("Test notification error:", data.error);
                }
            } catch (err) {
                toast.error("Erreur réseau.", "Impossible de contacter le serveur.");
                console.error("Network error sending test notification:", err);
            } finally {
                simulateNotifBtn.disabled = false;
                simulateNotifButtonSubTitle.textContent = "Simuler une notification";
            }
        });
    }

    const resetFCMTokenButton = document.getElementById('resetFCMTokenButton');
    const resetFCMTokenButtonSubTitle = document.getElementById('resetFCMTokenButtonSubTitle');

    if (resetFCMTokenButton) {
        resetFCMTokenButton.addEventListener('click', async () => {
            resetFCMTokenButton.disabled = true;
            resetFCMTokenButtonSubTitle.textContent = "Suppression en cours...";
            
            await revokeFCMToken();
            localStorage.removeItem('fcmToken');
            localStorage.removeItem('fcmTokenTimestamp');

            toast.success("Token FCM supprimé !", "Un nouveau sera généré au demarrage si les notifications sont activées.");
            resetFCMTokenButton.disabled = false;
            resetFCMTokenButtonSubTitle.textContent = "Réinitialiser le token FCM";
        });
    }

    const debugLogoutButton = document.getElementById('debugLogoutButton');
    const debugLogoutButtonSubTitle = document.getElementById('debugLogoutButtonSubTitle');

    if (debugLogoutButton) {
        debugLogoutButton.addEventListener('click', async () => {
            debugLogoutButton.disabled = true;
            debugLogoutButtonSubTitle.textContent = "Déconnexion en cours...";

            await performLogout();
            
            debugLogoutButton.disabled = false;
            debugLogoutButtonSubTitle.textContent = "Se déconnecter";
        });
    }

    const resetNotifGrantButton = document.getElementById('resetNotifGrantButton');
    const resetNotifGrantButtonSubTitle = document.getElementById('resetNotifGrantButtonSubTitle');

    if (resetNotifGrantButton) {
        resetNotifGrantButton.addEventListener('click', async () => {
            resetNotifGrantButton.disabled = true;
            resetNotifGrantButtonSubTitle.textContent = "Réinitialisation en cours...";

            // Clear notification permission state
            localStorage.setItem('notificationPermission', 'default');
            document.cookie = "notifDismissed=false; path=/; max-age=31536000"; //Reset dismissed cookie

            if (Notification.permission === 'denied') {
                toast.warning("Notifications bloquées !", "Veuillez les activer manuellement dans les paramètres de votre appareil.");
            }

            toast.success("L'état des notifications a été réinitialisé", "Vous pouvez maintenant les réactiver si besoin.");
            resetNotifGrantButton.disabled = false;
            resetNotifGrantButtonSubTitle.textContent = "Réinitialiser l'état des notifications";
        });
    }

    


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
        if (e.target.id === 'debugTrigger' || e.target.classList.contains('login-header-app-name') || e.target.classList.contains('app-version')) {
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
        updateCookieContainer();
        updateLocalStorageContainer();
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

                        // Password visibility toggle (eye icon)
                        const togglePasswordBtn = document.getElementById('togglePassword');
                        const passwordInput = document.getElementById('loginPasswordInput');
                        if (togglePasswordBtn && passwordInput) {
                           if (!togglePasswordBtn.dataset.bound) {
                               togglePasswordBtn.addEventListener('click', () => {
                                   const isHidden = passwordInput.type === 'password';
                                   passwordInput.type = isHidden ? 'text' : 'password';
                                   const icon = togglePasswordBtn.querySelector('i');
                                   if (icon) {
                                       icon.classList.toggle('fa-eye');
                                       icon.classList.toggle('fa-eye-slash');
                                   }
                                   togglePasswordBtn.setAttribute('aria-label', isHidden ? 'Masquer le mot de passe' : 'Afficher le mot de passe');
                               });
                               togglePasswordBtn.dataset.bound = 'true';
                           }
                        }
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

    let loggedInElsewhereWarningShown = false; //Prevent duplicate toasts

    function checkExistingSession(retryCount = 0) {
        const startTime = Date.now();
        let transitioned = false;
        let sessionInvalid401 = false;

        //show spinner if loading takes too long
        const spinnerTimeout = setTimeout(() => {
            if (!transitioned) {
                const spinner = document.querySelector('.spinner-large');
                if (spinner) {
                    spinner.classList.add('show');
                    console.log('[Loading] Spinner shown');
                } else {
                    console.warn('[Loading] Spinner element not found');
                }
            }
        }, 1500);


        function handleTransition(callback) {
            transitioned = true;
            clearTimeout(spinnerTimeout);
            
            // Hide spinnes
            const spinner = document.querySelector('.spinner-large');
            if (spinner && spinner.classList.contains('show')) {
                spinner.classList.remove('show');
                console.log('[Loading] Spinner hidden');
            }
            
            callback();
        }

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
            handleTransition(() => showDashboard());
            return;
        }

        // Explicitly set demo mode to false if not in demo mode
        window.appDemoMode = false;

        if (!navigator.onLine) {
            console.warn('[Auth] Device is offline, showing login view');
            handleTransition(() => showLoginView());
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
            if (response.status === 401) {
                //Session invalid might be logged in elsewhere
                console.warn('[Auth] Session invalid user may be logged in elsewhere');
                sessionInvalid401 = true;
                throw new Error('Session expired logged in elsewhere');
            }
            
            if (!response.ok) {
                throw new Error(`Auth refresh failed: ${response.status} ${response.statusText}`);
            }
            return response.json();
        })
        .then(() => {
            console.info('[Auth] Session refreshed successfully');
            handleTransition(() => showDashboard());
        })
        .catch(async (error) => {
            console.warn('[Auth] Session check failed:', error.message);
            
            if (sessionInvalid401 || error.message.includes('logged in elsewhere')) {
                //Only show warning if not already shown
                if (!loggedInElsewhereWarningShown) {
                    loggedInElsewhereWarningShown = true;
                    handleTransition(() => {
                        showLoginView();
                        //Reset FCM locally
                        localStorage.removeItem('fcmToken');
                        localStorage.removeItem('fcmTokenTimestamp');

                    });
                }
            } else {
                // 3 retries for timeout errors only
                if (retryCount < 3 && error.message.includes('timed out')) {
                    console.info(`[Auth] Retrying session check (${retryCount + 1}/3)...`);
                    setTimeout(() => checkExistingSession(retryCount + 1), 1000);
                } else {
                    handleTransition(() => showLoginView());
                }
            }
        });
    }

    // Show only loading view initially
    document.querySelectorAll('.view').forEach(view => {
        view.classList.add('hidden');
    });

    const loadingView = document.getElementById('loadingView');
    if (loadingView) {
        loadingView.classList.remove('hidden');
        console.log('[Loading] Loading view displayed');
    }
    
    // check session
    checkExistingSession();

    //Theme color management
    function updateThemeColor(viewType) {
        const themeColorLight = document.getElementById('themeColorLight');
        const themeColorDark = document.getElementById('themeColorDark');
        const themeColorDefault = document.getElementById('themeColorDefault');
        
        if (viewType === 'settings') {
            themeColorLight?.setAttribute('content', '#FFEEDB');
            themeColorDark?.setAttribute('content', '#FFEEDB');
            themeColorDefault?.setAttribute('content', '#FFEEDB');
        } else if (viewType === 'schedule') {
            themeColorLight?.setAttribute('content', '#FFEEDB');
            themeColorDark?.setAttribute('content', '#FFEEDB');
            themeColorDefault?.setAttribute('content', '#FFEEDB');
        } else {
            themeColorLight?.setAttribute('content', '#07A19F');
            themeColorDark?.setAttribute('content', '#07A19F');
            themeColorDefault?.setAttribute('content', '#07A19F');
        }
    }

    //Navbar
    const navbarHomeBtn = document.getElementById('navbarHomeBtn');
    const bottomNavbar = document.querySelector('.bottom-navbar');
    
    if (navbarHomeBtn) {
        navbarHomeBtn.addEventListener('click', () => {
            //Hide all views
            document.querySelectorAll('.view').forEach(view => {
                view.classList.add('hidden');
            });
            
            //Show dashboard
            const dashboardView = document.getElementById('dashboardView');
            if (dashboardView) {
                dashboardView.classList.remove('hidden');
                updateThemeColor('dashboard');

                //scroll to top
                const dashboardContainer = document.querySelector('.dashboard-container');
                if (dashboardContainer) {
                    dashboardContainer.scrollTo({ top: 0, behavior: 'smooth' });
                }
            }
            
            document.querySelectorAll('.navbar-item').forEach(item => {
                item.classList.remove('active');
            });
            navbarHomeBtn.classList.add('active');
            
            console.log('[Navbar] Home button clicked');
        });
        
        const observer = new MutationObserver(() => {
            const dashboardView = document.getElementById('dashboardView');
            const homeworkView = document.getElementById('homeworkView');
            const settingsView = document.getElementById('settingsView');
            const scheduleView = document.getElementById('scheduleView');

            const isAnyViewVisible = (dashboardView && !dashboardView.classList.contains('hidden')) ||
                                     (homeworkView && !homeworkView.classList.contains('hidden')) ||
                                     (settingsView && !settingsView.classList.contains('hidden')) ||
                                     (scheduleView && !scheduleView.classList.contains('hidden'));

            if (isAnyViewVisible) {
                if (bottomNavbar) {
                    bottomNavbar.style.display = 'flex';
                }
                if (dashboardView && !dashboardView.classList.contains('hidden')) {
                    navbarHomeBtn.classList.add('active');
                } else {
                    navbarHomeBtn.classList.remove('active');
                }
            } else {
                if (bottomNavbar) {
                    bottomNavbar.style.display = 'none';
                }
                navbarHomeBtn.classList.remove('active');
            }
        });
        
        const viewsToObserve = ['dashboardView', 'homeworkView', 'settingsView', 'scheduleView'];
        viewsToObserve.forEach(viewId => {
            const element = document.getElementById(viewId);
            if (element) {
                observer.observe(element, { 
                    attributes: true, 
                    attributeFilter: ['class'] 
                });
            }
        });
    }

    const navbarScheduleBtn = document.getElementById('navbarScheduleBtn');
    const navbarHomeworkBtn = document.getElementById('navbarHomeworkBtn');
    
    if (navbarScheduleBtn) {
        navbarScheduleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            
            //Update active state
            document.querySelectorAll('.navbar-item').forEach(item => {
                item.classList.remove('active');
            });
            navbarScheduleBtn.classList.add('active');
            
            console.log('[Navbar] Schedule button clicked');
            
            //Hide all views
            document.querySelectorAll('.view').forEach(view => {
                view.classList.add('hidden');
            });

            const scheduleView = document.getElementById('scheduleView');
            if (scheduleView) {
                console.log('[Schedule] Showing schedule view');
                scheduleView.classList.remove('hidden');
                updateThemeColor('schedule');
                updateScheduleView(new Date());
            } else {
                console.warn('[Schedule] Schedule view not found!');
            }
        });
    }
    
    
    const tabTodo = document.getElementById('tabTodo');
    const tabDone = document.getElementById('tabDone');
    const listTodo = document.getElementById('homeworkListTodo');
    const listDone = document.getElementById('homeworkListDone');

    if (tabTodo && tabDone && listTodo && listDone) {
        tabTodo.addEventListener('click', () => {
            tabTodo.classList.add('active');
            tabDone.classList.remove('active');
            listTodo.classList.remove('hidden');
            listDone.classList.add('hidden');
        });

        tabDone.addEventListener('click', () => {
            tabDone.classList.add('active');
            tabTodo.classList.remove('active');
            listDone.classList.remove('hidden');
            listTodo.classList.add('hidden');
        });
    }

    if (navbarHomeworkBtn) {
        navbarHomeworkBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            
            //Update active state
            document.querySelectorAll('.navbar-item').forEach(item => {
                item.classList.remove('active');
            });
            navbarHomeworkBtn.classList.add('active');
            
            console.log('[Navbar] Homework button clicked');
            
            //Hide all views
            document.querySelectorAll('.view').forEach(view => {
                view.classList.add('hidden');
            });

            const homeworkView = document.getElementById('homeworkView');
            if (homeworkView) {
                console.log('[Homework] Showing homework view');
                homeworkView.classList.remove('hidden');
                updateThemeColor('homework');
            } else {
                console.warn('[Homework] Homework view not found!');
            }
        });
    }

    const navbarSettingsBtn = document.getElementById('navbarSettingsBtn');
    if (navbarSettingsBtn) {
        navbarSettingsBtn.addEventListener('click', async () => {
            //Update active state
            document.querySelectorAll('.navbar-item').forEach(item => {
                item.classList.remove('active');
            });
            navbarSettingsBtn.classList.add('active');
            
            console.log('[Navbar] Settings button clicked');
            
            //same as upper settings button
            document.querySelectorAll('.view').forEach(view => {
                view.classList.add('hidden');
            });

            const settingsView = document.getElementById('settingsView');
            if (settingsView) {
                console.log('[Settings] Showing settings view');
                settingsView.classList.remove('hidden');
                updateThemeColor('settings');
                console.log('[Settings] Settings view classes:', settingsView.className);
                
                // Fetch and populate settings when settings view is opened
                await fetchSettings();
            } else {
                console.warn('[Settings] Settings view not found!');
            }
        });
    }

    //Report bug button
    const reportBugItem = document.getElementById('settingsReportBugItem');
    if (reportBugItem) {
        reportBugItem.addEventListener('click', async () => {
            console.log('[Settings] Opening Sentry feedback');
            try {
                const feedback = window.Sentry?.getFeedback?.();
                if (feedback) {

                    const form = await feedback.createForm();
                    form.appendToDom();
                    form.open();
                } else {
                    toast.warning(getI18nValue("toast.globalErrorTitle"), getI18nValue("toast.reportSystemUnavailableDes"));
                    console.warn('[Settings] Sentry feedback not available');
                }
            } catch (error) {
                console.error('[Settings] Error opening feedback:', error);
                toast.error(getI18nValue("toast.globalErrorTitle"), getI18nValue("toast.reportSystemErrorDesc"));
            }
        });
    }

    // Settings logout button
    const settingsLogoutItem = document.getElementById('settingsLogoutItem');
    if (settingsLogoutItem) {
        settingsLogoutItem.addEventListener('click', async () => {
            await performLogout();
        });
    }

    // Settings delete account button
    const settingsDeleteAccountItem = document.getElementById('settingsDeleteAccountItem');
    if (settingsDeleteAccountItem) {
        settingsDeleteAccountItem.addEventListener('click', async () => {
            console.log('[Settings] Delete account button clicked');
            await performDeleteAccount();
        });
    }

    //Theme Management
    function initializeTheme() {
        const savedTheme = localStorage.getItem('appTheme') || 'system';
        applyTheme(savedTheme, { animate: false });
        updateThemeLabel(savedTheme);
        
        //Listen for system theme changes
        if (window.matchMedia) {
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
                const currentTheme = localStorage.getItem('appTheme') || 'system';
                if (currentTheme === 'system') {
                    console.log('[Theme] System theme changed, reapplying theme');
                    //Animate when system theme toggles
                    applyTheme('system', { animate: true });
                }
            });
        }
    }

    function applyTheme(theme, { animate = false } = {}) {
        const root = document.documentElement;

        if (animate) {
            root.classList.add('theme-transitioning');
            void root.offsetHeight; 
        }

        if (theme === 'system') {
            //Use system preference
            if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
                root.setAttribute('data-theme', 'dark');
                root.style.colorScheme = 'dark';
            } else {
                root.removeAttribute('data-theme');
                root.style.colorScheme = 'light';
            }
        } else if (theme === 'dark') {
            root.setAttribute('data-theme', 'dark');
            root.style.colorScheme = 'dark';
        } else if (theme === 'light') {
            root.removeAttribute('data-theme');
            root.style.colorScheme = 'light';
        }
        
        // Remove transition class after transition completes
        if (animate) {
            setTimeout(() => {
                root.classList.remove('theme-transitioning');
            }, 500);
        }

        localStorage.setItem('appTheme', theme);
        console.log('[Theme] Applied theme:', theme);
    }

    function updateThemeLabel(theme) {
        const labelMap = {
            'light': getI18nValue('modal.light'),
            'dark': getI18nValue('modal.dark'),
            'system': getI18nValue('modal.system')
        };
        const settingsAppearanceLabel = document.querySelector('#settingsAppearanceItem .settings-item-label');
        if (settingsAppearanceLabel) {
            settingsAppearanceLabel.textContent = labelMap[theme] || getI18nValue('modal.system');
        }
    }

    const settingsAppearanceItem = document.getElementById('settingsAppearanceItem');
    if (settingsAppearanceItem) {
        settingsAppearanceItem.addEventListener('click', async () => {
            console.log('[Settings] Appearance button clicked');
            const modal = document.getElementById('themeSelectorModal');
            if (modal) {
                modal.classList.remove('hidden');

                const currentTheme = localStorage.getItem('appTheme') || 'system';
                document.querySelectorAll('.theme-option').forEach(option => {
                    option.classList.remove('selected');
                });
                const selectedButton = document.getElementById('theme' + currentTheme.charAt(0).toUpperCase() + currentTheme.slice(1));
                if (selectedButton) {
                    selectedButton.classList.add('selected');
                }
            }
        });
    }

    //Theme option buttons
    const themeOptions = document.querySelectorAll('.theme-option');
    themeOptions.forEach(option => {
        option.addEventListener('click', () => {
            const theme = option.getAttribute('data-theme');
            applyTheme(theme, { animate: true });
            updateThemeLabel(theme);
            
            themeOptions.forEach(opt => opt.classList.remove('selected'));
            option.classList.add('selected');
            
            console.log('[Theme] Theme changed to:', theme);
            
            const modal = document.getElementById('themeSelectorModal');
            if (modal) {
                modal.classList.add('closing');
                setTimeout(() => {
                    modal.classList.add('hidden');
                    modal.classList.remove('closing');
                }, 300);
            }
        });
    });

    const themeOverlay = document.querySelector('.theme-overlay');
    if (themeOverlay) {
        themeOverlay.addEventListener('click', (e) => {
            if (e.target === themeOverlay) {
                const modal = document.getElementById('themeSelectorModal');
                if (modal) {
                    modal.classList.add('closing');
                    setTimeout(() => {
                        modal.classList.add('hidden');
                        modal.classList.remove('closing');
                    }, 300);
                }
            }
        });
    }

    //Initialize theme on page load
    initializeTheme();

    //settings name edit button
    const settingsNameItem = document.getElementById('settingsNameItem');
    if (settingsNameItem) {
        settingsNameItem.addEventListener('click', async () => {
            console.log('[Settings] Name edit button clicked');
            const modal = document.getElementById('nameEditModal');
            const input = document.getElementById('nameEditInput');
            
            if (!modal || !input) {
                console.error('[Settings] Name edit modal elements not found');
                return;
            }
        
            const currentName = localStorage.getItem('student_firstname') || '';
            input.value = currentName;
            input.focus();
            
            modal.classList.remove('hidden');
            setTimeout(() => input.focus(), 100);
        });
    }
    const nameEditCancel = document.getElementById('nameEditCancel');
    if (nameEditCancel) {
        nameEditCancel.addEventListener('click', () => {
            const modal = document.getElementById('nameEditModal');
            if (modal) {
                modal.classList.add('closing');
                setTimeout(() => {
                    modal.classList.add('hidden');
                    modal.classList.remove('closing');
                    document.getElementById('nameEditInput').value = '';
                }, 300);
            }
        });
    }

    const nameEditSave = document.getElementById('nameEditSave');
    if (nameEditSave) {
        nameEditSave.addEventListener('click', async () => {
            const input = document.getElementById('nameEditInput');
            const newName = input.value.trim();
            
            if (!newName) {
                toast.error(getI18nValue("toast.globalErrorTitle"), getI18nValue("toast.noGivenNameErrorDesc"));
                return;
            }
            
            if (newName.length > 50) {
                toast.error(getI18nValue("toast.globalErrorTitle"), getI18nValue("toast.noGivenNameErrorDesc"));
                return;
            }
            
            console.log('[Settings] Saving name:', newName);
 
            const success = await updateSettings({ student_firstname: newName });
            
            if (success) {
                localStorage.setItem('student_firstname', newName);
                console.log('[Settings] Name saved to localStorage:', newName);
                

                const welcomeElement = document.getElementById('welcomeGreeting');
                if (welcomeElement) {
                    const greeting = getGreeting();
                    const emoji = getTimeEmoji();
                    welcomeElement.textContent = `${greeting} ${newName} ${emoji}`;
                    console.log('[Settings] Updated welcome greeting');
                }
            }
            
            //close modal
            const modal = document.getElementById('nameEditModal');
            if (modal) {
                modal.classList.add('closing');
                setTimeout(() => {
                    modal.classList.add('hidden');
                    modal.classList.remove('closing');
                    document.getElementById('nameEditInput').value = '';
                }, 300);
            }
        });
    }

    const nameEditInput = document.getElementById('nameEditInput');
    if (nameEditInput) {
        nameEditInput.addEventListener('keypress', async (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const saveBtn = document.getElementById('nameEditSave');
                if (saveBtn) saveBtn.click();
            }
        });
    }

    const nameEditOverlay = document.querySelector('.name-edit-overlay');
    if (nameEditOverlay) {
        nameEditOverlay.addEventListener('click', (e) => {
            if (e.target === nameEditOverlay) {
                const cancelBtn = document.getElementById('nameEditCancel');
                if (cancelBtn) cancelBtn.click();
            }
        });
    }

    //Language selector
    const settingsLanguageItem = document.getElementById('settingsLanguageItem');
    if (settingsLanguageItem) {
        settingsLanguageItem.addEventListener('click', () => {
            console.log('[Settings] Language selector button clicked');
            const modal = document.getElementById('languageSelectorModal');
            if (modal) {
                modal.classList.remove('hidden');
                updateLanguageOptions();
            }
        });
    }

    const languageOptions = document.querySelectorAll('.language-option');
    languageOptions.forEach(option => {
        option.addEventListener('click', async () => {
            const language = option.getAttribute('data-language');
            console.log('[Settings] Language selected:', language);
            
            localStorage.setItem('language', language);
            
            const loaded = await loadLanguage(language);
            //const loaded = false //To disable i18n temporarily if needed
            
            if (loaded) {
                updateLanguageOptions();
                
                //Update the label in settings
                const languageNames = {
                    'fr': 'Français',
                    'es': 'Español',
                    'en': 'English'
                };
                const currentLanguageLabel = document.getElementById('currentLanguageLabel');
                if (currentLanguageLabel) {
                    currentLanguageLabel.textContent = languageNames[language];
                }

                // Update dashboard greeting immediately if on dashboard
                const welcomeElement = document.getElementById('welcomeGreeting');
                const welcomeSubtitle = document.getElementById('welcomeSubtitle');
                const studentFirstName = localStorage.getItem('student_firstname') || null;
                
                if (welcomeElement) {
                    if (studentFirstName) {
                        welcomeElement.textContent = `${getGreeting()} ${studentFirstName} !`;
                    } else {
                        welcomeElement.textContent = `${getGreeting()} !`;
                    }
                }
                
                if (welcomeSubtitle) {
                    welcomeSubtitle.textContent = `${getSubtitle()} ${getTimeEmoji()}`;
                }

                //Save language preference to db
                await updateSettings({ lang: language });

            } else {
                console.error('[Settings] Failed to load language');
                toast.error(getI18nValue("toast.globalErrorTitle"), getI18nValue("toast.changeLanguageFailedDesc"));
                return;
            }
            
            setTimeout(() => {
                const modal = document.getElementById('languageSelectorModal');
                if (modal) {
                    modal.classList.add('closing');
                    setTimeout(() => {
                        modal.classList.add('hidden');
                        modal.classList.remove('closing');
                    }, 300);
                }
            }, 300);
        });
    });

    const languageOverlay = document.querySelector('.language-overlay');
    if (languageOverlay) {
        languageOverlay.addEventListener('click', (e) => {
            if (e.target === languageOverlay) {
                const modal = document.getElementById('languageSelectorModal');
                if (modal) {
                    modal.classList.add('closing');
                    setTimeout(() => {
                        modal.classList.add('hidden');
                        modal.classList.remove('closing');
                    }, 300);
                }
            }
        });
    }

    //Delay selector
    const delayButtons = document.querySelectorAll('.settings-time-option');
    delayButtons.forEach(button => {
        button.addEventListener('click', async (e) => {
            e.preventDefault();
            const selectedTime = button.getAttribute('data-time');
            
            //Remove selected class from all buttons
            delayButtons.forEach(btn => {
                btn.classList.remove('selected');
            });
            
            //Add selected class to clicked button
            button.classList.add('selected');
            console.log(`[Settings] Delay updated to ${selectedTime} minutes`);
            
            await updateSettings({ notification_delay: parseInt(selectedTime) });
        });
    });

    //Settings toggle handlers
    const settingsToggles = document.querySelectorAll('.settings-toggle-input');
    settingsToggles.forEach(toggle => {
        toggle.addEventListener('change', async (e) => {
            const settingsItem = toggle.closest('.settings-item');
            if (!settingsItem) return;
            
            const itemId = settingsItem.id;
            const isChecked = toggle.checked;
            
            let settingName = '';
            let settingValue = isChecked;
            
            //map names
            switch(itemId) {
                case 'settingsNotificationsItem':
                    settingName = 'class_reminder';
                    break;
                case 'settingsMenuDuMidiItem':
                    settingName = 'lunch_menu';
                    break;
                case 'settingsMenuDuSoirItem':
                    settingName = 'evening_menu';
                    break;
                case 'settingsHomeworkNotDoneItem':
                    settingName = 'unfinished_homework_reminder';
                    break;
                case 'settingsPackBackpackItem':
                    settingName = 'get_bag_ready_reminder';
                    break;
                case 'settingsNewGradeItem':
                    settingName = 'new_grade_notification';
                    break;
                case "settingsTelemetryConsentItem":
                    settingName = 'telemetry_consent';
                    break;
                default:
                    console.warn(`Unknown settings item: ${itemId}`);
                    return; 
            }
            
            if (settingName) {
                console.log(`[Settings] ${settingName} toggled to ${settingValue}`);
                await updateSettings({ [settingName]: settingValue });
            }
        });
    });

    //Time Picker Configuration Constants
    const TIME_PICKER_CONFIG = {
        ITEM_HEIGHT: 36,
        MIN_HOUR: 16,
        MAX_HOUR: 23,
        MIN_MINUTE: 0,
        MAX_MINUTE: 59
    };

    //time Picker State
    let currentTimePill = null;
    let currentHours = TIME_PICKER_CONFIG.MIN_HOUR;
    let currentMinutes = TIME_PICKER_CONFIG.MIN_MINUTE;
    let timePickerListeners = {};
    
    window.showTimePicker = function() {
        const modal = document.getElementById('timePickerModal');
        const overlay = document.querySelector('.time-picker-overlay');
        const hoursWheel = document.getElementById('timePickerHours');
        const minutesWheel = document.getElementById('timePickerMinutes');
        const doneBtn = document.getElementById('timePickerDone');
        const cancelBtn = document.getElementById('timePickerCancel');
        
        if (!modal || !overlay || !hoursWheel || !minutesWheel || !doneBtn || !cancelBtn) {
            console.error('[Time Picker] Required modal elements not found !');
            return;
        }
        
        const { ITEM_HEIGHT, MIN_HOUR, MAX_HOUR, MIN_MINUTE, MAX_MINUTE } = TIME_PICKER_CONFIG;
        
        const cleanup = () => {
            hoursWheel.removeEventListener('scroll', timePickerListeners.scroll);
            minutesWheel.removeEventListener('scroll', timePickerListeners.scroll);
            doneBtn.removeEventListener('click', timePickerListeners.done);
            cancelBtn.removeEventListener('click', timePickerListeners.cancel);
            overlay.removeEventListener('click', timePickerListeners.overlayClick);
        };
        
        //clean up old listeners first
        cleanup();
        
        const populateWheel = (wheel, min, max) => {
            wheel.innerHTML = '';
            for (let i = min; i <= max; i++) {
                const item = document.createElement('div');
                item.className = 'time-picker-item';
                item.textContent = String(i).padStart(2, '0');
                item.dataset.value = i;
                wheel.appendChild(item);
            }
        };
        
        populateWheel(hoursWheel, MIN_HOUR, MAX_HOUR);
        populateWheel(minutesWheel, MIN_MINUTE, MAX_MINUTE);
        
        //Set initial scroll positions
        hoursWheel.scrollTop = (currentHours - MIN_HOUR) * ITEM_HEIGHT;
        minutesWheel.scrollTop = currentMinutes * ITEM_HEIGHT;
        
        const updateSelection = () => {
            const hourIdx = Math.round(hoursWheel.scrollTop / ITEM_HEIGHT);
            const minIdx = Math.round(minutesWheel.scrollTop / ITEM_HEIGHT);
            
            hoursWheel.querySelectorAll('.time-picker-item').forEach((item, idx) => {
                item.classList.toggle('selected', idx === hourIdx);
            });
            minutesWheel.querySelectorAll('.time-picker-item').forEach((item, idx) => {
                item.classList.toggle('selected', idx === minIdx);
            });
        };
        
        //Close modal function
        const closeModal = () => {
            console.log('[Time Picker] Closing modal');
            modal.classList.add('closing');
            
            setTimeout(() => {
                modal.classList.add('hidden');
                modal.classList.remove('closing');
                cleanup();
            }, 300);
        };
        
        //Listeners
        timePickerListeners.scroll = updateSelection;
        
        timePickerListeners.done = async () => {
            console.log('[Time Picker] Done button clicked');
            const hourIdx = Math.round(hoursWheel.scrollTop / ITEM_HEIGHT);
            const minIdx = Math.round(minutesWheel.scrollTop / ITEM_HEIGHT);
            
            currentHours = MIN_HOUR + hourIdx;
            currentMinutes = minIdx;
            const formatted = `${currentHours}h${String(currentMinutes).padStart(2, '0')}`;
            const timeFormatHHMM = `${String(currentHours).padStart(2, '0')}:${String(currentMinutes).padStart(2, '0')}`;
            
            console.log(`[Time Picker] Selected time: ${formatted} (${timeFormatHHMM})`);
            
            if (currentTimePill) {
                const settingsItem = currentTimePill.closest('.settings-item');
                const itemId = settingsItem?.id;
                
                let settingName = '';
                
                //Map items
                if (itemId === 'settingsHomeworkNotDoneItem') {
                    settingName = 'unfinished_homework_reminder_time';
                } else if (itemId === 'settingsPackBackpackItem') {
                    settingName = 'get_bag_ready_reminder_time';
                }
                
                console.log(`[Time Picker] Setting ${settingName} to ${timeFormatHHMM}`);
                
                currentTimePill.textContent = formatted;
                
                if (settingName) {
                    await updateSettings({ [settingName]: timeFormatHHMM });
                }
                
                currentTimePill = null;
            }
            
            closeModal();
        };
        
        timePickerListeners.cancel = () => {
            console.log('[Time Picker] Cancel button clicked');
            currentTimePill = null;
            closeModal();
        };
        
        timePickerListeners.overlayClick = (e) => {
            if (e.target === overlay) {
                console.log('[Time Picker] Overlay clicked');
                timePickerListeners.cancel();
            }
        };
        
        hoursWheel.addEventListener('scroll', timePickerListeners.scroll, { passive: true });
        minutesWheel.addEventListener('scroll', timePickerListeners.scroll, { passive: true });
        
        doneBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            timePickerListeners.done();
        });
        
        cancelBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            timePickerListeners.cancel();
        });
        
        overlay.addEventListener('click', timePickerListeners.overlayClick);
        
        //Display and initialize
        modal.classList.remove('hidden');
        updateSelection();
    };
    
    // Time Input Change Handler
    const timeInputs = document.querySelectorAll('.settings-time-input');
    timeInputs.forEach(input => {
        input.addEventListener('change', async function(e) {
            const timeStr = e.target.value;
            if (!timeStr) return;
            
            const [hours, minutes] = timeStr.split(':');
            const formatted = `${hours}h${minutes}`;
            
            // Update the pill text
            const pill = this.parentElement.querySelector('.settings-item-time-pill');
            if (pill) {
                pill.textContent = formatted;
            }
            
            // Determine which setting to update
            const item = this.closest('.settings-item');
            let settingName = '';
            
            if (item.id === 'settingsHomeworkNotDoneItem') {
                settingName = 'unfinished_homework_reminder_time';
            } else if (item.id === 'settingsPackBackpackItem') {
                settingName = 'get_bag_ready_reminder_time';
            }
            
            if (settingName) {
                console.log(`[Settings] Updating ${settingName} to ${timeStr}`);
                await updateSettings({ [settingName]: timeStr });
            }
        });
    });

    //Initialize calendar buton in schedule
    const datePicker = document.getElementById('scheduleDatePicker');

    if (datePicker) {
        datePicker.addEventListener('change', (e) => {
            if (e.target.value) {
                updateScheduleView(new Date(e.target.value));
            }
        });
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