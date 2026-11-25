/*
 * Formularz patentu w module redagowania (FD#449): pola „Kraj” oraz
 * „Pierwszeństwo z polskiego patentu o nr zgłoszenia” dotyczą tylko patentów
 * zagranicznych, więc chowamy ich wiersze, dopóki „Typ patentu” nie jest
 * ustawiony na „zagraniczny”. Warstwa wyłącznie wizualna — regułę egzekwuje
 * serwer przy zapisie. Wiersza z wpisaną wartością albo z błędem NIE chowamy,
 * żeby redaktor widział, co ma poprawić.
 */
(function () {
    "use strict";

    var POLA_ZAGRANICZNE = ["id_kraj", "id_pierwszenstwo_nr_zgloszenia"];

    function init() {
        var typ = document.getElementById("id_typ_patentu");
        if (!typ) {
            return;
        }

        var pola = [];
        POLA_ZAGRANICZNE.forEach(function (id) {
            var pole = document.getElementById(id);
            var wiersz = pole && pole.closest(".grp-row, .form-row");
            if (wiersz) {
                pola.push({pole: pole, wiersz: wiersz});
            }
        });
        if (!pola.length) {
            return;
        }

        function odswiez() {
            pola.forEach(function (p) {
                var pokaz = typ.value === "zagraniczny" || p.pole.value !== "" ||
                    p.wiersz.querySelector(".errorlist") !== null;
                p.wiersz.style.display = pokaz ? "" : "none";
            });
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
