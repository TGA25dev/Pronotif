const isAndroid = () => {
    return /Android/i.test(navigator.userAgent);
};

const isIos = () => {
    return /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
};

const isDesktop = () => {
    return !isAndroid() && !isIos();
};

// Variables globales
let deferredPrompt = null;

const updateDeviceSpecificContent = () => {
    const iosSteps = document.getElementById('ios-steps');
    const androidSteps = document.getElementById('android-steps');
    const installSteps = document.getElementById('installSteps');
    const installButton = document.getElementById('installButton');

    if (!installSteps) return;

    console.log('Device detection:', {
        isIos: isIos(),
        isAndroid: isAndroid(),
        isDesktop: isDesktop(),
        deferredPrompt: !!deferredPrompt
    });

    // Always hide the install button first
    if (installButton) {
        installButton.style.display = 'none';
    }

    // Reset display
    if (iosSteps) iosSteps.style.display = 'none';
    if (androidSteps) iosSteps.style.display = 'none';

    if (isIos()) {
        if (iosSteps) {
            iosSteps.style.display = 'block';
            installSteps.style.display = 'block';
        }
    } else if (isAndroid()) {
        if (androidSteps) {
            androidSteps.style.display = 'block';
            installSteps.style.display = 'block';
            // Only show install button if we have the deferredPrompt
            if (installButton && deferredPrompt) {
                installButton.style.display = 'block';
            }
        }
    } else if (isDesktop()) {
        installSteps.innerHTML = `
            <div class="pc-message">
                <span class="device-icon">💻</span>
                <p data-i18n="device-info">L'application est conçue pour les appareils mobiles.</p>
                <p data-i18n="device-info2" class="secondary-text">Revenez sur cette page depuis votre téléphone !</p>
            </div>
        `;
    }
};

window.addEventListener('beforeinstallprompt', (evt) => {
    console.log('[PWA] BeforeInstallPrompt captured !');
    evt.preventDefault();
    deferredPrompt = evt;

    updateDeviceSpecificContent();
});

document.addEventListener('DOMContentLoaded', () => {
    // Initialize beta code overlay
    initBetaCodeOverlay();
    
    // Initialize URL handling from shared config
    config.initializeUrlHandling();
    
    // Get modal element and hide it explicitly on page load
    const warningModal = document.getElementById('warningModal');
    if (warningModal) {
        warningModal.style.display = 'none';
    }
    
    const platformBtns = document.querySelectorAll('.platform-btn');
    const directSteps = document.querySelector('.direct-steps');
    const step2 = document.querySelector('.step-2');
    const downloadBtn = document.querySelector('.download-exe-btn');
    const progressContainer = document.querySelector('.steps-container');
    const installButton = document.getElementById('installButton');
    const installSteps = document.getElementById('installSteps');
    const closeBtn = document.querySelector('.close-btn');
    const confirmDownload = document.getElementById('confirmDownload');
    const directBtn = document.querySelector('.direct-btn');

    updateDeviceSpecificContent();

    // Query parameters
    const urlParams = new URLSearchParams(window.location.search);
    const step2Param = urlParams.get('step2');

    if (step2Param !== null) {
        // Trigger
        const progressContainer = document.querySelector('.steps-container');
        const step2 = document.querySelector('.step-2');
        const step1 = document.querySelector('.step-1');
    
        if (progressContainer && step2 && step1) {
            // Deactivate step 1 and activate step 2
            step1.classList.remove('active');
            step2.classList.add('active');
            progressContainer.classList.add('progress-active');
    
            // Scroll with offset
            setTimeout(() => {
                const offset = 20;
                const elementPosition = step2.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - offset;
                
                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });
                
                console.log('Scrolling to step 2 with offset...');
            }, 100); // Delay to ensure the class is added before scrolling
        }
    }

    // Platform buttons initialization
    if (platformBtns) {
        platformBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault(); // Prevent default action
                platformBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                
                if (btn.classList.contains('direct-btn')) {
                    showModal(); // Use function to show modal
                }

                if (progressContainer && step2) {
                    setTimeout(() => {
                        progressContainer.classList.add('progress-active');
                        step2.classList.add('active');
                    }, 500);
                }
            });
        });
    }

    function showModal() {
        const scrollY = window.scrollY;
        warningModal.style.display = 'flex';
        document.body.classList.add('modal-open');
        document.body.style.position = 'fixed';
        document.body.style.top = `-${scrollY}px`;
        document.body.style.width = '100%';
    }

    function hideModal() {
        const scrollY = document.body.style.top;
        document.body.style.position = '';
        document.body.style.top = '';
        document.body.style.width = '';
        window.scrollTo(0, parseInt(scrollY || '0') * -1);
        document.body.classList.remove('modal-open');
        warningModal.style.display = 'none';
    }

    if (directBtn) {
        directBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            showModal();
        });
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', (e) => {
            e.preventDefault();
            hideModal();
        });
    }

    if (confirmDownload) {
        confirmDownload.addEventListener('click', () => {
            // Fetch latest version from GitHub API
            fetch('https://api.github.com/repos/TGA25dev/Pronotif/releases/latest')
                .then(response => {
                    if (!response.ok) throw new Error('Network response was not ok');
                    return response.json();
                })
                .then(data => {
                    const latestVersion = data.tag_name.replace('v', ''); // Remove 'v' prefix
                    window.location.href = `https://github.com/TGA25dev/Pronotif/releases/latest/download/Pronotif.Setup.v${latestVersion}.zip`;
                    console.log('Redirecting to latest version:', latestVersion);
                })
                .catch(error => {
                    console.error('Error fetching latest version:', error);
                    // Fallback if API request fail
                    window.location.href = "https://github.com/TGA25dev/Pronotif/releases/latest/download/Pronotif.Setup.v0.8.1.zip";
                    console.log('Redirecting to hardcoded version: 0.8.1');
                });
            hideModal();
        });
    }

    window.addEventListener('click', (event) => {
        if (event.target === warningModal) {
            hideModal();
        }
    });

    // Prevent scrolling on modal background when touching
    warningModal.addEventListener('touchmove', (e) => {
        e.preventDefault();
    }, { passive: false });
});

