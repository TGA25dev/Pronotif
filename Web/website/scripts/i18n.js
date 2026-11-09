const supportedLanguages = ['fr', 'en', 'es'];
const translations = {};

function getNestedTranslation(value, keyPath) {
    return keyPath.split('.').reduce((current, key) => current?.[key], value);
}

function getLanguageFromPath() {
    const pathLanguage = window.location.pathname.split('/')[1]?.toLowerCase();
    return supportedLanguages.includes(pathLanguage) ? pathLanguage : null;
}

function getDefaultLanguage() {
    const browserLanguage = navigator.language || navigator.userLanguage || 'fr';
    const language = browserLanguage.split('-')[0].toLowerCase();
    return supportedLanguages.includes(language) ? language : 'fr';
}

async function loadTranslations(language) {
    if (translations[language]) return translations[language];

    const response = await fetch(`/langs/${language}.json`, { cache: 'no-store' });
    if (!response.ok) {
        throw new Error(`Failed to load ${language} translations (${response.status})`);
    }

    translations[language] = await response.json();
    return translations[language];
}

function translateAttribute(attribute, languageData) {
    document.querySelectorAll(`[data-i18n-${attribute}]`).forEach(element => {
        const key = element.getAttribute(`data-i18n-${attribute}`);
        const value = getNestedTranslation(languageData, key);
        if (value) element.setAttribute(attribute, value);
    });
}

function applyTranslations(language) {
    const languageData = translations[language];
    if (!languageData) return;

    document.querySelectorAll('[data-i18n-html]').forEach(element => {
        const key = element.getAttribute('data-i18n-html');
        const value = getNestedTranslation(languageData, key);
        if (value) element.innerHTML = value;
    });

    document.querySelectorAll('[data-i18n]').forEach(element => {
        if (element.hasAttribute('data-i18n-html')) return;
        const key = element.getAttribute('data-i18n');
        const value = getNestedTranslation(languageData, key);
        if (value) element.textContent = value;
    });

    translateAttribute('placeholder', languageData);
    translateAttribute('title', languageData);
    translateAttribute('aria-label', languageData);
    translateAttribute('content', languageData);
    document.documentElement.lang = language;
    document.title = getNestedTranslation(languageData, 'page-title') || document.title;
}

async function setLanguage(language) {
    if (!supportedLanguages.includes(language)) return;

    try {
        await loadTranslations(language);
        localStorage.setItem('language', language);
        window.currentLang = language;
        applyTranslations(language);
    } catch (error) {
        console.error('[i18n] Unable to load translations:', error);
    }
}

function initLanguageSwitcher() {
    const toggle = document.getElementById('langToggle');
    const dropdown = document.getElementById('langDropdown');
    if (!toggle || !dropdown) return;

    toggle.addEventListener('click', event => {
        event.stopPropagation();
        dropdown.classList.toggle('show');
    });

    dropdown.querySelectorAll('.lang-option').forEach(option => {
        option.addEventListener('click', () => {
            const language = option.dataset.lang;
            const destination = language === 'fr' ? '/' : `/${language}`;
            window.location.assign(destination);
        });
    });

    document.addEventListener('click', event => {
        if (!event.target.closest('.language-switcher')) {
            dropdown.classList.remove('show');
        }
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    const language = getLanguageFromPath() || localStorage.getItem('language') || getDefaultLanguage();
    window.currentLang = language;
    await setLanguage(language);
    document.querySelector('.lang-code').textContent = language.toUpperCase();
    document.querySelectorAll('.lang-option').forEach(option => {
        option.classList.toggle('active', option.dataset.lang === language);
    });
    initLanguageSwitcher();
    window.dispatchEvent(new Event('i18n-ready'));
});

window.applyTranslations = applyTranslations;
