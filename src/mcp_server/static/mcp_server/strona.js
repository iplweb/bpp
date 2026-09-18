// Strona /mcp/: kopiowanie promptu, adresów i wklejek kliknięciem w pole.
// Klikalny jest cały kontener z atrybutem data-mcp-kopiuj="<id>"; przycisk
// w rogu to ta sama akcja, tyle że osiągalna z klawiatury.
(function () {
    "use strict";

    // Widzący dostają potwierdzenie zmianą ikony (schowek -> „ptaszek”),
    // czytniki ekranu — tekstem w obszarze aria-live.
    function pokazKomunikat(pojemnik, tekst, udane) {
        var komunikat = pojemnik.querySelector(".mcp-strona__komunikat");
        if (komunikat) {
            komunikat.textContent = tekst;
        }
        var przycisk = pojemnik.querySelector(".mcp-strona__kopiuj");
        var ikona = pojemnik.querySelector(".mcp-strona__kopiuj-ikona");
        if (udane && przycisk && ikona) {
            przycisk.classList.add("mcp-strona__kopiuj--skopiowano");
            ikona.classList.replace("fi-clipboard", "fi-check");
        }
        window.setTimeout(function () {
            if (komunikat) {
                komunikat.textContent = "";
            }
            if (przycisk && ikona) {
                przycisk.classList.remove("mcp-strona__kopiuj--skopiowano");
                ikona.classList.replace("fi-check", "fi-clipboard");
            }
        }, 2000);
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
    });

    // Skrypt ładowany z „defer”, więc DOM jest już sparsowany.
    dopasujSciezkiDoSystemu();
})();
