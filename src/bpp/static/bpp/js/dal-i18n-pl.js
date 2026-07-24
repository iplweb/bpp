// Polish i18n loader for django-autocomplete-light (DAL).
//
// DLACZEGO ISTNIEJE:
// Vendored `dal/static/autocomplete_light/i18n/pl.js` deklaruje
// `var dalLoadLanguage = function (...) {...}` w zasięgu GLOBALNYM (jako
// zwykły <script>), a `autocomplete_light.js` odwołuje się do tej funkcji
// jako do GLOBALA (`typeof dalLoadLanguage !== 'undefined'` oraz wywołanie
// z nasłuchu na event `dal-language-loaded`). Po zbundlowaniu esbuildem
// każdy plik ma własny scope modułu, a `var dalLoadLanguage` nie jest
// nigdzie w module używane — esbuild wycina je jako martwy, wolny od
// side-effectów binding (initializer to czysty function expression).
// Zostaje tylko `document.dispatchEvent(...)` (side-effect), więc event
// leci, listener odpala, ale funkcji NIE ma → ReferenceError i DAL select2
// traci polskie i18n. To INNY mechanizm niż łata `shell:patchBundle`
// (tam aliasowanie zmangowanego `yl` na `window.yl`), więc tamta łata
// tego nie obejmuje.
//
// NAPRAWA (jawny eksport na window — wzorzec jak `select2-pl.js`):
// definiujemy `dalLoadLanguage` na `window`, dzięki czemu wolna referencja
// z `autocomplete_light.js` rozwiązuje się przez global scope do
// `window.dalLoadLanguage` w runtime. Import tego pliku zastępuje import
// vendored `i18n/pl.js` w `bundle-entry.js` (ten sam efekt: rejestracja
// `select2/i18n/pl` w AMD select2 + dispatch eventu `dal-language-loaded`),
// ale w postaci odpornej na tree-shaking.

window.dalLoadLanguage = function (jQuery) {
    var amd = jQuery && jQuery.fn && jQuery.fn.select2 && jQuery.fn.select2.amd
        ? jQuery.fn.select2.amd
        : undefined;

    if (!amd) {
        return;
    }

    amd.define("select2/i18n/pl", [], function () {
        function plural(n, forms) {
            if (n === 1) return forms[0];
            if (n > 1 && n <= 4) return forms[1];
            if (n >= 5) return forms[2];
        }

        var charWords = ["znak", "znaki", "znaków"];
        var itemWords = ["element", "elementy", "elementów"];

        return {
            errorLoading: function () {
                return "Nie można załadować wyników.";
            },
            inputTooLong: function (args) {
                var over = args.input.length - args.maximum;
                return "Usuń " + over + " " + plural(over, charWords);
            },
            inputTooShort: function (args) {
                var remaining = args.minimum - args.input.length;
                return "Podaj przynajmniej " + remaining + " " +
                    plural(remaining, charWords);
            },
            loadingMore: function () {
                return "Trwa ładowanie…";
            },
            maximumSelected: function (args) {
                return "Możesz zaznaczyć tylko " + args.maximum + " " +
                    plural(args.maximum, itemWords);
            },
            noResults: function () {
                return "Brak wyników";
            },
            searching: function () {
                return "Trwa wyszukiwanie…";
            },
            removeAllItems: function () {
                return "Usuń wszystkie przedmioty";
            }
        };
    });
};

// Zachowanie side-effectu vendored pl.js: powiadom `autocomplete_light.js`,
// że język jest gotowy (ścieżka z nasłuchem na event, gdy definicja
// dotrze po inicjalizacji DAL).
document.dispatchEvent(new CustomEvent("dal-language-loaded", { lang: "pl" }));