console.log('[PWA] Starting PWA events');

window.addEventListener('appinstalled', (evt) => {
    const androidSteps = document.getElementById('android-steps');
    const installTitle = document.querySelector('.install-steps h2');
    if (androidSteps && installTitle) {
        installTitle.style.display = 'none';
        androidSteps.innerHTML = `
            <div class="success-message">
                <h2 data-i18n="success-message">Installation réussie !</h2>
                <p data-i18n="success-message2">Merci d'avoir installé l'application ! 🎉</p>
                <p data-i18n="success-message3" class="secondary-text">Vous pouvez maintenant fermer cette fenêtre.</p>
            </div>
        `;
    }
});

// Service Worker
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('scripts/sw.js')
            .then((registration) => {
                console.log('Server worker succesfully saved : ', registration);
                // Check if the service worker is active
                if (registration.active) {
                    console.log("ServiceWorker is active");
                } else {
                    console.log("ServiceWorker is not active");
                }
            })
            .catch(error => console.error('ServiceWorker error:', error));
    });
}

// Language handling
let translations = {};
let currentLang = localStorage.getItem('language') || 'fr'; // Changed from 'lang' to 'language'

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

// Remove old toggleLanguage function since we're using the dropdown now

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

// Beta code functionality
function initBetaCodeOverlay() {
    const betaCodeOverlay = document.getElementById('betaCodeOverlay');
    const betaCodeInput = document.getElementById('betaCodeInput');
    const betaCodeSubmit = document.getElementById('betaCodeSubmit');
    const betaCodeError = document.getElementById('betaCodeError');
    const betaRequestBtn = document.getElementById('betaRequestBtn');
    const mainContent = document.querySelector('.bento-container');
    const languageSwitcher = document.querySelector('.language-switcher');

    // Check if user has already entered a valid code
    const hasValidCode = localStorage.getItem('pronotif_beta_access') === 'true';

    if (hasValidCode) {
        betaCodeOverlay.classList.add('hidden');
        mainContent.style.display = 'block';
        languageSwitcher.style.display = 'block';
    } else {
        mainContent.style.display = 'none';
        languageSwitcher.style.display = 'none';
    }

    // Beta request button handler
    if (betaRequestBtn) {
        betaRequestBtn.addEventListener('click', function () {
            showBetaRequestModal();
        });
    }

    // Format the beta code
    betaCodeInput.addEventListener('input', function () {
        let code = this.value.replace(/[^A-Za-z0-9]/g, '').toUpperCase();

        // Group the code into chunks of 3 characters
        if (code.length > 3) {
            code = code.replace(/(.{3})(?=.)/g, '$1-');
        }

        this.value = code;
        betaCodeError.classList.remove('visible');
    });

    betaCodeSubmit.addEventListener('click', function () {
        validateBetaCode();
    });

    betaCodeInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            validateBetaCode();
        }
    });

    async function validateBetaCode() {
        let code = betaCodeInput.value.trim();

        // Ensure the code is formatted as XXX-XXX-XXX
        code = code.replace(/[^A-Za-z0-9]/g, '').toUpperCase();
        if (code.length === 9) {
            code = code.replace(/(.{3})(.{3})(.{3})/, '$1-$2-$3');
        }

        // Validate the format strictly
        if (!/^[A-Z0-9]{3}-[A-Z0-9]{3}-[A-Z0-9]{3}$/.test(code)) {
            betaCodeError.textContent = "Le code doit être au format XXX-XXX-XXX.";
            betaCodeError.classList.add('visible');
            betaCodeInput.focus();
            return;
        }

        try {
            const response = await fetch('https://api.pronotif.tech/v1/beta/verify', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ code }),
            });

            const result = await response.json();

            if (response.ok && result.success) {
                localStorage.setItem('pronotif_beta_access', 'true');
                betaCodeOverlay.classList.add('hidden');

                setTimeout(() => {
                    mainContent.style.display = 'block';
                    languageSwitcher.style.display = 'block';
                }, 500);
            } else {
                // Map API error messages to French
                const errorMessages = {
                    "Invalid or expired code": "Code invalide ou expiré.",
                    "Code required": "Un code est requis.",
                    "Content-Type must be application/json": "Le type de contenu doit être application/json.",
                    "Missing request data": "Données de requête manquantes.",
                    "Invalid code format": "Format de code invalide.",
                };

                betaCodeError.textContent = errorMessages[result.error] || "Une erreur est survenue. Veuillez réessayer.";
                betaCodeError.classList.add('visible');
                betaCodeInput.focus();
            }
        } catch (error) {
            console.error('Error validating beta code:', error);
            betaCodeError.textContent = "Erreur de connexion. Veuillez réessayer.";
            betaCodeError.classList.add('visible');
        }
    }
}

