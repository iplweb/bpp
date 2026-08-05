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
// 2. Zgłoszenia, które nie mają ANI lokalizacji, ANI treści — czyli klasa
//    "(unknown)" z komunikatem "{}". Powstają, gdy window.onerror dostaje
//    zdarzenie zamiast Errora (nieudane ładowanie <link>).
//
//    UWAGA: sam brak lokalizacji NIE wystarcza do wyciszenia. Wcześniejsza,
//    szersza wersja tej reguły zjadała nasze własne błędy: ręczne
//    `Rollbar.error("...")` (buduje `body.message`, zero ramek), odrzucone
//    obietnice z reason innym niż Error (ramka "(unknown)") oraz SyntaxError
//    z Rollbar #502 — a ten ostatni jest najpewniej sygnałem, że któryś nasz
//    statyk nie parsuje się na starszej przeglądarce.
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

    // Opis wyjątku z `body.trace` albo z pierwszego ogniwa `body.trace_chain`.
    function opisWyjatku(body) {
        if (body.trace && body.trace.exception) {
            return body.trace.exception;
        }
        if (Array.isArray(body.trace_chain) && body.trace_chain.length) {
            return body.trace_chain[0].exception || {};
        }
        return {};
    }

    // Czy zgłoszenie bez lokalizacji niesie JAKĄKOLWIEK treść, na której da
    // się pracować. Rollbar #444 to `class: "(unknown)"`, `message: "{}"` —
    // powstaje, gdy window.onerror dostaje zdarzenie zamiast Errora (nieudane
    // ładowanie <link>). Tam faktycznie nie ma czego szukać.
    function czyPustyOpis(wyjatek) {
        var klasa = wyjatek.class;
        var komunikat = wyjatek.message;
        var bezKlasy = !klasa || klasa === "(unknown)";
        var bezKomunikatu = !komunikat || komunikat === "{}";
        return bezKlasy && bezKomunikatu;
    }

    function czyPominac(payload, origin) {
        if (!payload || !payload.body || !origin) {
            return false;
        }

        var body = payload.body;

        // Brak `trace`/`trace_chain` → to nie jest raport o wyjątku, tylko
        // ręczny log (`Rollbar.error("...")` buduje `body.message`) albo
        // komunikat samego Rollbara o przekroczeniu rate-limitu. Nigdy nie
        // wyciszamy — to są zgłoszenia, które ktoś wysłał świadomie.
        if (!body.trace && !Array.isArray(body.trace_chain)) {
            return false;
        }

        var sciezki = zbierzRamki(payload)
            .map(function (ramka) {
                return ramka && ramka.filename;
            })
            .filter(czyUzytecznaSciezka);

        if (sciezki.length) {
            var mamyNaszaRamke = sciezki.some(function (sciezka) {
                return czyNaszaSciezka(sciezka, origin);
            });
            // Choć jedna ramka z naszego kodu → to może być nasz błąd.
            return !mamyNaszaRamke;
        }

        // Brak jakiejkolwiek lokalizacji. Wyciszamy TYLKO wtedy, gdy nie ma
        // też treści — inaczej wyrzucilibyśmy m.in. odrzucone obietnice
        // z reason innym niż Error (ramka "(unknown)") oraz SyntaxError
        // z Rollbar #502. Ten ostatni jest szczególnie ważny: przeglądarka
        // ujawnia treść błędu parsowania wyłącznie dla skryptów same-origin
        // (obce bez CORS dostają gołe "Script error."), więc konkretny
        // komunikat sugeruje, że któryś z NASZYCH statyków się nie parsuje —
        // czyli realną regresję kompatybilności, a nie szum.
        return czyPustyOpis(opisWyjatku(body));
    }

    root.bppRollbarFilters = {
        czyPominac: czyPominac,
        czyUzytecznaSciezka: czyUzytecznaSciezka,
    };
})(typeof window !== "undefined" ? window : this);
