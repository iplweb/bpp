/*
 * Kompilacja motywu z konfiguracji — wspólna dla przeglądarki i serwera.
 *
 *   - przeglądarka: web worker konfiguratora (motyw-kompilator-worker.js),
 *   - serwer: bpp/motyw_kompilator.py uruchamia ten plik w V8 (mini-racer)
 *     przy „Zastosuj” i przy migracji wyglądu po aktualizacji BPP
 *     (manage.py odswiez_motywy).
 *
 * Wymaga globalnych BppSass (dist/sass-przegladarka.js) i BppMotywKonfig
 * (motyw-konfig.js). Pliki SCSS pochodzą z dist/motyw-zrodla-scss.json
 * (Grunt: motywyZrodla): "bpp/<plik>" i "foundation/<ścieżka w pakiecie>".
 */
/* global BppSass, BppMotywKonfig */
(function (root) {
    "use strict";

    // Rozwiązywanie importów jak przy loadPaths: [scss BPP, scss Foundation].
    // Kanoniczne adresy: "mem:/bpp/<plik>", "mem:/foundation/scss/<ścieżka>".
    function importer(pliki) {
        function znajdz(sciezka) {
            var i = sciezka.lastIndexOf("/");
            var katalog = sciezka.slice(0, i + 1);
            var nazwa = sciezka.slice(i + 1).replace(/\.scss$/, "");
            var kandydaci = [
                katalog + "_" + nazwa + ".scss",
                katalog + nazwa + ".scss",
                sciezka + "/_index.scss",
                sciezka + "/index.scss",
            ];
            for (var k = 0; k < kandydaci.length; k++) {
                if (Object.prototype.hasOwnProperty.call(pliki, kandydaci[k])) {
                    return kandydaci[k];
                }
            }
            return null;
        }

        return {
            canonicalize: function (url) {
                var znaleziony;
                if (url.indexOf("mem:/") === 0) {
                    znaleziony = znajdz(url.slice(5));
                } else {
                    znaleziony = znajdz("bpp/" + url) || znajdz("foundation/scss/" + url);
                }
                return znaleziony ? new URL("mem:/" + znaleziony) : null;
            },
            load: function (canonicalUrl) {
                return {
                    contents: pliki[canonicalUrl.pathname.replace(/^\//, "")],
                    syntax: "scss",
                };
            },
        };
    }

    // Konfig → gotowy CSS (z trybem kolorów i tłem treści).
    // opcje.czcionkiUrl — adres katalogu czcionek (np. "/static/bpp/fonts"),
    // opcje.trybPodgladu — wymuszony wariant trybu automatycznego (podgląd).
    function kompiluj(pliki, konfig, opcje) {
        opcje = opcje || {};
        var imp = importer(pliki);
        var wynik = BppSass.compileString(
            BppMotywKonfig.doScss(konfig, { czcionkiUrl: opcje.czcionkiUrl }),
            {
                importer: imp,
                importers: [imp],
                url: new URL("mem:/bpp/__wejscie.scss"),
                style: "compressed",
                silenceDeprecations: ["global-builtin", "if-function", "import"],
                // Ostrzeżenia o przestarzałej składni (Foundation) zalewałyby
                // konsolę i spowalniały kompilację; build Grunta je pokazuje.
                logger: BppSass.Logger.silent,
            },
        );
        // przetworzCss usuwa też BOM — w <style> psułby pierwszą regułę
        // (@import czcionek z internetu).
        return BppMotywKonfig.przetworzCss(wynik.css, konfig, {
            trybPodgladu: opcje.trybPodgladu,
        });
    }

    root.BppMotywKompilator = { importer: importer, kompiluj: kompiluj };
})(typeof self !== "undefined" ? self : this);
