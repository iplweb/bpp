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
        },
        'golden': {
            name: 'Złoty',
            class: 'theme-golden',
            description: 'Luksusowy i elegancki - złote akcenty'
        },
        'srebrny': {
            name: 'Srebrny',
            class: 'theme-srebrny',
            description: 'Elegancki i profesjonalny - srebrne akcenty'
        },
        'mario-bros': {
            name: 'Brat Ludwika',
            class: 'theme-mario-bros',
            description: 'Kolorowy i wesoły - styl retro gier'
        },
        'luigi': {
            name: 'Brat Mariana',
            class: 'theme-luigi',
            description: 'Zielony i świeży - styl Luigi'
        }
    };

    const STORAGE_KEY = 'bpp-admin-theme';
    const FONT_STORAGE_KEY = 'bpp-admin-font';

    // Font configuration
    const FONTS = {
        'default': {
            name: 'Domyślna czcionka',
            class: null,
            description: 'Systemowa czcionka domyślna'
        },
        'inter-small': {
            name: 'Inter',
            class: 'font-inter-small',
            description: 'Czcionka Inter (Google Fonts)'
        },
        'opensans-small': {
            name: 'Open Sans',
            class: 'font-opensans-small',
            description: 'Czcionka Open Sans (Google Fonts)'
        },
        'roboto-small': {
            name: 'Roboto',
            class: 'font-roboto-small',
            description: 'Czcionka Roboto (Google Fonts)'
        },
        'lato-small': {
            name: 'Lato',
            class: 'font-lato-small',
            description: 'Czcionka Lato (Google Fonts)'
        },
        'sourcesans-small': {
            name: 'Source Sans Pro',
            class: 'font-sourcesans-small',
            description: 'Czcionka Source Sans Pro (Google Fonts)'
        },
        'segoeui-small': {
            name: 'Segoe UI',
            class: 'font-segoeui-small',
            description: 'Czcionka systemowa Windows (Vista+)'
        },
        'arial-small': {
            name: 'Arial',
            class: 'font-arial-small',
            description: 'Klasyczna czcionka (Windows/Mac/Linux)'
        },
        'verdana-small': {
            name: 'Verdana',
            class: 'font-verdana-small',
            description: 'Czytelna czcionka ekranowa'
        },
        'calibri-small': {
            name: 'Calibri',
            class: 'font-calibri-small',
            description: 'Nowoczesna czcionka Microsoft Office'
        }
    };

    /**
     * Get the current theme from localStorage
     */
    function getCurrentTheme() {
        const stored = localStorage.getItem(STORAGE_KEY);
        return stored && THEMES[stored] ? stored : 'default';
    }

    /**
     * Get the current font from localStorage
     */
    function getCurrentFont() {
        const stored = localStorage.getItem(FONT_STORAGE_KEY);
        return stored && FONTS[stored] ? stored : null;
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
     * Set and apply a font
     */
    function setFont(fontKey) {
        if (fontKey && !FONTS[fontKey]) {
            console.warn('Unknown font:', fontKey);
            return;
        }

        // Remove all font classes
        Object.values(FONTS).forEach(font => {
            if (font.class) {
                document.body.classList.remove(font.class);
            }
        });

        // Handle font selection
        if (fontKey === 'default' || !fontKey) {
            // Default font - remove from localStorage
            localStorage.removeItem(FONT_STORAGE_KEY);
        } else if (FONTS[fontKey].class) {
            // Apply new font class
            document.body.classList.add(FONTS[fontKey].class);
            // Save to localStorage
            localStorage.setItem(FONT_STORAGE_KEY, fontKey);
        }

        // Update active indicators in menu
        updateFontIndicators(fontKey);
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
     * Update active font indicators in the menu
     */
    function updateFontIndicators(activeFontKey) {
        // Remove all active classes
        document.querySelectorAll('.font-selector-item').forEach(item => {
            item.classList.remove('active');
        });

        // Add active class to current font if set
        if (activeFontKey) {
            const activeSelector = document.querySelector(`.font-selector-${activeFontKey}`);
            if (activeSelector) {
                activeSelector.classList.add('active');
            }
        }
    }

    /**
     * Initialize theme on page load
     */
    function initTheme() {
        const currentTheme = getCurrentTheme();
        setTheme(currentTheme);

        // Also initialize font if saved
        const currentFont = getCurrentFont();
        if (currentFont) {
            setFont(currentFont);
        }
    }

    /**
     * Handle theme and font selection from menu
     */
    function handleThemeSelection(event) {
        const link = event.target.closest('a[href^="#theme-"], a[href^="#font-"]');
        if (!link) return;

        event.preventDefault();
        const href = link.getAttribute('href');

        // Handle theme selection
        if (href.startsWith('#theme-')) {
            const themeKey = href.replace('#theme-', '');

            // Validate theme exists
            if (!THEMES[themeKey]) {
                console.warn('Unknown theme from link:', themeKey);
                return;
            }

            setTheme(themeKey);
            provideVisualFeedback(link);
        }
        // Handle font selection
        else if (href.startsWith('#font-')) {
            const fontKey = href.replace('#font-', '');

            // Validate font exists
            if (!FONTS[fontKey]) {
                console.warn('Unknown font from link:', fontKey);
                return;
            }

            setFont(fontKey);
            provideVisualFeedback(link);
        }
    }

    /**
     * Provide visual feedback for menu item selection
     */
    function provideVisualFeedback(link) {
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
        fonts: FONTS,
        getCurrentTheme: getCurrentTheme,
        getCurrentFont: getCurrentFont,
        setTheme: setTheme,
        setFont: setFont,
        getAvailableThemes: () => Object.keys(THEMES),
        getAvailableFonts: () => Object.keys(FONTS)
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
