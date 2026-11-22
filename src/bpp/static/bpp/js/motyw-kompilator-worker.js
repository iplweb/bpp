/*
 * Web worker konfiguratora wyglądu: kompiluje podgląd motywu w tle
 * (1–3 s, UI w tym czasie nie zamiera). Sama kompilacja: motyw-kompilator.js
 * (ten sam kod uruchamia serwer przy „Zastosuj”).
 *
 * Adresy zależności w query stringu workera:
 *   sass        — dist/sass-przegladarka.js (Grunt: shell:esbuildSass),
 *   konfig      — motyw-konfig.js,
 *   kompilator  — motyw-kompilator.js,
 *   zrodla      — dist/motyw-zrodla-scss.json (Grunt: motywyZrodla).
 *
 * Wiadomość: {id, konfig, czcionkiUrl, trybPodgladu?} → odpowiedź {id, css}
 * albo {id, blad}. `trybPodgladu` (jasny/ciemny) wymusza wariant trybu
 * automatycznego na podglądzie.
 */
/* global BppMotywKompilator */
"use strict";

var parametry = new URL(self.location.href).searchParams;

// Skrypty wyłącznie z tej samej domeny i ścieżki plików statycznych co sam
// worker — parametry podaje strona konfiguratora, ale nie ufamy im w ciemno.
var KATALOG_WORKERA = self.location.pathname.replace(/[^/]*$/, "");
var KATALOG_STATYCZNY = KATALOG_WORKERA.replace(/bpp\/js\/$/, "");

function zaufanyAdres(nazwa) {
    var adres = new URL(parametry.get(nazwa) || "", self.location.href);
    if (adres.origin !== self.location.origin || adres.pathname.indexOf(KATALOG_STATYCZNY) !== 0) {
        throw new Error("Niedozwolony adres zasobu kompilatora: " + nazwa);
    }
    return adres.origin + adres.pathname;
}

importScripts(zaufanyAdres("sass"), zaufanyAdres("konfig"), zaufanyAdres("kompilator"));

var zrodla = null;

function pobierzZrodla() {
    if (!zrodla) {
        zrodla = fetch(zaufanyAdres("zrodla")).then(function (r) {
            if (!r.ok) throw new Error("Nie udało się pobrać źródeł SCSS: " + r.status);
            return r.json();
        });
    }
    return zrodla;
}

self.onmessage = function (e) {
    var dane = e.data;
    pobierzZrodla()
        .then(function (pliki) {
            var css = BppMotywKompilator.kompilujWarianty(
                pliki,
                dane.konfig,
                { czcionkiUrl: dane.czcionkiUrl },
                dane.warianty,
            );
            self.postMessage({ id: dane.id, css: css });
        })
        .catch(function (blad) {
            self.postMessage({ id: dane.id, blad: String((blad && blad.message) || blad) });
        });
};
