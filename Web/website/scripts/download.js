//Redirect to root
if (window.location.pathname.endsWith('/download.html')) {
    window.location.replace('/Web/website/');
}

else if (window.location.pathname.endsWith('/download')) {
    window.location.replace('/');

};


// Language handling
let translations = {};
let currentLang = localStorage.getItem('language') || 'fr';

async function loadTranslations(lang) {
    try {
        const response = await fetch(`langs/${lang}.json`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        translations[lang] = await response.json();
        return translations[lang];
    } catch (error) {
        console.error('Error loading translations:', error);
        return null;
    }
}

async function updateLanguage(lang) {
    if (!translations[lang]) {
        const newTranslations = await loadTranslations(lang);
        if (!newTranslations) return;
    }
    
    const currentTranslations = translations[lang];
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (currentTranslations && currentTranslations[key]) {
            if (el.tagName.toLowerCase() === 'input' && el.type === 'submit') {
                el.value = currentTranslations[key];
            } else {
                el.textContent = currentTranslations[key];
            }
        }
    });
}

// Language switcher functionality
const languageToggle = document.querySelector('.language-toggle');
const languageDropdown = document.querySelector('.language-dropdown');
const languageOptions = document.querySelectorAll('.language-option');
const activeLang = document.querySelector('.active-lang');

function updateSelectedLanguage(lang) {
    document.querySelectorAll('.language-option').forEach(option => {
        if (option.dataset.lang === lang) {
            option.classList.add('selected');
        } else {
            option.classList.remove('selected');
        }
    });
    activeLang.textContent = lang.toUpperCase();
}

languageToggle?.addEventListener('click', () => {
    languageDropdown.classList.toggle('show');
});

languageOptions?.forEach(option => {
    option.addEventListener('click', async () => {
        const lang = option.dataset.lang;
        
        document.documentElement.lang = lang;
        localStorage.setItem('language', lang);
        currentLang = lang;
        
        await updateLanguage(lang);
        updateSelectedLanguage(lang);
        
        setTimeout(() => {
            languageDropdown.classList.remove('show');
        }, 150);
    });
});

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('.language-switcher')) {
        languageDropdown?.classList.remove('show');
    }
});

// Initialize language on page load
document.addEventListener("DOMContentLoaded", async () => {
    const savedLanguage = localStorage.getItem('language') || 'fr';
    document.documentElement.lang = savedLanguage;
    if (activeLang) {
        activeLang.textContent = savedLanguage.toUpperCase();
        updateSelectedLanguage(savedLanguage);
    }
    await updateLanguage(savedLanguage);

});