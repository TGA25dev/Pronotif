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

document.addEventListener('DOMContentLoaded', () => {
    // Sélection des éléments DOM
    const platformBtns = document.querySelectorAll('.platform-btn');
    const msStoreSteps = document.querySelector('.ms-store-steps');
    const directSteps = document.querySelector('.direct-steps');
    const step2 = document.querySelector('.step-2');
    const storeBtn = document.querySelector('.store-btn');
    const downloadBtn = document.querySelector('.download-exe-btn');
    const progressContainer = document.querySelector('.steps-container');
    const installButton = document.getElementById('installButton');
    const installSteps = document.getElementById('installSteps');

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
        if (androidSteps) androidSteps.style.display = 'none';

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
        } else {
            // Desktop view
            installSteps.innerHTML = `
                <div class="pc-message">
                    <span class="device-icon">💻</span>
                    <p>L'application est conçue pour les appareils mobiles.</p>
                    <p class="secondary-text">Revenez sur cette page depuis votre téléphone !</p>
                </div>
            `;
        }
    };

    // Appeler immédiatement la fonction de détection
    updateDeviceSpecificContent();

    // Initialisation des boutons de plateforme
    if (platformBtns) {
        platformBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                platformBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                
                if (btn.classList.contains('ms-store-btn')) {
                    // window.open('ms-windows-store://pdp/?productid=9999999', '_blank');
                } else if (btn.classList.contains('direct-btn')) {
                    window.location.href = "https://github.com/TGA25dev/Pronotif/releases/latest/download/Pronotif.Setup.v0.5.1.zip";
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
                alert('Installation non disponible pour le moment. Assurez-vous que l\'application n\'est pas déjà installée.');
                return;
            }

            try {
                deferredPrompt.prompt();
                const choiceResult = await deferredPrompt.userChoice;
                if (choiceResult.outcome === 'accepted') {
                    console.log('[PWA] Installation acceptée');
                }
                deferredPrompt = null;
            } catch (error) {
                console.error('[PWA] Erreur d\'installation:', error);
                alert('Une erreur est survenue lors de l\'installation.');
            }
        });
    }

    // Initialisation
    updateDeviceSpecificContent();
});

// Événements globaux
window.addEventListener('beforeinstallprompt', (evt) => {
    evt.preventDefault();
    deferredPrompt = evt;
    console.log('[PWA] beforeinstallprompt event captured');
    // Update the UI after capturing the prompt
    updateDeviceSpecificContent();
});

window.addEventListener('appinstalled', (evt) => {
    const androidSteps = document.getElementById('android-steps');
    const installTitle = document.querySelector('.install-steps h2');
    if (androidSteps && installTitle) {
        installTitle.style.display = 'none';
        androidSteps.innerHTML = `
            <div class="success-message">
                <h2>Installation réussie !</h2>
                <p>Merci d'avoir installé l'application ! 🎉</p>
                <p class="secondary-text">Vous pouvez maintenant fermer cette fenêtre.</p>
            </div>
        `;
    }
});

// Service Worker
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('scripts/sw.js')
            .then(() => console.log('ServiceWorker enregistré'))
            .catch(error => console.error('Erreur ServiceWorker:', error));
    });
}

