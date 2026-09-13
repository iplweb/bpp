// BPP namespace and utilities
// Using window.* for IIFE bundle compatibility
if (window.bpp == undefined) window.bpp = {};

window.queryDict = {};

location.search.substr(1).split("&").forEach(
    function (item) {
        window.queryDict[item.split("=")[0]] = item.split("=")[1]
    });

// Local reference for convenience within this module
var queryDict = window.queryDict;

window.qs = function(key) {
    key = key.replace(/[*+?^$.\[\]{}()|\\\/]/g, "\\$&"); // escape RegEx meta chars
    var match = location.search.match(new RegExp("[?&]"+key+"=([^&]+)(&|$)"));
    return match && decodeURIComponent(match[1].replace(/\+/g, " "));
};

// Local reference for convenience
var qs = window.qs;

/**
 * Scroll element to top of the visible area, accounting
 * for all sticky elements (nav bar, breadcrumbs) that
 * overlay the top of the viewport.
 *
 * Uses dynamic offsetHeight reads so it works regardless
 * of viewport size or number of wrapped nav-bar lines.
 *
 * Sticky selectors checked:
 *   - nav.sticky-header  (main top bar)
 *   - #breadcrumbs-wrapper (breadcrumb bar)
 *   - [data-bpp-sticky-bar] (dodatkowy pasek w treści strony,
 *     np. nawigacja po sekcjach jednostki) -- liczony tylko, gdy
 *     element docelowy leży pod nim
 *
 * @param {Element} element  DOM element to scroll into view
 * @param {Object}  [opts]   Optional settings
 * @param {number}  [opts.extraPadding=10]
 *     Extra pixels of breathing room below sticky bars
 * @param {string}  [opts.behavior='smooth']
 *     ScrollBehavior value ('smooth' | 'instant')
 */
window.bpp.scrollToVisible = function(element, opts) {
    opts = opts || {};
    var padding = (opts.extraPadding !== undefined)
        ? opts.extraPadding : 10;
    var behavior = opts.behavior || 'smooth';

    var offset = padding;
    var nav = document.querySelector(
        'nav.sticky-header'
    );
    if (nav) offset += nav.offsetHeight;
    var bc = document.getElementById(
        'breadcrumbs-wrapper'
    );
    if (bc) offset += bc.offsetHeight;

    // Dodatkowy pasek sticky wewnątrz treści. Jego `top` jest już liczony
    // od dołu belek powyżej (CSS: calc(var(--bpp-sticky-offset) + luz)),
    // więc nie dodajemy go do sumy, tylko bierzemy dolną krawędź paska w
    // pozycji przypiętej: top + wysokość.
    //
    // O tym, czy pasek w ogóle zasłoni cel, decyduje KOLEJNOŚĆ W DOM, a nie
    // bieżące współrzędne: po przewinięciu pasek będzie przypięty u góry,
    // więc każdy element leżący w dokumencie PO nim wyląduje pod nim.
    // Porównanie prostokątów sprzed przewinięcia dawało tu złą odpowiedź
    // dla pierwszej sekcji (skok do góry: cel był chwilowo nad paskiem).
    var bar = document.querySelector('[data-bpp-sticky-bar]');
    if (bar && bar.offsetHeight && bar !== element) {
        var barStyle = window.getComputedStyle(bar);
        var celPonizej = !!(bar.compareDocumentPosition(element)
            & Node.DOCUMENT_POSITION_FOLLOWING);
        if (barStyle.position === 'sticky' && celPonizej) {
            var barOffset = (parseFloat(barStyle.top) || 0)
                + bar.offsetHeight + padding;
            offset = Math.max(offset, barOffset);
        }
    }

    var top = element.getBoundingClientRect().top
        + window.scrollY - offset;
    window.scrollTo({ top: top, behavior: behavior });
};
