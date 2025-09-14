const config = {
    isDevelopment: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1',
    
    getUrlSuffix: function(path) {
        if (!this.isDevelopment) return '';
        if (path === '/') return '/index.html';
        return '.html';
    },
    
    handleUrlNavigation: function(button) {
        const baseUrl = button.getAttribute('data-href');
        
        if (baseUrl) {
            // Safer URL validation: trim whitespace, prevent protocol-relative and dangerous schemes
            const safeBaseUrl = baseUrl.trim();
            
            if ((safeBaseUrl.startsWith('/') && !safeBaseUrl.startsWith('//')) || 
                safeBaseUrl.startsWith('http://') || 
                safeBaseUrl.startsWith('https://')) {
                
                const suffix = this.getUrlSuffix(safeBaseUrl);
                
                // For home page in dev, we need the full path
                if (this.isDevelopment && safeBaseUrl === '/') {
                    window.location.href = 'index.html';
                } else {
                    window.location.href = safeBaseUrl + suffix;
                }
            } else {
                console.error('Invalid or potentially unsafe URL detected:', baseUrl);
            }
        }
    },

    initializeUrlHandling: function() {
        document.querySelectorAll('[data-href]').forEach(button => {
            button.addEventListener('click', () => this.handleUrlNavigation(button));
        });
    }
};