/**
 * Podswietlanie frazy w opisie bibliograficznym (HTML).
 *
 * Opis niesie zamierzony markup (<b>, <i>, <sub>) oraz — od czasu wdrozenia
 * WCAG 3.1.2 — <span lang="xx"> wokol tytulu obcojezycznego. Naiwne
 * `text.replace(regex, '<mark>$1</mark>')` nie odroznia tresci od
 * znacznikow: fraza "en" trafiala w lang="en" i wstawiala <mark> w SRODEK
 * atrybutu, produkujac zepsuty markup przy .html(text).
 *
 * Opis moze tez niesc encje HTML — np. `_escape_bare_angle_brackets`
 * (src/bpp/util/text.py) zamienia bare "<" na "&lt;", co po dalszym
 * escapowaniu ampersandu w data-records daje lancuch typu "&amp;lt;".
 * Fraza "amp" albo "lt" (pospolita w tekstach medycznych: "ampicylina",
 * "amputacja") trafialaby wtedy w SRODEK encji, psujac ja identycznie jak
 * <span lang>. Dlatego pomijane sa zarowno znaczniki, jak i encje HTML
 * (lacznie z lancuchami wielokrotnie zagniezdzonych encji, np. "&amp;lt;"
 * traktowane jako jedna nierozdzielna calosc) — podswietlanie dziala
 * wylacznie w segmentach czystego tekstu.
 *
 * Rozwiazanie: podziel wejscie na segmenty <tag> / encja / tekst i
 * podswietlaj wylacznie w tekstowych.
 *
 * UWAGA: funkcja zaklada wejscie juz przepuszczone przez sanityzator HTML
 * (nh3 — patrz safe_opis_bibliograficzny_html). Nie jest bezpieczna dla
 * dowolnego surowego tekstu zawierajacego goly znak "<" bez odpowiadajacego
 * ">" traktowanego jako czesc znacznika — taki "<" polknie fragment tresci
 * jako rzekomy znacznik. W tym potoku (dwuwarstwowa sanityzacja) to
 * nieosiagalne, ale funkcja jest globalna i wielokrotnego uzytku, wiec
 * ostroznie przy nowych zastosowaniach.
 */
(function (window) {
    "use strict";

    // Kolejnosc alternatyw ma znaczenie: encja musi byc rozpoznana zanim
    // fragment trafi do gałęzi tekstowej. Encja to "&" + jeden lub wiecej
    // segmentow "znakiAlfanumeryczne;" pod rzad — obejmuje to zarowno
    // pojedyncze encje ("&amp;", "&#8211;"), jak i lancuchy wielokrotnie
    // zagniezdzonych encji ("&amp;lt;" — podwojnie zescape'owany "<").
    var TAG_LUB_ENCJA_LUB_TEKST =
        /(<[^>]*>)|(&(?:[#a-zA-Z0-9]+;)+)|([^<&]+|&)/g;

    function escapeRegExp(ciag) {
        return ciag.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    }

    /**
     * @param {string} html - opis bibliograficzny (moze zawierac znaczniki
     *   i encje HTML)
     * @param {string} fraza - szukany tekst (bez rozrozniania wielkosci liter)
     * @returns {string} HTML z <mark> wokol trafien w tresci
     */
    function bppHighlightOutsideTags(html, fraza) {
        if (!fraza) {
            return html;
        }

        var regex = new RegExp("(" + escapeRegExp(fraza) + ")", "gi");

        return html.replace(
            TAG_LUB_ENCJA_LUB_TEKST,
            function (_, znacznik, encja, tekst) {
                if (znacznik || encja) {
                    return znacznik || encja;
                }
                return tekst.replace(
                    regex,
                    '<mark class="bpp-highlight">$1</mark>'
                );
            }
        );
    }

    window.bppHighlightOutsideTags = bppHighlightOutsideTags;
})(typeof window !== "undefined" ? window : this);
