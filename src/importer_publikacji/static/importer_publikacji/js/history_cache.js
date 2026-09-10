// Sprzątanie NIEŚWIEŻYCH snapshotów HTMX dla stron importera publikacji.
//
// Dlaczego to w ogóle istnieje
// ----------------------------
// `index.html` ma `hx-history="false"` na `#importer-wizard`, więc HTMX nigdy
// NIE ZAPISZE snapshotu tej strony do localStorage — przy Back/Forward pyta
// serwer o pełną stronę (patrz `_is_htmx_partial` w views/helpers.py).
//
// Problem: `restoreHistory()` w HTMX czyta cache BEZ oglądania się na
// `hx-history` — ta flaga blokuje tylko ZAPIS (`saveCurrentPageToHistory`).
// Wpisy zapisane ZANIM flaga się pojawiła (układ kroku 1 sprzed kafelków:
// radiowy wybór źródła + lista sesji pod spodem) siedzą w localStorage
// przeglądarki bezterminowo i to je HTMX przywraca po naciśnięciu „Wstecz".
// Użytkownik widzi wtedy layout, którego nie ma już nawet w kodzie.
//
// Samo się to nie naprawi: skoro zapisu nigdy nie będzie, nic tych wpisów nie
// nadpisze (HTMX podmienia wpis o tym samym URL-u dopiero przy zapisie), a
// LRU wyrzuci je dopiero po 10 innych stronach z HTMX-em. Dlatego kasujemy je
// jawnie przy każdym wejściu na stronę importera.
(function (window) {
    "use strict";

    var KLUCZ = "htmx-history-cache";

    // Usuń z cache HTMX-a wpisy, których URL zaczyna się od `prefiks`.
    // Zwraca liczbę usuniętych wpisów (0 gdy nie było czego usuwać).
    function usunWpisy(storage, prefiks) {
        var surowe = storage.getItem(KLUCZ);
        if (!surowe) {
            return 0;
        }

        var cache;
        try {
            cache = JSON.parse(surowe);
        } catch (e) {
            // Uszkodzony JSON (obcy kod pisał pod ten klucz, przerwany zapis).
            // HTMX sam traktuje taki cache jak pusty (`parseJSON` zwraca null),
            // więc kasujemy wpis w całości — inaczej zostawilibyśmy śmieć,
            // którego i tak nikt nie odczyta.
            storage.removeItem(KLUCZ);
            return 0;
        }

        if (!Array.isArray(cache)) {
            storage.removeItem(KLUCZ);
            return 0;
        }

        var zostaje = cache.filter(function (wpis) {
            return !(
                wpis &&
                typeof wpis.url === "string" &&
                wpis.url.indexOf(prefiks) === 0
            );
        });

        var usuniete = cache.length - zostaje.length;
        if (usuniete > 0) {
            storage.setItem(KLUCZ, JSON.stringify(zostaje));
        }
        return usuniete;
    }

    window.bppImporterHistoryCache = { usunWpisy: usunWpisy, KLUCZ: KLUCZ };

    // Auto-start: prefiks URL-a importera wstrzykuje szablon (`data-prefiks`),
    // żeby nie zaszywać tu ścieżki na sztywno.
    var skrypt = window.document.currentScript;
    if (!skrypt) {
        return;
    }
    var prefiks = skrypt.getAttribute("data-prefiks");
    if (!prefiks) {
        return;
    }
    try {
        usunWpisy(window.localStorage, prefiks);
    } catch (e) {
        // localStorage niedostępny (tryb prywatny, zablokowane dane witryn) —
        // wtedy HTMX też go nie odczyta, więc nieświeży snapshot nie ma jak
        // się pojawić i nie ma czego sprzątać. Strona działa normalnie.
    }
})(window);
