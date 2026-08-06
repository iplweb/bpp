/**
 * Podswietlanie frazy w opisie bibliograficznym (HTML).
 *
 * Opis niesie zamierzony markup (<b>, <i>, <sub>) oraz — od czasu wdrozenia
 * WCAG 3.1.2 — <span lang="xx"> wokol tytulu obcojezycznego. Naiwne
 * `text.replace(regex, '<mark>$1</mark>')` nie odroznia tresci od
 * znacznikow: fraza "en" trafiala w lang="en" i wstawiala <mark> w SRODEK
 * atrybutu, produkujac zepsuty markup przy .html(text).
 *
 * Rozwiazanie: podziel wejscie na segmenty <tag> / tekst i podswietlaj
 * wylacznie w tekstowych.
 */
(function (window) {
    "use strict";

    var TAG_LUB_TEKST = /(<[^>]*>)|([^<]+)/g;

    function escapeRegExp(ciag) {
        return ciag.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    }

    /**
     * @param {string} html - opis bibliograficzny (moze zawierac znaczniki)
     * @param {string} fraza - szukany tekst (bez rozrozniania wielkosci liter)
     * @returns {string} HTML z <mark> wokol trafien w tresci
     */
    function bppHighlightOutsideTags(html, fraza) {
        if (!fraza) {
            return html;
        }

        var regex = new RegExp("(" + escapeRegExp(fraza) + ")", "gi");

        return html.replace(TAG_LUB_TEKST, function (_, znacznik, tekst) {
            if (znacznik) {
                return znacznik;
            }
            return tekst.replace(regex, '<mark class="bpp-highlight">$1</mark>');
        });
    }

    window.bppHighlightOutsideTags = bppHighlightOutsideTags;
})(typeof window !== "undefined" ? window : this);
