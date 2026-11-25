/*
 * Formularz patentu w module redagowania (FD#449): pole „Kraj” dotyczy tylko
 * patentów zagranicznych, więc chowamy jego wiersz, dopóki „Typ patentu” nie
 * jest ustawiony na „zagraniczny”. Warstwa wyłącznie wizualna — regułę
 * egzekwuje serwer przy zapisie. Wiersza z wpisaną wartością albo z błędem
 * NIE chowamy, żeby redaktor widział, co ma poprawić.
 */
(function () {
    "use strict";

    function init() {
        var typ = document.getElementById("id_typ_patentu");
        var kraj = document.getElementById("id_kraj");
        if (!typ || !kraj) {
            return;
        }
        var wiersz = kraj.closest(".grp-row, .form-row");
        if (!wiersz) {
            return;
        }

        function odswiez() {
            var pokaz = typ.value === "zagraniczny" || kraj.value !== "" ||
                wiersz.querySelector(".errorlist") !== null;
            wiersz.style.display = pokaz ? "" : "none";
        }

        typ.addEventListener("change", odswiez);
        odswiez();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
