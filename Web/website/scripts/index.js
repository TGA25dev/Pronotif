//Language Configuration
let translations = {};
let currentLang = localStorage.getItem('language') || getDefaultLang();

//Get browser language, fallback to fr
function getDefaultLang() {
    const navLang = navigator.language || navigator.userLanguage || 'fr';
    console.log("Browser language detected:", navLang);
    const shortLang = navLang.split('-')[0].toLowerCase();
    // Supported languages
    const supported = ['fr', 'en', 'es'];
    return supported.includes(shortLang) ? shortLang : 'fr';
}
async function loadTranslations(lang) {
    try {
        const response = await fetch(`langs/${lang}.json`);
        if (!response.ok) throw new Error(`Failed to load ${lang} translations`);
        translations[lang] = await response.json();
        return translations[lang];
    } catch (error) {
        console.error('Error loading translations:', error);
        return null;
    }
}

async function applyTranslations(lang) {
    if (!translations[lang]) {
        await loadTranslations(lang);
    }
    
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (translations[lang] && translations[lang][key]) {
            el.textContent = translations[lang][key];
        }
    });
}

function updateLanguageUI(lang) {
    document.querySelector('.lang-code').textContent = lang.toUpperCase();
    
    document.querySelectorAll('.lang-option').forEach(option => {
        option.classList.toggle('active', option.dataset.lang === lang);
    });
}

function initLanguageSwitcher() {
    const langToggle = document.getElementById('langToggle');
    const langDropdown = document.getElementById('langDropdown');
    const langOptions = document.querySelectorAll('.lang-option');

    if (!langToggle || !langDropdown) return;

    //Toggle dropdown
    langToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        langDropdown.classList.toggle('show');
    });

    langOptions.forEach(option => {
        option.addEventListener('click', async () => {
            const lang = option.dataset.lang;
            currentLang = lang;
            localStorage.setItem('language', lang);
            
            document.documentElement.lang = lang;
            updateLanguageUI(lang);
            await applyTranslations(lang);
            
            langDropdown.classList.remove('show');
        });
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.language-switcher')) {
            langDropdown.classList.remove('show');
        }
    });
}

let deferredPrompt = null;

const isAndroid = () => /Android/i.test(navigator.userAgent);
const isIos = () => /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
const isDesktop = () => !isAndroid() && !isIos();

window.addEventListener('beforeinstallprompt', (e) => {
    console.log('[PWA] BeforeInstallPrompt captured !');
    e.preventDefault();
    deferredPrompt = e;
    renderInstallSection();
});

window.addEventListener('appinstalled', () => {
    console.log('[PWA] App installed');
    const container = document.getElementById('install-content');
    if (container) {
        container.innerHTML = `
            <div class="success-message" style="text-align: center; padding: 2rem;">
                <h3 data-i18n="success-message" style="color: var(--primary-teal); margin-bottom: 1rem; font-size: 1.8rem;">Installation réussie !</h3>
                <p data-i18n="success-message2" style="font-size: 1.2rem; color: var(--text-dark);">Merci d'avoir installé l'application ! 🎉</p>
            </div>
        `;
        applyTranslations(currentLang);
    }
});

function renderInstallSection() {
    const container = document.getElementById('install-content');
    if (!container) return;

    console.log('Device detection:', {
        isIos: isIos(),
        isAndroid: isAndroid(),
        isDesktop: isDesktop(),
        deferredPrompt: !!deferredPrompt
    });

    let html = '';

    if (isAndroid()) {
        html = `
            <div class="install-steps">
                <div class="step">
                    <span class="step-number">1</span>
                    <p data-i18n="android_step1">Appuyez sur le bouton "Installer maintenant" ci-dessous</p>
                </div>
                <div class="step">
                    <span class="step-number">2</span>
                    <p data-i18n="android_step2">Dans la fenêtre qui s'affiche, appuyez sur "Installer"</p>
                </div>
                <div class="step">
                    <span class="step-number">3</span>
                    <p data-i18n="android_step3">C'est tout ! ✨</p>
                </div>
            </div>
            ${deferredPrompt ? `<button id="pwa-install-btn" class="btn btn-primary install-action-btn" data-i18n="install_button">Installer maintenant</button>` : ''}
        `;
    } else if (isIos()) {
        html = `
            <div class="install-steps">
                <div class="step">
                    <span class="step-number">1</span>
                    <p>
                        Appuyez sur <strong>•••</strong> puis Partager
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-left: 4px; color: var(--primary-teal);"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"></path><polyline points="16 6 12 2 8 6"></polyline><line x1="12" y1="2" x2="12" y2="15"></line></svg>
                    </p>
                </div>
                <div class="step">
                    <span class="step-number">2</span>
                    <p>Sélectionnez "Sur l'écran d'accueil"</p>
                </div>
                <div class="step">
                    <span class="step-number">3</span>
                    <p>Activez "Ouvrir comme app web" puis cliquez sur "Ajouter"</p>
                </div>
            </div>
            <p class="ios-note" data-i18n="ios_final" style="text-align: center; margin-top: 1rem; color: var(--text-gray);">Ouvrez ensuite l'appli 'Pronot'if'.</p>
        `;
    } else {
        // Desktop
        html = `
            <div class="desktop-install-message">
                <div class="qr-container">
                    <img src="./assets/qr-code.svg" alt="QRCode" class="qr-code">
                </div>
                <p class="qr-caption">Scannez pour installer l'app</p>
                <p class="qr-subcaption">Ouvrez l'appareil photo de votre téléphone</p>
            </div>
        `;
    }

    container.innerHTML = html;
    
    //Reapply translations for the new content
    applyTranslations(currentLang);

    const installBtn = document.getElementById('pwa-install-btn');
    if (installBtn && deferredPrompt) {
        installBtn.addEventListener('click', async () => {
            deferredPrompt.prompt();
            const { outcome } = await deferredPrompt.userChoice;
            console.log(`User response to the install prompt: ${outcome}`);
            deferredPrompt = null;
            renderInstallSection();
        });
    }
}

//Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    document.documentElement.lang = currentLang;
    updateLanguageUI(currentLang);
    await applyTranslations(currentLang);
    initLanguageSwitcher();
    renderInstallSection();

    //Burger Menu Logic
    const burgerMenu = document.querySelector('.burger-menu');
    const navLinks = document.querySelector('.nav-links');
    const links = document.querySelectorAll('.nav-links a');

    if (burgerMenu && navLinks) {
        burgerMenu.addEventListener('click', () => {
            burgerMenu.classList.toggle('active');
            navLinks.classList.toggle('active');
        });

        //Close menu when a link is clicked
        links.forEach(link => {
            link.addEventListener('click', () => {
                burgerMenu.classList.remove('active');
                navLinks.classList.remove('active');
            });
        });

        // Close menu when clicking outside
        document.addEventListener('click', (e) => {
            if (!burgerMenu.contains(e.target) && !navLinks.contains(e.target)) {
                burgerMenu.classList.remove('active');
                navLinks.classList.remove('active');
            }
        });
    }

    const installBtns = document.querySelectorAll('[data-i18n="btn-install"], [data-i18n="header-install"]');
    const githubBtns = document.querySelectorAll('[data-i18n="btn-github"]');

    //Navbar Scroll Effect
    const header = document.querySelector('.header');
    if (header) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                header.classList.add('scrolled');
            } else {
                header.classList.remove('scrolled');
            }
        });
    }

    const parallaxElements = document.querySelectorAll('.emoji-wrapper, .floating-shape');
    if (parallaxElements.length > 0) {
        window.addEventListener('scroll', () => {
            const scrollY = window.scrollY;
            
            parallaxElements.forEach(element => {
                const speed = parseFloat(element.getAttribute('data-speed') || 0.05);
                const yPos = scrollY * speed;
                element.style.transform = `translateY(${yPos}px)`;
            });
        });
    }

    installBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const installSection = document.getElementById('install');
            if (installSection) {
                installSection.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });

    githubBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            window.open('https://github.com/TGA25dev/Pronotif', '_blank');
        });
    });

    //Scroll Animation for Mockups
    const mockupLeft = document.querySelector('.mockup-left');
    const mockupRight = document.querySelector('.mockup-right');
    const mockupCenter = document.querySelector('.mockup-center');

    if (mockupLeft && mockupRight && mockupCenter) {
        window.addEventListener('scroll', () => {
            const scrollY = window.scrollY;
            //Start animation immediately and finish by 500px scroll
            const progress = Math.min(Math.max(scrollY / 500, 0), 1);
            
            const ease = t => t * (2 - t); //Ease out quad
            const easedProgress = ease(progress);

            //Calculate values based on eased progress
            const translateX = 100 + (60 * easedProgress);
            
            //RotateY: 15deg > 5deg
            const rotateY = 15 - (10 * easedProgress);
            
            //RotateZ: 2deg > 0deg
            const rotateZ = 2 - (2 * easedProgress);

            // Left Phone
            mockupLeft.style.transform = `translateX(-${translateX}%) translateZ(-50px) rotateY(${rotateY}deg) rotateZ(-${rotateZ}deg)`;
            
            // Right Phone
            mockupRight.style.transform = `translateX(${translateX}%) translateZ(-50px) rotateY(-${rotateY}deg) rotateZ(${rotateZ}deg)`;
            
        });
    }

    //Horizontal Scroll Animation for Features
    const featuresSection = document.querySelector('.features-scroll-section');
    const featuresWrapper = document.querySelector('.features-scroll-wrapper');
    const featuresContainer = document.querySelector('.features-container');

    if (featuresSection && featuresWrapper && featuresContainer) {
        
        function getScrollRange() {
            const scrollWidth = featuresWrapper.scrollWidth;
            const viewportWidth = featuresContainer.clientWidth;
            const style = window.getComputedStyle(featuresContainer);
            const paddingLeft = parseFloat(style.paddingLeft) || 0;
            return Math.max(0, scrollWidth + paddingLeft - viewportWidth);
        }

        function initScroll() {
            const maxTranslate = getScrollRange();
            featuresSection.style.height = `${maxTranslate + window.innerHeight}px`;
        }

        window.addEventListener('load', initScroll);
        window.addEventListener('resize', initScroll);
        initScroll();

        window.addEventListener('scroll', () => {
            const sectionRect = featuresSection.getBoundingClientRect();
            const maxTranslate = getScrollRange();
            const scrollDistance = -sectionRect.top;
            
            if (scrollDistance <= 0) {
                featuresWrapper.style.transform = 'translateX(0)';
            } else if (scrollDistance < maxTranslate) {
                featuresWrapper.style.transform = `translateX(-${scrollDistance}px)`;
            } else {
                featuresWrapper.style.transform = `translateX(-${maxTranslate}px)`;
            }
        });
    }
});