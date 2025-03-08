document.addEventListener('DOMContentLoaded', () => {

    // Offline check on page load
    function checkOnlineStatus() {
        if (!navigator.onLine) {
            // If we're offline according to navigator.onLine, redirect to offline page
            window.location.href = 'offline.htm';
        }
    }
    
    // Check immediately on load
    checkOnlineStatus();
    
    //Listen for network status changes
    window.addEventListener('offline', checkOnlineStatus);

    function isImageTooDark(imageData) {
        const data = imageData.data;
        let brightness = 0;
        
        // Sample every 20th pixel
        for (let i = 0; i < data.length; i += 80) {
            brightness += (data[i] + data[i + 1] + data[i + 2]) / 3;
        }
        
        const averageBrightness = brightness / (data.length / 80);
        return averageBrightness < 30; // Threshold
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

    // Initialize DOM elements
    const cameraButton = document.getElementById('cameraButton');
    const cameraView = document.getElementById('cameraView');
    const feedbackMessage = document.getElementById('feedbackMessage');
    const spinner = document.getElementById('spinner');
    const infosQR = document.getElementById('infosQR');

    // Service Worker Registration
    if ('serviceWorker' in navigator) {
        // First unregister any existing service worker
        navigator.serviceWorker.getRegistrations().then(async registrations => {
            for (const registration of registrations) {
                await registration.unregister();
            }
            
            // Then register the new one with cache busting
            const swUrl = `sw.js?cache=${Date.now()}`;
            navigator.serviceWorker.register(swUrl, {
                scope: './',
                updateViaCache: 'none'
            }).then(registration => {
                // Force immediate check for updates
                registration.update();
                
                // Listen for new service worker installation
                registration.addEventListener('updatefound', () => {
                    const newWorker = registration.installing;
                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'installed') {
                            // Force the new service worker to activate
                            newWorker.postMessage({type: 'SKIP_WAITING'});
                        }
                    });
                });
            });
        }).catch(console.error);
    }

    // Camera Permission
    cameraButton.addEventListener('click', async () => {
        try {
            // Try back camera first
            const constraints = {
                video: {
                    facingMode: { exact: 'environment' },
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                },
                audio: false
            };

            let stream;
            try {
                stream = await navigator.mediaDevices.getUserMedia(constraints); //Get the stream (camera)
                const errorDiv = document.querySelector('.camera-error');
                if (errorDiv) errorDiv.remove();

            } catch (backCameraError) {
                console.log('Back camera not available, trying front camera');
                stream = await navigator.mediaDevices.getUserMedia({ //Fallback to front camera
                    video: { facingMode: 'user' }
                });
            }

            cameraView.srcObject = stream;
            cameraView.style.display = 'block';
            cameraButton.style.display = 'none';
            infosQR.style.display = 'block';

            // Start QR code scanning
            function startQRScanning() {
                const canvasElement = document.getElementById('canvas');
                const ctx = canvasElement.getContext('2d', { willReadFrequently: true });
                let isProcessing = false;
                let lastScanTime = 0;
                const scanInterval = 250;

                const scan = () => {
                    const now = Date.now();
                    if (now - lastScanTime < scanInterval) {
                        requestAnimationFrame(scan);
                        return;
                    }

                    if (cameraView.readyState === cameraView.HAVE_ENOUGH_DATA && !isProcessing) {
                        lastScanTime = now;
                        canvasElement.width = cameraView.videoWidth;
                        canvasElement.height = cameraView.videoHeight;
                        ctx.drawImage(cameraView, 0, 0, canvasElement.width, canvasElement.height);
                        const imageData = ctx.getImageData(0, 0, canvasElement.width, canvasElement.height);
                        
                        // Skip processing if the image is too dark
                        if (isImageTooDark(imageData)) {
                            requestAnimationFrame(scan);
                            return;
                        }
                        
                        const code = jsQR(imageData.data, canvasElement.width, canvasElement.height);

                        if (code) {
                            try {
                                // Verify if the data looks like a valid QR code string
                                if (!code.data || typeof code.data !== 'string' || code.data.trim() === '') {
                                    showFeedback('QR code invalide (empty data)', 'error');
                                    console.warn('Invalid QR code data:', code.data);
                                    setTimeout(() => {
                                        hideFeedback();
                                    }, 3000);
                                    requestAnimationFrame(scan);
                                    return;
                                }

                                // Try to parse as JSON
                                let qrData;
                                try {
                                    qrData = JSON.parse(code.data);
                                } catch (parseError) {
                                    showFeedback('Ce QR code n\'est pas un QR code Pronot\'if valide', 'error');
                                    console.warn('QR code parse error:', parseError);
                                    setTimeout(() => {
                                        hideFeedback();
                                    }, 3000);
                                    requestAnimationFrame(scan);
                                    return;
                                }
                                
                                // Verify if the parsed data
                                if (!qrData.session_id || !qrData.token) {
                                    showFeedback('QR code invalide', 'error');
                                    console.warn('Invalid QR code format:', qrData);
                                    setTimeout(() => {
                                        hideFeedback();
                                    }, 3000);
                                    requestAnimationFrame(scan);
                                    return;
                                }

                                console.log('Raw QR data:', qrData);

                                // Convert None values to "0"strings
                                const convertToString = (value) => {
                                    if (value === "None") return "0";
                                    return value;
                                };

                                // Map the data
                                const mappedData = {
                                    session_id: qrData.session_id,
                                    token: qrData.token,
                                    login_page_link: qrData.login_page_link,
                                    student_username: qrData.student_username,
                                    student_password: qrData.student_password,
                                    student_fullname: qrData.student_fullname,
                                    student_firstname: qrData.student_firstname,
                                    student_class: qrData.student_class,
                                    ent_used: convertToString(qrData.ent_used),
                                    lunch_times: convertToString(qrData.lunch_times),
                                    qr_code_login: convertToString(qrData.qr_code_login),
                                    uuid: qrData.uuid === "None" ? "00000000-0000-0000-0000-000000000000" : qrData.uuid,
                                    topic_name: qrData.topic_name,
                                    timezone: qrData.timezone,
                                    notification_delay: qrData.notification_delay,
                                    evening_menu: convertToString(qrData.evening_menu),
                                    unfinished_homework_reminder: convertToString(qrData.unfinished_homework_reminder),
                                    get_bag_ready_reminder: convertToString(qrData.get_bag_ready_reminder)
                                };


                                isProcessing = true;
                                cameraView.classList.add('loading');
                                spinner.style.display = 'block';
                                document.body.style.opacity = '0.7';
                                showFeedback('QR code detected, processing...', 'info');

                                console.log('Sending data to API:', mappedData);

                                fetch('https://api.pronotif.tech/v1/app/qrscan', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify(mappedData)
                                })
                                .then(async response => {
                                    if (!response.ok) {
                                        let errorMessage;
                                        switch (response.status) {
                                            case 429:
                                                errorMessage = 'Too many attempts. Please wait a moment.';
                                                break;
                                            case 400:
                                                const serverResponse = await response.text();
                                                errorMessage = `Invalid request: ${serverResponse}`;
                                                break;
                                            case 401:
                                                errorMessage = 'Invalid or expired session.';
                                                break;
                                            case 500:
                                                errorMessage = 'Server error. Please try again later.';
                                                break;
                                            default:
                                                errorMessage = `Server error (${response.status})`;
                                        }
                                        throw new Error(errorMessage);
                                    }
                                    return response.json();
                                })
                                .then(apiResponse => {
                                    spinner.style.display = 'none';
                                    document.body.style.opacity = '1';
                                    showFeedback('Vous êtes mantenant connecté ! 🥳', 'success');
                                    console.log('QR scan API response:', apiResponse);
                                    setTimeout(() => {
                                        isProcessing = false;
                                        cameraView.classList.remove('loading');
                                        hideFeedback();
                                    }, 3000);
                                    cameraView.style.display = 'none';
                                    infosQR.style.display = 'none';
                                    
                                })
                                .catch(error => {
                                    console.error('Error:', error);
                                    document.body.style.opacity = '1';
                                    showFeedback(error.message || 'Error processing QR code. Please try again.', 'error');
                                    setTimeout(() => {
                                        isProcessing = false;
                                        cameraView.classList.remove('loading');
                                        hideFeedback();
                                        spinner.style.display = 'none';
                                    }, 3000);
                                });

                            } catch (parseError) {
                                console.error('QR code parse error:', parseError);
                                showFeedback('Invalid QR code format', 'error');
                                setTimeout(() => {
                                    isProcessing = false;
                                    cameraView.classList.remove('loading');
                                    hideFeedback();
                                    spinner.style.display = 'none';
                                }, 3000);
                            }
                        } else {
                            // Don't show spinner when no QR code is detected
                            spinner.style.display = 'none';
                        }
                    }
                    requestAnimationFrame(scan);
                };

                function showFeedback(message, type) {
                    if (!feedbackMessage) return;
                    feedbackMessage.innerHTML = message;
                    // Reset all classes first
                    feedbackMessage.className = 'feedback-message';
                    // Add the specific type class
                    feedbackMessage.classList.add(type);
                    feedbackMessage.style.display = 'block';
                }

                function hideFeedback() {
                    if (!feedbackMessage) return;
                    feedbackMessage.style.display = 'none';
                }

                scan();
            }
            startQRScanning();

        } catch (err) {
            console.error('Camera access denied:', err);
            
            // Check if error message already exists
            if (!document.querySelector('.camera-error')) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'camera-error';
                
                if (err.name === 'NotAllowedError') {
                    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
                    const isAndroid = /Android/.test(navigator.userAgent);

                    let settingsUrl = '';
                    let message = '';

                    if (isIOS) {
                        settingsUrl = '';
                        message = 'Accès à la caméra refusé 😔<br>Impossible de continuer...';

                    } else if (isAndroid) {
                        settingsUrl = "intent://#Intent;action=android.settings.SETTINGS;category=android.intent.category.DEFAULT;end;";
                        message = 'Accès à la caméra refusé 😔<br>Ouvrez les paramètres pour continuer.';

                    } else {
                        message = 'Accès à la caméra refusé 😔<br>Ouvrez les paramètres pour autoriser l\'accès à la caméra';
                    }

                    errorDiv.innerHTML = `
                        <div class="error-message">
                            ${message}
                            ${!isIOS ? `
                            <button class="settings-button" onclick="${isAndroid ? `window.location.href='${settingsUrl}'` : 'window.location.reload()'}">
                                ${isAndroid ? '⚙️ Ouvrir les paramètres' : '🔄 Réessayer'}
                            </button>
                            ` : ''}
                        </div>
                    `;
                } else {
                    errorDiv.innerHTML = `
                        Impossible d'accéder à la caméra 😔
                        <button class="settings-button" onclick="window.location.reload()">
                            🔄 Réessayer
                        </button>
                    `;
                }
                
                cameraButton.parentNode.insertBefore(errorDiv, cameraButton.nextSibling);
            }
        }
    });
});