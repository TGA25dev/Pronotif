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
    const platformBtns = document.querySelectorAll('.platform-btn');
    const msStoreSteps = document.querySelector('.ms-store-steps');
    const directSteps = document.querySelector('.direct-steps');
    const step2 = document.querySelector('.step-2');
    const storeBtn = document.querySelector('.store-btn');
    const downloadBtn = document.querySelector('.download-exe-btn');
    const progressContainer = document.querySelector('.steps-container');
    const installButton = document.getElementById('installButton');
    const installSteps = document.getElementById('installSteps');

    updateDeviceSpecificContent();

    // Platform buttons initialization
    if (platformBtns) {
        platformBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault(); // Prevent default action
                platformBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                
                if (btn.classList.contains('ms-store-btn')) {
                    //window.open('ms-windows-store://pdp/?productid=9999999', '_blank');
                } else if (btn.classList.contains('direct-btn')) {
                    warningModal.style.display = 'block';
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

    // Installation PWA
    if (installButton) {
        installButton.addEventListener('click', async () => {
            if (!deferredPrompt) {
                alert('Installation non disponible pour le moment. Assurez-vous que l\'application n\'est pas déja  installée.');
                return;
            }

            try {
                deferredPrompt.prompt();
                const choiceResult = await deferredPrompt.userChoice;
                if (choiceResult.outcome === 'accepted') {
                    console.log('[PWA] Installation accepted !');
                }
                deferredPrompt = null;
            } catch (error) {
                console.error('[PWA] Installation error :', error);
                alert('Une erreur est survenue lors de l\'installation.');
            }
        });
    }

    updateDeviceSpecificContent();

    if (window.innerWidth <= 768) {
        const steps = document.querySelectorAll('.step');
        
        steps.forEach(step => {
            step.addEventListener('click', () => {
                const nextStep = step.nextElementSibling;
                if (nextStep && nextStep.classList.contains('step')) {
                    nextStep.scrollIntoView({ behavior: 'smooth' });
                }
            });
        });
    }

    const directBtn = document.querySelector('.direct-btn');
    const warningModal = document.getElementById('warningModal');
    const closeBtn = document.querySelector('.close-btn');
    const confirmDownload = document.getElementById('confirmDownload');

    function showModal() {
        const scrollY = window.scrollY;
        warningModal.style.display = 'block';
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
            window.location.href = "https://github.com/TGA25dev/Pronotif/releases/latest/download/Pronotif.Setup.v0.5.1.zip";
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

// Language handeling

const translations = {
    // French
    'fr': {
        'title': "Installer Pronot'if",
        'subtitle': "Vous y êtes presque !",
        'setup': "Pronot'if Setup",
        'setup_desc': "Le logiciel sur PC pour vous inscrire sur Pronot'if.",
        'store': "Microsoft Store",
        'store_desc': "Installation simple et sécurisée via le Store",
        'direct': "Téléchargement Direct",
        'direct_desc': "Téléchargez directement le fichier d'installation",
        'step2': "Pronot'if Mobile",
        'step2_desc': "Une fois la configuration effectuée, installez l'application mobile.",
        'platform_btn_badge': "Prochainement...",
        'toggle_btn': "Change language",
        'back_home': "← Retour à l'accueil",

        // Ios
        'ios_step1': "Appuyez sur l'icône de partage",
        'ios_step2': "Sélectionnez \"Sur l'écran d'accueil\"",
        'ios_step3': "Appuyez sur \"Ajouter\"",
        'ios_step4': "C'est tout ! ✨",
        'ios_final': "Ouvrez ensuite l'appli 'Pronot'if'.",

        // Android
        'android_step1': "Appuyez sur le bouton \"Installer maintenant\" ci-dessous",
        'android_step2': "Dans la fenêtre qui s'affiche, appuyez sur \"Installer\"",
        'android_step3': "C'est tout ! ✨",
        'android_final': "Ouvrez ensuite l'appli 'Pronot'if'.",
        'install_button': "Installer maintenant",

        // Pc
        'device-info': "L'application est conçue pour les appareils mobiles.",
        'device-info2': "Revenez sur cette page depuis votre téléphone !",

        // Success message
        'success-message': "Installation réussie !",
        'success-message2': "Merci d'avoir installé l'application ! 🎉",
        'success-message3': "Vous pouvez maintenant fermer cette fenêtre.",

        // Warning message
        'warning_title': "Attention",
        'warning_message': "L'application peut être signalée comme suspecte par votre antivirus car elle n'est pas encore certifiée. C'est normal et vous pouvez l'installer en toute confiance.",
        'warning_message2': "Le code source est disponible publiquement sur GitHub",
        'confirm_btn': "D'accord, je comprends"
    },

    // English
    'en': {
        'title': "Install Pronot'if",
        'subtitle': "You're almost there!",
        'setup': "Pronot'if Setup",
        'setup_desc': "The PC software to register for Pronot'if.",
        'store': "Microsoft Store",
        'store_desc': "Simple and secure installation via the Store",
        'direct': "Direct Download",
        'direct_desc': "Download the installation file directly",
        'step2': "Pronot'if Mobile",
        'step2_desc': "Once setup is complete, install the mobile app.",
        'platform_btn_badge': "Coming soon...",
        'toggle_btn': "Changer la langue",
        'back_home': "← Back to home",

        // Ios
        'ios_step1': "Tap the share icon",
        'ios_step2': "Select \"Add to Home Screen\"",
        'ios_step3': "Tap \"Add\"",
        'ios_step4': "That's it! ✨",
        'ios_final': "Then open the 'Pronot'if' app.",

        // Android
        'android_step1': "Tap the \"Install now\" button below",
        'android_step2': "In the popup that appears, tap \"Install\"",
        'android_step3': "That's it! ✨",
        'android_final': "Then open the 'Pronot'if' app.",
        'install_button': "Install now",

        // Pc
        'device-info': "The app is designed for mobile devices.",
        'device-info2': "Return to this page from your phone!",

        // Success message
        'success-message': "Installation successful!",
        'success-message2': "Thank you for installing the app! 🎉",
        'success-message3': "You can now close this window.",

        // Warning message
        'warning_title': "Warning",
        'warning_message': "The app may be flagged as suspicious by your antivirus because it is not yet certified. This is normal and you can safely install it.",
        'warning_message2': "The source code is publicly available on GitHub",
        'confirm_btn': "I understand"
    }
};

let currentLang = localStorage.getItem('lang') || 'fr';

document.addEventListener("DOMContentLoaded", () => {
    updateLanguage();
});

function toggleLanguage() {
    currentLang = currentLang === 'fr' ? 'en' : 'fr';
    localStorage.setItem('lang', currentLang);
    updateLanguage();
}

function updateLanguage() {
    const lang = translations[currentLang];
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (lang[key]) {
            el.innerText = lang[key];
        }
    });
}