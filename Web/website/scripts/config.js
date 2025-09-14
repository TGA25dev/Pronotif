const config = {
    isDevelopment: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1',
    
    getUrlSuffix: function(path) {
        if (!this.isDevelopment) return '';
        if (path === '/') return '/index.html';
        return '.html';
    },
    
    handleUrlNavigation: function(button) {
        const path = button.getAttribute('data-href');
        if (path) {
            // Validate URL before navigation
            if (path === '/' || path.startsWith('/') || 
                path.startsWith('http://') || path.startsWith('https://')) {
                
                const suffix = this.getUrlSuffix(path);
                // For home page in dev, we need the full path
                if (this.isDevelopment && path === '/') {
                    window.location.href = 'index.html';
                } else {
                    window.location.href = path + suffix;
                }
            } else {
                console.error('Invalid URL detected:', path);
            }
        }
    },

    initializeUrlHandling: function() {
        document.querySelectorAll('[data-href]').forEach(button => {
            button.addEventListener('click', () => this.handleUrlNavigation(button));
        });
    }
};