// Beta Request Modal
function showBetaRequestModal() {
    const modal = document.getElementById('betaRequestModal');
    const form = document.getElementById('betaRequestForm');
    const success = document.getElementById('betaRequestSuccess');
    
    // Reset modal state
    form.style.display = 'block';
    success.style.display = 'none';
    
    // Clear form
    document.getElementById('betaForm').reset();
    
    // Show modal
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    
    // Focus first input
    setTimeout(() => {
        document.getElementById('betaName').focus();
    }, 100);
}

function hideBetaRequestModal() {
    const modal = document.getElementById('betaRequestModal');
    modal.style.display = 'none';
    document.body.style.overflow = '';
}


document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('betaRequestModal');
    const closeBtn = modal.querySelector('.beta-request-close-btn');
    const cancelBtn = modal.querySelector('.beta-cancel-btn');
    const form = document.getElementById('betaForm');
    const successCloseBtn = document.getElementById('betaSuccessClose');
    
    // Close button handlers
    closeBtn.addEventListener('click', hideBetaRequestModal);
    cancelBtn.addEventListener('click', hideBetaRequestModal);
    successCloseBtn.addEventListener('click', hideBetaRequestModal);
    
    // Close on background click
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            hideBetaRequestModal();
        }
    });
    
    // Form submission
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(form);
        const data = {
            name: formData.get('name').trim(),
            email: formData.get('email').trim(),
            reason: formData.get('reason').trim()
        };
        
        // Field validation
        if (!data.name || !data.email) {
            alert('Veuillez remplir tous les champs obligatoires');
            return;
        }
        
        // Email validation
        const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        if (!emailRegex.test(data.email)) {
            alert('Veuillez entrer une adresse e-mail valide');
            return;
        }
        
        // Length validation
        if (data.name.length > 100) {
            alert('Le nom est trop long (maximum 100 caractères)');
            return;
        }
        
        if (data.reason.length > 500) {
            alert('La raison est trop longue (maximum 500 caractères)');
            return;
        }
        
        // Disable submit button
        const submitBtn = form.querySelector('.beta-submit-btn');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Envoi en cours...';
        
        // Send request to backend API
        fetch('https://api.pronotif.tech/v1/beta/request', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                console.log('Beta request submitted successfully:', data);
                
                // Show success message
                document.getElementById('betaRequestForm').style.display = 'none';
                document.getElementById('betaRequestSuccess').style.display = 'block';
                
                // Reset form for next time
                form.reset();
            } else {
                // Handle backend errors
                alert(result.error || 'Une erreur est survenue lors de l\'envoi de votre demande');
                console.error('Backend error:', result.error);
            }
        })
        .catch(error => {
            console.error('Network error:', error);
            alert('Erreur de connexion. Veuillez réessayer plus tard.');
        })
        .finally(() => {
            // Re-enable submit button
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        });
    });
    
    // Prevent modal content from closing when clicked
    modal.querySelector('.beta-request-modal-content').addEventListener('click', function(e) {
        e.stopPropagation();
    });
});