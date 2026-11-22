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
importScripts(parametry.get("sass"), parametry.get("konfig"), parametry.get("kompilator"));

var zrodla = null;

function pobierzZrodla() {
    if (!zrodla) {
        zrodla = fetch(parametry.get("zrodla")).then(function (r) {
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
            var css = BppMotywKompilator.kompiluj(pliki, dane.konfig, {
                czcionkiUrl: dane.czcionkiUrl,
                trybPodgladu: dane.trybPodgladu,
            });
            self.postMessage({ id: dane.id, css: css });
        })
        .catch(function (blad) {
            self.postMessage({ id: dane.id, blad: String((blad && blad.message) || blad) });
        });
};
