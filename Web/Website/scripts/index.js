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
            window.location.href = baseUrl + config.urlSuffix;
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

    document.getElementById('discoverBtn').addEventListener('click', () => {
        const modal = document.getElementById('comingSoonModal');
        modal.classList.add('show');
    });

    document.querySelector('.close-modal').addEventListener('click', () => {
        const modal = document.getElementById('comingSoonModal');
        modal.classList.remove('show');
    });

    document.querySelector('.modal-btn').addEventListener('click', () => {
        const modal = document.getElementById('comingSoonModal');
        modal.classList.remove('show');
    });

    document.getElementById('comingSoonModal').addEventListener('click', (e) => {
        if (e.target === document.getElementById('comingSoonModal')) {
            e.target.classList.remove('show');
        }
    });
});
