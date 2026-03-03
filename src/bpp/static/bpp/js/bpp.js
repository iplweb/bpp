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

    var top = element.getBoundingClientRect().top
        + window.scrollY - offset;
    window.scrollTo({ top: top, behavior: behavior });
};
