// BPP Form Handlers
// Provides common form-related functionality

if (window.bpp == undefined) window.bpp = {};

window.bpp.forms = {
    requireConfirmation: function(message) {
        return function(e) {
            if (!confirm(message)) {
                e.preventDefault();
                return false;
            }
        };
    },

    init: function() {
        var self = this;

        // Find all forms with data-confirm attribute
        document.querySelectorAll('form[data-confirm]').forEach(function(form) {
            var message = form.getAttribute('data-confirm');
            form.addEventListener('submit', self.requireConfirmation(message));
        });

        // Find all elements with data-confirm-submit attribute
        document.querySelectorAll('[data-confirm-submit]').forEach(function(element) {
            var message = element.getAttribute('data-confirm-submit');
            if (element.tagName.toLowerCase() === 'form') {
                element.addEventListener('submit', self.requireConfirmation(message));
            }
        });
    }
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        window.bpp.forms.init();
    });
} else {
    window.bpp.forms.init();
}
