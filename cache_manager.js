/**
 * Cache Management Utilities for Link Checker Dashboard
 * Ensures fresh data is always loaded from GitHub Pages
 */

class CacheManager {
    constructor() {
        this.timestamp = new Date().getTime();
        this.cacheVersion = this.getCacheVersion();
        this.init();
    }

    // Get cache version from meta tag or generate new one
    getCacheVersion() {
        const metaTag = document.querySelector('meta[name="github-pages-cache"]');
        return metaTag ? metaTag.content : `v=${this.timestamp}`;
    }

    // Initialize cache management
    init() {
        console.log(`Cache Manager initialized - Version: ${this.cacheVersion}`);
        
        // Clear any existing cache on load
        this.clearStorageCache();
        
        // Set up visibility change handler for refresh
        this.setupVisibilityHandler();
        
        // Add cache headers to all future requests
        this.interceptRequests();
    }

    // Clear browser storage cache
    clearStorageCache() {
        try {
            if (typeof(Storage) !== "undefined") {
                localStorage.clear();
                sessionStorage.clear();
                console.log('Storage cache cleared');
            }
        } catch (e) {
            console.warn('Could not clear storage cache:', e);
        }
    }

    // Clear service worker caches
    async clearServiceWorkerCache() {
        try {
            if ('caches' in window) {
                const cacheNames = await caches.keys();
                await Promise.all(
                    cacheNames.map(name => caches.delete(name))
                );
                console.log('Service worker caches cleared');
            }
        } catch (e) {
            console.warn('Could not clear service worker cache:', e);
        }
    }

    // Full cache clear and refresh
    async clearAllCaches() {
        try {
            // Clear storage
            this.clearStorageCache();
            
            // Clear service worker caches
            await this.clearServiceWorkerCache();
            
            // Unregister service workers
            if ('serviceWorker' in navigator) {
                const registrations = await navigator.serviceWorker.getRegistrations();
                await Promise.all(
                    registrations.map(registration => registration.unregister())
                );
                console.log('Service workers unregistered');
            }
            
            // Force reload from server
            window.location.reload(true);
        } catch (e) {
            console.warn('Cache clearing partially failed:', e);
            // Fallback: normal reload with cache buster
            window.location.href = window.location.href.split('?')[0] + '?t=' + new Date().getTime();
        }
    }

    // Refresh dashboard with cache busting
    refreshDashboard() {
        const currentUrl = window.location.href.split('?')[0];
        const timestamp = new Date().getTime();
        console.log('Refreshing dashboard with cache buster:', timestamp);
        window.location.href = `${currentUrl}?t=${timestamp}&nocache=true`;
    }

    // Set up page visibility change handler
    setupVisibilityHandler() {
        if (typeof document.hidden !== "undefined") {
            document.addEventListener("visibilitychange", () => {
                if (!document.hidden) {
                    // Page became visible - check if data is stale
                    const loadTime = new Date(document.querySelector('#load-time')?.textContent || 0);
                    const now = new Date();
                    const timeDiff = now - loadTime;
                    
                    // If page data is older than 5 minutes, refresh
                    if (timeDiff > 300000) { // 5 minutes
                        console.log('Stale data detected, refreshing...');
                        this.refreshDashboard();
                    }
                }
            });
        }
    }

    // Intercept and add cache busting to requests
    interceptRequests() {
        // Override fetch to add cache busting headers
        const originalFetch = window.fetch;
        window.fetch = (url, options = {}) => {
            if (typeof url === 'string' && url.includes('.csv')) {
                const separator = url.includes('?') ? '&' : '?';
                url = `${url}${separator}t=${this.timestamp}&nocache=true`;
            }
            
            options.headers = {
                ...options.headers,
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            };
            
            return originalFetch(url, options);
        };
    }

    // Add cache-busting parameters to URLs
    addCacheBuster(url) {
        const separator = url.includes('?') ? '&' : '?';
        return `${url}${separator}t=${this.timestamp}&nocache=true`;
    }

    // Update status indicator
    updateStatus() {
        const loadTimeElement = document.getElementById('load-time');
        const dataVersionElement = document.getElementById('data-version');
        
        if (loadTimeElement) {
            loadTimeElement.textContent = new Date().toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
        }
        
        if (dataVersionElement) {
            dataVersionElement.textContent = this.cacheVersion;
        }
    }
}

// Global functions accessible from HTML
window.clearBrowserCache = function() {
    if (window.cacheManager) {
        window.cacheManager.clearAllCaches();
    } else {
        // Fallback
        try {
            if (typeof(Storage) !== "undefined") {
                localStorage.clear();
                sessionStorage.clear();
            }
            window.location.reload(true);
        } catch (e) {
            window.location.reload();
        }
    }
};

window.refreshDashboard = function() {
    if (window.cacheManager) {
        window.cacheManager.refreshDashboard();
    } else {
        // Fallback
        const currentUrl = window.location.href.split('?')[0];
        const timestamp = new Date().getTime();
        window.location.href = `${currentUrl}?t=${timestamp}`;
    }
};

// Initialize cache manager when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.cacheManager = new CacheManager();
    
    // Set up keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + R for refresh
        if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
            e.preventDefault();
            window.refreshDashboard();
        }
        // Ctrl/Cmd + Shift + R for cache clear and refresh
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'R') {
            e.preventDefault();
            window.clearBrowserCache();
        }
    });
    
    console.log('Cache management system ready');
});