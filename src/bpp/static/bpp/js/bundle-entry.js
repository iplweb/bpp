// BPP JavaScript Bundle Entry Point
// This file imports all JavaScript dependencies in the correct order
// Built with esbuild
//
// NOTE: jQuery is bundled via --inject:jquery-shim.js which ensures
// window.$ and window.jQuery are set BEFORE any other modules execute.
// This is critical for UMD libraries like jquery-ui and Foundation.

// ===== 2. JQUERY PLUGINS =====
import 'jquery.cookie';
import 'jqueryui/jquery-ui.min.js';
import 'jinplace/js/jinplace.js';
import 'jquery-circle-progress';

// ===== 3. FOUNDATION =====
import 'what-input';
import 'foundation-sites';
import 'foundation-datepicker';
import 'foundation-datepicker/js/locales/foundation-datepicker.pl.js';

// ===== 4. HTMX =====
import htmx from 'htmx.org';
window.htmx = htmx;  // Export to window for inline scripts

// ===== 5. DATATABLES =====
import 'datatables.net';
import 'datatables.net-zf';

// ===== 6. SELECT2 =====
import select2 from 'select2';
import './select2-pl.js';  // Polish language (exports to window.select2PlLanguage)

// Ensure Select2 is attached to the global jQuery for django-autocomplete-light
select2(window.jQuery);

// Set Polish language for Select2
window.jQuery.fn.select2.defaults.set('language', window.select2PlLanguage);

// ===== 7. MUSTACHE + TONE (for notifications) =====
import * as Mustache from '../../../../notifications/static/notifications/js/mustache.js';
window.Mustache = Mustache;

import * as Tone from 'tone';
window.Tone = Tone;

// ===== 8. DJANGO LIBRARIES (from .venv) =====
// Paths relative to site-packages
import '../../../../../.venv/lib/python3.12/site-packages/cookielaw/static/cookielaw/js/cookielaw.js';
// NOTE: multiseek.js must be loaded separately (not bundled) because it uses
// sloppy mode global function declarations that don't work in ES modules.
// It's loaded in multiseek/index.html template.
import '../../../../../.venv/lib/python3.12/site-packages/session_security/static/session_security/script.js';
import '../../../../../.venv/lib/python3.12/site-packages/dal/static/autocomplete_light/autocomplete_light.js';
import '../../../../../.venv/lib/python3.12/site-packages/dal/static/autocomplete_light/i18n/pl.js';
import '../../../../../.venv/lib/python3.12/site-packages/dal_select2/static/autocomplete_light/select2.js';

// ===== 9. DJANGO I18N (static file) =====
import './jsi18n-pl.js';

// ===== 10. BPP APPLICATION CODE =====
import './bpp.js';
import './form-handlers.js';
import '../../../../notifications/static/notifications/js/notifications.js';

// ===== 11. GLOBAL EXPORTS =====
// NOTE: django-autocomplete-light's 'yl' namespace is patched via sed
// post-processing in Gruntfile.js (shell:patchBundle task) to ensure
// it's available globally for inline scripts.

// ===== 12. PREVENT TREE-SHAKING FOR HTML-USED OBJECTS =====
// These are used in HTML templates, so we need to prevent tree-shaking
void window.bppNotifications;
void window.Mustache;
void window.Tone;
