// Configuration
const config = {
    isDevelopment: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1',
    urlSuffix: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? '.html' : ''
};

// URL Handler
function initializeUrlHandling() {
    const buttons = document.querySelectorAll('[data-href]');
    buttons.forEach(button => {
        button.addEventListener('click', () => {
            const baseUrl = button.getAttribute('data-href');
            
            // Validate URL before navigation
            if (baseUrl.startsWith('/') || 
                baseUrl.startsWith('http://') || 
                baseUrl.startsWith('https://')) {
                window.location.href = baseUrl + config.urlSuffix;
            } else {
                console.error('Invalid URL detected:', baseUrl);
            }
        });
    });
}

// Carousel Text Sizing
function adjustFontSize() {
    const carouselTexts = document.querySelectorAll('.carousel-text');
    carouselTexts.forEach(text => {
        const length = text.textContent.length;
        if (window.innerWidth <= 768) {  // Only for mobile screens
            if (length > 30) {
                text.style.fontSize = '18px';
            } else if (length > 20) {
                text.style.fontSize = '21px';
            } else {
                text.style.fontSize = '26px';
            }
        } else {
            text.style.fontSize = ''; // Reset font size for larger screens
        }
    });
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initializeUrlHandling();
    adjustFontSize();
    window.addEventListener('resize', adjustFontSize);

    const discoverBtn = document.getElementById('discoverBtn');
    const comingSoonModal = document.getElementById('comingSoonModal');
    const closeModal = document.querySelector('.close-modal');
    const modalBtn = document.querySelector('.modal-btn');

    if (discoverBtn && comingSoonModal) {
        discoverBtn.addEventListener('click', () => {
            comingSoonModal.classList.add('show');
        });
    }

    if (closeModal && comingSoonModal) {
        closeModal.addEventListener('click', () => {
            comingSoonModal.classList.remove('show');
        });
    }

    if (modalBtn && comingSoonModal) {
        modalBtn.addEventListener('click', () => {
            comingSoonModal.classList.remove('show');
        });
    }

    if (comingSoonModal) {
        comingSoonModal.addEventListener('click', (e) => {
            if (e.target === comingSoonModal) {
                e.target.classList.remove('show');
            }
        });
    }
});

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

function updateSelectedLanguage(lang) {
    // Update selected state
    document.querySelectorAll('.language-option').forEach(option => {
        if (option.dataset.lang === lang) {
            option.classList.add('selected');
        } else {
            option.classList.remove('selected');
        }
    });

    // Update active language display
    const langCode = lang.toUpperCase();
    activeLang.textContent = langCode;
}

// Language switcher functionality
const languageToggle = document.querySelector('.language-toggle');
const languageDropdown = document.querySelector('.language-dropdown');
const languageOptions = document.querySelectorAll('.language-option');
const activeLang = document.querySelector('.active-lang');

if (languageToggle && languageDropdown) {
    languageToggle.addEventListener('click', () => {
        languageDropdown.classList.toggle('show');
    });
}

if (languageOptions) {
    languageOptions.forEach(option => {
        option.addEventListener('click', async () => {
            const lang = option.dataset.lang;
            
            // Change language
            document.documentElement.lang = lang;
            localStorage.setItem('language', lang);
            currentLang = lang;
            
            // Update UI
            await updateLanguage(lang);
            updateSelectedLanguage(lang);
            
            // Hide dropdown with a small delay
            setTimeout(() => {
                if (languageDropdown) {
                    languageDropdown.classList.remove('show');
                }
            }, 150);
        });
    });
}

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('.language-switcher')) {
        languageDropdown.classList.remove('show');
    }
});

// Initialize language on page load
document.addEventListener("DOMContentLoaded", async () => {
    const savedLanguage = localStorage.getItem('language') || 'fr';
    document.documentElement.lang = savedLanguage;
    activeLang.textContent = savedLanguage.toUpperCase();
    updateSelectedLanguage(savedLanguage);
    await updateLanguage(savedLanguage);
});
