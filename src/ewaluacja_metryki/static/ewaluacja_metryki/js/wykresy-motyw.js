/*
 * Wykresy metryk (Plotly, circle-progress) w trybie ciemnym.
 *
 * Biblioteki rysują własnymi, stałymi kolorami (białe tło Plotly, ciemny
 * tekst osi, pierścień `rgba(0,0,0,.1)`), których nie zmieni ani motyw
 * z trybem ciemnym (_tryb-ciemny.scss), ani konfigurator wyglądu
 * (przetworzCss działa tylko na CSS). Dlatego kolory bierzemy z WYLICZONEGO
 * stylu strony (getComputedStyle) — działa przy każdym mechanizmie trybu
 * ciemnego i przy zmianie motywu, bez znajomości palety.
 *
 * Tryb jasny zostaje nietknięty: poprawki włączają się tylko, gdy tekst
 * strony jest jasny (czyli tło ciemne).
 *
 * Skrypt dołączać PO plotly.min.js — owija Plotly.newPlot i
 * $.fn.circleProgress, więc wywołania w szablonach zostają bez zmian.
 */
(function (w) {
    "use strict";

    function rgb(kolor) {
        var m = (kolor || "").match(/[\d.]+/g);
        return m ? m.slice(0, 3).map(Number) : [0, 0, 0];
    }

    function luminancja(c) {
        var f = function (v) {
            v /= 255;
            return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
        };
        return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
    }

    function kolorTekstu(el) {
        return w.getComputedStyle(el || document.body).color;
    }

    function zAlfa(kolor, alfa) {
        return "rgba(" + rgb(kolor).join(",") + "," + alfa + ")";
    }

    // Ciemne tło = jasny tekst strony.
    function ciemny(el) {
        return luminancja(rgb(kolorTekstu(el))) > 0.5;
    }

    function ustawDomyslnie(obiekt, klucz, wartosc) {
        if (obiekt[klucz] === undefined) obiekt[klucz] = wartosc;
    }

    // Przezroczyste tło (spod wykresu prześwituje karta), tekst i siatka
    // w kolorze tekstu strony. Jawnie ustawione kolory zostają.
    function plotlyUklad(layout, el) {
        if (!layout || !ciemny(el)) return layout;
        var tekst = kolorTekstu(el);
        var siatka = zAlfa(tekst, 0.15);
        layout.paper_bgcolor = "rgba(0,0,0,0)";
        layout.plot_bgcolor = "rgba(0,0,0,0)";
        layout.font = layout.font || {};
        ustawDomyslnie(layout.font, "color", tekst);
        Object.keys(layout).forEach(function (k) {
            if (/^[xy]axis\d*$/.test(k) && layout[k]) {
                ustawDomyslnie(layout[k], "gridcolor", siatka);
                ustawDomyslnie(layout[k], "zerolinecolor", siatka);
                ustawDomyslnie(layout[k], "linecolor", siatka);
            }
        });
        if (layout.legend) ustawDomyslnie(layout.legend, "bgcolor", "rgba(0,0,0,0)");
        return layout;
    }

    function owinPlotly() {
        if (!w.Plotly || w.Plotly.__bppMotyw) return;
        var newPlot = w.Plotly.newPlot;
        w.Plotly.newPlot = function (cel, dane, layout, config) {
            var el = typeof cel === "string" ? document.getElementById(cel) : cel;
            return newPlot.call(this, cel, dane, plotlyUklad(layout || {}, el), config);
        };
        w.Plotly.__bppMotyw = true;
    }

    function owinCircleProgress() {
        var $ = w.jQuery;
        if (!$ || !$.fn.circleProgress || $.fn.circleProgress.__bppMotyw) return;
        var oryginal = $.fn.circleProgress;
        var owiniety = function (opcje) {
            if (opcje && typeof opcje === "object" && opcje.emptyFill === undefined &&
                ciemny(this[0])) {
                opcje = $.extend({}, opcje, { emptyFill: zAlfa(kolorTekstu(this[0]), 0.15) });
                return oryginal.call(this, opcje);
            }
            return oryginal.apply(this, arguments);
        };
        $.extend(owiniety, oryginal);
        owiniety.__bppMotyw = true;
        $.fn.circleProgress = owiniety;
    }

    owinPlotly();
    owinCircleProgress();
    w.bppWykresyMotyw = { plotlyUklad: plotlyUklad, ciemny: ciemny };
})(window);
