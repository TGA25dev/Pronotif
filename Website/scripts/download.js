const platformBtns = document.querySelectorAll('.platform-btn');
const msStoreSteps = document.querySelector('.ms-store-steps');
const directSteps = document.querySelector('.direct-steps');
const step2 = document.querySelector('.step-2');
const storeBtn = document.querySelector('.store-btn');
const downloadBtn = document.querySelector('.download-exe-btn');
const progressContainer = document.querySelector('.steps-container');

// S'assurer que les sections sont cachées au chargement initial
document.addEventListener('DOMContentLoaded', () => {
    msStoreSteps.classList.add('hidden');
    directSteps.classList.add('hidden');
    // Retirer toute classe active des boutons
    platformBtns.forEach(btn => btn.classList.remove('active'));
});

platformBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        // Reset tous les boutons et sections
        platformBtns.forEach(b => b.classList.remove('active'));
        msStoreSteps.classList.add('hidden');
        directSteps.classList.add('hidden');
        
        // Activer uniquement le bouton cliqué et sa section
        btn.classList.add('active');
        if (btn.classList.contains('ms-store-btn')) {
            msStoreSteps.classList.remove('hidden');
        } else if (btn.classList.contains('direct-btn')) {
            directSteps.classList.remove('hidden');
        }
    });
});

// Supprimer l'activation automatique du bouton Microsoft Store
// document.querySelector('.ms-store-btn').click();

[storeBtn, downloadBtn].forEach(btn => {
    btn.addEventListener('click', () => {
        setTimeout(() => {
            progressContainer.classList.add('progress-active');
            step2.classList.add('active');
        }, 100);
    });
});

// Register Service Worker
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('scripts/sw.js')
            .then(() => {
                console.log('ServiceWorker registration successful');
            })
            .catch(error => {
                console.error('ServiceWorker registration failed:', error);
            });
    });
}

const installButton = document.getElementById('installButton');
let deferredPrompt = null; // Initialize as null

// Always start with button hidden
installButton.style.display = 'none';

// Show the install button only when beforeinstallprompt event is fired
console.log('[PWA] Setting up beforeinstallprompt listener');
window.addEventListener('beforeinstallprompt', (evt) => {
    evt.preventDefault(); // Prevent default browser install prompt
    console.log('[PWA] beforeinstallprompt event fired');
    deferredPrompt = evt;
    
    // Only show install button for Android devices
    if (isAndroid()) {
        console.log('[PWA] Showing install button for Android');
        installButton.style.display = 'block';
    }
});

// Handle the click on the install button
installButton.addEventListener('click', async () => {
    console.log('[PWA] Install button clicked, deferredPrompt:', deferredPrompt);
    
    if (!deferredPrompt) {
        console.log('[PWA] No deferred prompt available');
        alert('Installation non disponible pour le moment. Assurez-vous que l\'application n\'est pas déjà installée.');
        return;
    }

    try {
        deferredPrompt.prompt();
        const choiceResult = await deferredPrompt.userChoice;
        console.log('[PWA] User choice:', choiceResult.outcome);
        
        if (choiceResult.outcome === 'accepted') {
            console.log('[PWA] User accepted installation');
        }
        deferredPrompt = null;
    } catch (error) {
        console.error('[PWA] Error during installation:', error);
        alert('Une erreur est survenue lors de l\'installation.');
    }
});

function updateInstallInstructions() {
    const iosSteps = document.getElementById('ios-steps');
    const androidSteps = document.getElementById('android-steps');

    if (isIos()) {
        console.log('[PWA] Detected iOS device');
        iosSteps.style.display = 'block';
        androidSteps.style.display = 'none';
        installButton.style.display = 'none';
    } else if (isAndroid()) {
        console.log('[PWA] Detected Android device');
        iosSteps.style.display = 'none';
        androidSteps.style.display = 'block';
        // Only show button if we have a deferred prompt
        installButton.style.display = deferredPrompt ? 'block' : 'none';
    } else {
        console.log('[PWA] Detected non-mobile device');
        iosSteps.style.display = 'none';
        androidSteps.style.display = 'none';
        installButton.style.display = 'none';
        detectPC();
    }
}

// Listen for successful installation
window.addEventListener('appinstalled', (evt) => {
    console.log('[PWA] App was successfully installed');
    installButton.style.display = 'none';
    const androidSteps = document.getElementById('android-steps');
    const installTitle = document.querySelector('.install-steps h2');
    installTitle.style.display = 'none';

    androidSteps.innerHTML = `
        <div class="success-message">
            <h2>Installation réussie !</h2>
            <p>Merci d'avoir installé l'application ! 🎉</p>
            <p class="secondary-text">Vous pouvez maintenant fermer cette fenetre.</p>
        </div>
    `;
});

// Improved device detection
const isAndroid = () => {
    return /Android/i.test(navigator.userAgent);
};

const isIos = () => {
    const userAgent = window.navigator.userAgent.toLowerCase();
    return /iphone|ipad|ipod/.test(userAgent) && !window.MSStream;
};

window.addEventListener('load', updateInstallInstructions);

// iOS Detection and install prompt
function detectiOS() {
    const installButton = document.getElementById('installButton');
    const isStandalone = ('standalone' in window.navigator) && (window.navigator.standalone);
    
    if (isIos()) {
        installButton.style.display = 'none';
        if (!isStandalone) {
            document.getElementById('ios-install-prompt').style.display = 'block';
        }
    }
}    

// PC Detection
function detectPC() {
    const step2Header = document.querySelector('.step-2 .step-header');
    const installSteps = document.querySelector('#installSteps');
    
    if (!/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) {
        installSteps.style.display = 'none';
        
        // Insert the PC message after the header (after subtitle)
        step2Header.insertAdjacentHTML('afterend', `
            <div class="pc-message">
                <span class="device-icon">📱</span>
                <p>Cette application est conçue pour les appareils mobiles.</p>
                <p class="secondary-text">Revenez sur cette page depuis votre téléphone !</p>
            </div>
        `);
    }
}

window.addEventListener('load', updateInstallInstructions);

