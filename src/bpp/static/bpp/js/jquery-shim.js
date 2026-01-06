// jQuery shim - MUSI być inject'owany przez esbuild przed innymi modułami
// Import jQuery z npm i eksponowanie jako globalne PRZED czymkolwiek innym
import jQuery from 'jquery';

// Ustaw globale SYNCHRONICZNIE przed jakimkolwiek innym kodem
window.$ = window.jQuery = jQuery;
window.django = window.django || {};
window.django.jQuery = jQuery;

// Dla kompatybilności z nowszymi środowiskami
if (typeof globalThis !== 'undefined') {
    globalThis.$ = globalThis.jQuery = jQuery;
}

export default jQuery;
