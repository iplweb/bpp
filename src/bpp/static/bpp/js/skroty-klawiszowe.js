/**
 * Preferencja skrotow jednoznakowych (WCAG 2.1.4 Character Key Shortcuts).
 *
 * Kryterium wymaga, zeby skrot zlozony z samych znakow drukowalnych dalo sie
 * wylaczyc, przemapowac albo ograniczyc do focusa komponentu. Skrot `/`
 * otwierajacy wyszukiwarke globalna wisi na `document`, wiec wybieramy
 * pierwsza droge.
 *
 * BPP w czesci publicznej nie ma kont uzytkownikow (GitHub i Gmail trzymaja
 * taka preferencje w profilu), wiec zapisujemy ja w localStorage. Kryterium
 * nie wymaga trwalosci miedzy urzadzeniami — tylko istnienia mechanizmu.
 *
 * Domyslka: WLACZONE. Brak wpisu nie moze zmieniac zachowania nikomu, kto
 * nic nie ustawil.
 */
(function (window) {
    "use strict";

    var KLUCZ = "bpp.skrotyJednoznakowe";
    var ETYKIETA_WL = "Skróty klawiszowe: włączone";
    var ETYKIETA_WYL = "Skróty klawiszowe: wyłączone";
    var stanAwaryjny = null;  // Fallback w pamięci gdy localStorage niedostępny

    function bppSkrotyWlaczone() {
        if (stanAwaryjny !== null) {
            return stanAwaryjny;
        }
        try {
            return window.localStorage.getItem(KLUCZ) !== "0";
        } catch (e) {
            // Tryb prywatny, wylaczone ciasteczka, wyczerpany limit. Fallbacku
            // z pamieci NIE czytamy tu ponownie: warunek wyzej juz zwrocil
            // `stanAwaryjny`, jesli byl ustawiony, wiec w tym miejscu jest on
            // zawsze `null`. Zostaje domyslka — skroty wlaczone.
            return true;
        }
    }

    function bppUstawSkroty(wlaczone) {
        try {
            window.localStorage.setItem(KLUCZ, wlaczone ? "1" : "0");
            stanAwaryjny = null;  // Zapis się powiedział — czyść fallback
        } catch (e) {
            // Zapis niemozliwy (tryb prywatny, limit, itp.) — trzymaj
            // stan w pamięci sesji. Przełącznik będzie działa w bieżącej
            // sesji, choć preferencja nie przetrwa przeładowania.
            stanAwaryjny = !!wlaczone;
        }
        return !!wlaczone;
    }

    function bppPodepnijPrzelacznikSkrotow(el) {
        if (!el) {
            return;
        }

        function odswiez() {
            var wl = bppSkrotyWlaczone();
            el.setAttribute("aria-pressed", wl ? "true" : "false");
            el.textContent = wl ? ETYKIETA_WL : ETYKIETA_WYL;
        }

        el.addEventListener("click", function () {
            bppUstawSkroty(!bppSkrotyWlaczone());
            odswiez();
        });

        odswiez();
    }

    window.bppSkrotyWlaczone = bppSkrotyWlaczone;
    window.bppUstawSkroty = bppUstawSkroty;
    window.bppPodepnijPrzelacznikSkrotow = bppPodepnijPrzelacznikSkrotow;
})(typeof window !== "undefined" ? window : this);
