// Strona /mcp/: kopiowanie promptu, adresów i wklejek kliknięciem w pole.
// Klikalny jest cały kontener z atrybutem data-mcp-kopiuj="<id>"; przycisk
// w rogu to ta sama akcja, tyle że osiągalna z klawiatury.
(function () {
    "use strict";

    function pokazKomunikat(pojemnik, tekst) {
        var komunikat = pojemnik.querySelector(".mcp-strona__komunikat");
        if (!komunikat) {
            return;
        }
        komunikat.textContent = tekst;
        window.setTimeout(function () {
            komunikat.textContent = "";
        }, 2500);
    }

    // Zapasowo dla kontekstu bez HTTPS (navigator.clipboard jest wtedy
    // niedostępny) albo gdy przeglądarka odmówiła dostępu do schowka.
    function kopiujPrzezZaznaczenie(zrodlo) {
        var zakres = document.createRange();
        zakres.selectNodeContents(zrodlo);
        var zaznaczenie = window.getSelection();
        zaznaczenie.removeAllRanges();
        zaznaczenie.addRange(zakres);
        try {
            return document.execCommand("copy");
        } catch (blad) {
            console.error("mcp: kopiowanie przez zaznaczenie nie powiodło się", blad);
            return false;
        }
    }

    // Kliknięcie kończące zaznaczanie myszą nie może podmieniać schowka —
    // ktoś zaznacza fragment wklejki właśnie po to, żeby skopiować sam ten
    // fragment. Przycisk kopiuje zawsze, bo tam intencja jest jednoznaczna.
    function trwaZaznaczanie(zdarzenie) {
        if (zdarzenie.target.closest(".mcp-strona__kopiuj")) {
            return false;
        }
        var zaznaczenie = window.getSelection();
        return Boolean(zaznaczenie) && zaznaczenie.toString().trim() !== "";
    }

    document.addEventListener("click", function (zdarzenie) {
        var pojemnik = zdarzenie.target.closest("[data-mcp-kopiuj]");
        if (!pojemnik || trwaZaznaczanie(zdarzenie)) {
            return;
        }
        var zrodlo = document.getElementById(pojemnik.dataset.mcpKopiuj);
        if (!zrodlo) {
            console.error("mcp: brak elementu do skopiowania", pojemnik);
            return;
        }
        var ok = pojemnik.dataset.komunikatOk;
        var blad = pojemnik.dataset.komunikatBlad;

        function zapasowo() {
            pokazKomunikat(pojemnik, kopiujPrzezZaznaczenie(zrodlo) ? ok : blad);
        }

        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(zrodlo.textContent).then(
                function () {
                    pokazKomunikat(pojemnik, ok);
                },
                function (odmowa) {
                    console.error("mcp: schowek odmówił zapisu", odmowa);
                    zapasowo();
                }
            );
        } else {
            zapasowo();
        }
    });
})();
