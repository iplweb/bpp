// Filtr zgłoszeń dla frontendowego Rollbara (`checkIgnore`).
//
// Odsiewamy dwie klasy zgłoszeń, z którymi NIC nie da się zrobić:
//
// 1. Błędy pochodzące wyłącznie z obcych skryptów — u nas w praktyce widget
//    dostępności UserWay, ładowany z ich CDN-u. Przykład: SyntaxError
//    "invalid group specifier name" (lookbehind w regexie, nieobsługiwany
//    przez Safari < 16.4). To ich bundle, ich wydanie — nie mamy jak tego
//    naprawić ani nawet zdiagnozować.
//
// 2. Zgłoszenia bez użytecznego stack trace'u — brak ramek, filename
//    "(unknown)" albo filename będący komunikatem błędu. Powstają m.in. gdy
//    window.onerror dostaje zdarzenie zamiast Errora (nieudane ładowanie
//    <link>, serializowane przez Rollbara do "{}") albo gdy przeglądarka jest
//    tak stara, że nie podaje lokalizacji (Chrome 64 na Androidzie 8).
//    Bez pliku i linii nie ma czego szukać.
//
// ZASADA: w razie wątpliwości RAPORTUJ. Filtr, który przez własny błąd
// wycisza prawdziwe awarie, jest gorszy niż brak filtra — dlatego każda
// nierozpoznana sytuacja (brak payloadu, nieznany kształt) daje `false`.
//
// Ten plik jest ZWYKŁYM skryptem, nie modułem: rollbar.html ładuje go wcześnie
// w <head>, a `type="module"` odroczyłby wykonanie i część błędów z czasu
// ładowania strony uciekłaby przed inicjalizacją Rollbara.
(function (root) {
    "use strict";

    // Czy `filename` w ogóle wskazuje na jakiś plik? Rollbar wstawia tu
    // czasem "(unknown)" albo — dla przeglądarek nie podających lokalizacji —
    // sam komunikat błędu ("SyntaxError: Unexpected token =").
    function czyUzytecznaSciezka(filename) {
        if (!filename || typeof filename !== "string") {
            return false;
        }
        return /^https?:\/\//.test(filename) || filename.charAt(0) === "/";
    }

    function czyNaszaSciezka(filename, origin) {
        if (filename.charAt(0) === "/") {
            // Ścieżka względna → zawsze z bieżącego origin.
            return true;
        }
        return filename.indexOf(origin + "/") === 0 || filename === origin;
    }

    // Rollbar zapisuje ramki w `body.trace.frames` albo — dla wyjątków
    // łańcuchowych — w `body.trace_chain[].frames`.
    function zbierzRamki(payload) {
        var body = (payload && payload.body) || {};
        var ramki = [];

        if (body.trace && Array.isArray(body.trace.frames)) {
            ramki = ramki.concat(body.trace.frames);
        }
        if (Array.isArray(body.trace_chain)) {
            body.trace_chain.forEach(function (trace) {
                if (trace && Array.isArray(trace.frames)) {
                    ramki = ramki.concat(trace.frames);
                }
            });
        }
        return ramki;
    }

    function czyPominac(payload, origin) {
        if (!payload || !payload.body || !origin) {
            return false;
        }

        var sciezki = zbierzRamki(payload)
            .map(function (ramka) {
                return ramka && ramka.filename;
            })
            .filter(czyUzytecznaSciezka);

        if (!sciezki.length) {
            // Nic, co dałoby się zlokalizować w kodzie.
            return true;
        }

        var mamyNaszaRamke = sciezki.some(function (sciezka) {
            return czyNaszaSciezka(sciezka, origin);
        });

        // Choć jedna ramka z naszego kodu → to może być nasz błąd, raportuj.
        return !mamyNaszaRamke;
    }

    root.bppRollbarFilters = {
        czyPominac: czyPominac,
        czyUzytecznaSciezka: czyUzytecznaSciezka,
    };
})(typeof window !== "undefined" ? window : this);
