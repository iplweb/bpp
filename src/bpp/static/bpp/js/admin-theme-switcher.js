/**
 * Admin Theme Switcher
 * Manages theme selection and persistence in localStorage
 */
(function() {
    'use strict';

    // Theme configuration
    const THEMES = {
        'default': {
            name: 'Domyślny (ciemny)',
            class: '',
            description: 'Czarne tło z niebieskimi akcentami'
        },
        'classic-light': {
            name: 'Klasyczny jasny',
            class: 'theme-classic-light',
            description: 'Styl dziennikarski - czysty i nowoczesny'
        },
        'navy-academic': {
            name: 'Granatowy akademicki',
            class: 'theme-navy-academic',
            description: 'Poważny i prestiżowy - styl The Economist'
        },
        'gray-professional': {
            name: 'Szary profesjonalny',
            class: 'theme-gray-professional',
            description: 'Nowoczesny i techniczny - styl Bloomberg'
        },
        'cream-green': {
            name: 'Kremowo-zielony',
            class: 'theme-cream-green',
            description: 'Akademicki i spokojny - styl biblioteczny'
        },
        'minimal-light': {
            name: 'Minimalistyczny jasny',
            class: 'theme-minimal-light',
            description: 'Prosty i czytelny - styl Medium'
        }
    };

    const STORAGE_KEY = 'bpp-admin-theme';

    /**
     * Get the current theme from localStorage
     */
    function getCurrentTheme() {
        const stored = localStorage.getItem(STORAGE_KEY);
        return stored && THEMES[stored] ? stored : 'default';
    }

    /**
     * Set and apply a theme
     */
    function setTheme(themeKey) {
        if (!THEMES[themeKey]) {
            console.warn('Unknown theme:', themeKey);
            return;
        }

        // Remove all theme classes
        Object.values(THEMES).forEach(theme => {
            if (theme.class) {
                document.body.classList.remove(theme.class);
            }
        });

        // Apply new theme class
        if (THEMES[themeKey].class) {
            document.body.classList.add(THEMES[themeKey].class);
        }

        // Save to localStorage
        localStorage.setItem(STORAGE_KEY, themeKey);

        // Update active indicators in menu
        updateMenuIndicators(themeKey);
    }

    /**
     * Update active theme indicators in the menu
     */
    function updateMenuIndicators(activeThemeKey) {
        // Remove all active classes
        document.querySelectorAll('.theme-selector-item').forEach(item => {
            item.classList.remove('active');
        });

        // Add active class to current theme
        const activeSelector = document.querySelector(`.theme-selector-${activeThemeKey}`);
        if (activeSelector) {
            activeSelector.classList.add('active');
        }
    }

    /**
     * Initialize theme on page load
     */
    function initTheme() {
        const currentTheme = getCurrentTheme();
        setTheme(currentTheme);
    }

    /**
     * Handle theme selection from menu
     */
    function handleThemeSelection(event) {
        // Check if clicked on a theme selector link
        const link = event.target.closest('a[href^="#theme-"]');
        if (!link) return;

        event.preventDefault();

        // Extract theme key from hash (e.g., "#theme-classic-light" -> "classic-light")
        const href = link.getAttribute('href');
        const themeKey = href.replace('#theme-', '');

        // Validate theme exists
        if (!THEMES[themeKey]) {
            console.warn('Unknown theme from link:', themeKey);
            return;
        }

        setTheme(themeKey);

        // Provide visual feedback
        const menuItem = link.closest('li');
        if (menuItem) {
            // Add a brief highlight effect
            menuItem.style.transition = 'background-color 0.3s';
            const originalBg = menuItem.style.backgroundColor;
            menuItem.style.backgroundColor = '#5a9fd4';
            setTimeout(() => {
                menuItem.style.backgroundColor = originalBg;
            }, 300);
        }
    }

    /**
     * Add keyboard shortcuts for theme switching
     */
    function initKeyboardShortcuts() {
        document.addEventListener('keydown', function(e) {
            // Don't trigger if user is typing in an input/textarea
            if (e.target.matches('input, textarea, select')) {
                return;
            }

            // Alt + T + [1-7] for quick theme switching
            if (e.altKey && e.key === 't') {
                e.preventDefault();
                const themeKeys = Object.keys(THEMES);

                // Listen for the next number key
                const numberListener = function(e2) {
                    const num = parseInt(e2.key);
                    if (num >= 1 && num <= themeKeys.length) {
                        e2.preventDefault();
                        setTheme(themeKeys[num - 1]);
                    }
                    document.removeEventListener('keydown', numberListener);
                };

                document.addEventListener('keydown', numberListener);

                // Remove listener after 2 seconds if no key pressed
                setTimeout(() => {
                    document.removeEventListener('keydown', numberListener);
                }, 2000);
            }
        });
    }

    /**
     * Export theme API for external use
     */
    window.BPPAdminTheme = {
        themes: THEMES,
        getCurrentTheme: getCurrentTheme,
        setTheme: setTheme,
        getAvailableThemes: () => Object.keys(THEMES)
    };

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            initTheme();
            initKeyboardShortcuts();
            // Add click listener for theme selection
            document.addEventListener('click', handleThemeSelection);
        });
    } else {
        // DOM already loaded
        initTheme();
        initKeyboardShortcuts();
        document.addEventListener('click', handleThemeSelection);
    }

})();
