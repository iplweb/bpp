// Strona /mcp/: kopiowanie promptu, adresów i wklejek kliknięciem w pole.
// Klikalne jest całe pole z atrybutem data-mcp-kopiuj="<id>"; osobnego
// przycisku nie ma, więc z klawiatury obsługujemy Enter i spację.
(function () {
    "use strict";

    function pokazKomunikat(pojemnik, tekst, udane) {
        var komunikat = pojemnik.querySelector(".mcp-strona__komunikat");
        if (komunikat) {
            komunikat.textContent = tekst;
            komunikat.classList.toggle("mcp-strona__komunikat--ok", udane);
            komunikat.classList.toggle("mcp-strona__komunikat--blad", !udane);
        }
        pojemnik.classList.toggle("mcp-strona__kopiowalny--skopiowano", udane);
        window.setTimeout(function () {
            if (komunikat) {
                komunikat.textContent = "";
                komunikat.classList.remove("mcp-strona__komunikat--ok");
                komunikat.classList.remove("mcp-strona__komunikat--blad");
            }
            pojemnik.classList.remove("mcp-strona__kopiowalny--skopiowano");
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

    function kopiuj(pojemnik) {
        var zrodlo = document.getElementById(pojemnik.dataset.mcpKopiuj);
        if (!zrodlo) {
            console.error("mcp: brak elementu do skopiowania", pojemnik);
            return;
        }
        var ok = pojemnik.dataset.komunikatOk;
        var blad = pojemnik.dataset.komunikatBlad;

        function zapasowo() {
            var udane = kopiujPrzezZaznaczenie(zrodlo);
            pokazKomunikat(pojemnik, udane ? ok : blad, udane);
        }

        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(zrodlo.textContent).then(
                function () {
                    pokazKomunikat(pojemnik, ok, true);
                },
                function (odmowa) {
                    console.error("mcp: schowek odmówił zapisu", odmowa);
                    zapasowo();
                }
            );
        } else {
            zapasowo();
        }
    }

    // Kliknięcie kończące zaznaczanie myszą nie może podmieniać schowka —
    // ktoś zaznacza fragment wklejki właśnie po to, żeby skopiować sam ten
    // fragment.
    function trwaZaznaczanie() {
        var zaznaczenie = window.getSelection();
        return Boolean(zaznaczenie) && zaznaczenie.toString().trim() !== "";
    }

    document.addEventListener("click", function (zdarzenie) {
        var pojemnik = zdarzenie.target.closest("[data-mcp-kopiuj]");
        if (pojemnik && !trwaZaznaczanie()) {
            kopiuj(pojemnik);
        }
    });

    // Pole jest klikalne, więc ma role="button" i tabindex — a to znaczy,
    // że musi reagować na Enter i spację tak jak zwykły przycisk.
    document.addEventListener("keydown", function (zdarzenie) {
        if (zdarzenie.key !== "Enter" && zdarzenie.key !== " ") {
            return;
        }
        var pojemnik = zdarzenie.target.closest("[data-mcp-kopiuj]");
        if (!pojemnik) {
            return;
        }
        // Spacja przewija stronę, Enter bywa submitem — tu robi kopiowanie.
        zdarzenie.preventDefault();
        kopiuj(pojemnik);
    });

    // Ścieżki plików konfiguracyjnych mają wariant POSIX i windowsowy —
    // oba są w HTML-u, bo strona jest cache'owana wspólnie dla wszystkich
    // i serwer nie różnicuje jej po User-Agencie. Wybór robimy tutaj.
    function toWindows() {
        var dane = navigator.userAgentData;
        var platforma = (dane && dane.platform) || navigator.platform || "";
        return /win/i.test(platforma);
    }

    function dopasujSciezkiDoSystemu() {
        if (!toWindows()) {
            return;
        }
        var warianty = document.querySelectorAll("[data-system]");
        Array.prototype.forEach.call(warianty, function (wariant) {
            wariant.hidden = wariant.dataset.system !== "windows";
        });
    }

    // Skrypt ładowany z „defer”, więc DOM jest już sparsowany.
    dopasujSciezkiDoSystemu();
})();
