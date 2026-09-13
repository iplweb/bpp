// Strona /mcp/: przyciski „Kopiuj” przy prompcie, adresach i wklejkach.
// Przycisk wskazuje element do skopiowania atrybutem data-mcp-kopiuj="<id>".
(function () {
    "use strict";

    function pokazKomunikat(przycisk, tekst) {
        var komunikat = przycisk.parentElement.querySelector(
            ".mcp-strona__komunikat"
        );
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

    document.addEventListener("click", function (zdarzenie) {
        var przycisk = zdarzenie.target.closest("[data-mcp-kopiuj]");
        if (!przycisk) {
            return;
        }
        var zrodlo = document.getElementById(przycisk.dataset.mcpKopiuj);
        if (!zrodlo) {
            console.error("mcp: brak elementu do skopiowania", przycisk);
            return;
        }
        var ok = przycisk.dataset.komunikatOk;
        var blad = przycisk.dataset.komunikatBlad;

        function zapasowo() {
            pokazKomunikat(przycisk, kopiujPrzezZaznaczenie(zrodlo) ? ok : blad);
        }

        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(zrodlo.textContent).then(
                function () {
                    pokazKomunikat(przycisk, ok);
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
