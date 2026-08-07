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
 * Ten sam tokenizer napedza druga funkcje modulu, bppStripTags(html) —
 * zwraca sam tekst (bez znacznikow, z encjami zdekodowanymi). Uzywana do
 * FILTROWANIA rekordow (nie tylko podswietlania): dopasowanie po tekscie
 * bez znacznikow, zeby fraza "span"/"lang" nie trafiala fałszywie w
 * <span lang="…"> i nie dawala trafien bez zadnego podswietlenia na liscie.
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

    // Encje nazwane obslugiwane przez decodeEncje. Zestaw minimalny (te,
    // ktore faktycznie wystepuja w potoku opisu bibliograficznego) —
    // encje numeryczne (&#NN; / &#xHH;) obslugiwane osobno, ponizej.
    var ENCJE_NAZWANE = {
        amp: "&",
        lt: "<",
        gt: ">",
        quot: '"',
        apos: "'"
    };

    var ENCJA_REGEX = /&(#x[0-9a-fA-F]+|#[0-9]+|[a-zA-Z]+);/g;

    function decodeEncje(tekst) {
        var poprzedni;
        var wynik = tekst;
        var iteracje = 0;
        // Petla obsluguje wielokrotnie zagniezdzone encje (np. podwojnie
        // zescape'owany "&amp;lt;" -> jedna decyzja regexu dekoduje tylko
        // najbardziej zewnetrzna warstwe, "&lt;" zostaje na kolejny
        // przebieg) - do ustalonego punktu albo limitu iteracji jako
        // zabezpieczenie przed patologicznym wejsciem.
        do {
            poprzedni = wynik;
            wynik = wynik.replace(ENCJA_REGEX, function (dopasowanie, cialo) {
                if (cialo.charAt(0) === "#") {
                    var kod;
                    if (cialo.charAt(1) === "x" || cialo.charAt(1) === "X") {
                        kod = parseInt(cialo.slice(2), 16);
                    } else {
                        kod = parseInt(cialo.slice(1), 10);
                    }
                    return isNaN(kod) ? dopasowanie : String.fromCodePoint(kod);
                }
                var znak = ENCJE_NAZWANE[cialo];
                return znak === undefined ? dopasowanie : znak;
            });
            iteracje += 1;
        } while (wynik !== poprzedni && iteracje < 5);
        return wynik;
    }

    /**
     * Usuwa znaczniki HTML z opisu, zostawiajac wylacznie tresc tekstowa
     * (z zdekodowanymi encjami). Uzywa TEGO SAMEGO tokenizera co
     * podswietlanie, wiec segmentacja tekst/znacznik/encja jest identyczna —
     * przeznaczone do filtrowania po tresci (patrz uzycie w
     * praca_tabela_mono.html), zeby fraza "span"/"lang" nie trafiala w
     * znacznik <span lang="…"> i nie dawala falszywie pozytywnych trafien.
     *
     * @param {string} html - opis bibliograficzny (moze zawierac znaczniki
     *   i encje HTML)
     * @returns {string} sam tekst, bez znacznikow, z encjami zdekodowanymi
     */
    function bppStripTags(html) {
        var segmenty = [];
        html.replace(TAG_LUB_ENCJA_LUB_TEKST, function (_, znacznik, encja, tekst) {
            if (znacznik) {
                return "";
            }
            if (encja) {
                segmenty.push(decodeEncje(encja));
                return "";
            }
            segmenty.push(tekst);
            return "";
        });
        return segmenty.join("");
    }

    window.bppHighlightOutsideTags = bppHighlightOutsideTags;
    window.bppStripTags = bppStripTags;
})(typeof window !== "undefined" ? window : this);
