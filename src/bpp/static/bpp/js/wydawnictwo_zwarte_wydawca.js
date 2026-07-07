/*
 * Freshdesk #385 — Rozdział: podświetlanie wymaganego pola "wydawca".
 *
 * Gdy rekord wydawnictwa zwartego ma wskazane wydawnictwo nadrzędne
 * (czyli jest rozdziałem), pole "wydawca" jest istotne i łatwo je
 * przeoczyć. Ten skrypt podświetla je wizualnie jako wymagane, dopóki
 * pozostaje puste. Faktyczne dziedziczenie wydawcy po wydawnictwie
 * nadrzędnym realizuje serwer (Wydawnictwo_ZwarteForm.clean) — to jest
 * wyłącznie warstwa UI i nie jest wymagana do działania mechanizmu.
 */
(function ($) {
    "use strict";

    function wydawcaInput() {
        return $("#id_wydawca");
    }

    function wydawcaRow() {
        // Wiersz formularza admina opakowujący pole wydawca (div.form-row /
        // div.field-wydawca w zależności od wersji szablonu).
        return wydawcaInput().closest(".form-row, .field-wydawca");
    }

    function nadrzedneWybrane() {
        var val = $("#id_wydawnictwo_nadrzedne").val();
        return val !== null && val !== undefined && val !== "";
    }

    function wydawcaPusty() {
        var val = wydawcaInput().val();
        return val === null || val === undefined || val === "";
    }

    function odswiezPodswietlenie() {
        var row = wydawcaRow();
        if (!row.length) {
            return;
        }
        var wymagany = nadrzedneWybrane() && wydawcaPusty();
        row.toggleClass("bpp-wydawca-wymagany", wymagany);

        var label = row.find("label").first();
        if (!label.length) {
            return;
        }
        var marker = label.find(".bpp-wydawca-required-marker");
        if (wymagany) {
            if (!marker.length) {
                label.append(
                    ' <span class="bpp-wydawca-required-marker" ' +
                        'title="Przy rozdziale podaj wydawcę (lub zostanie ' +
                        'odziedziczony po wydawnictwie nadrzędnym)">' +
                        "❗ wymagane przy rozdziale</span>"
                );
            }
        } else {
            marker.remove();
        }
    }

    $(function () {
        odswiezPodswietlenie();
        // django-autocomplete-light (Select2) emituje "change" na ukrytym
        // <select>; nasłuchujemy obu pól.
        $(document).on(
            "change",
            "#id_wydawnictwo_nadrzedne, #id_wydawca",
            odswiezPodswietlenie
        );
    });
})(window.django ? window.django.jQuery : window.jQuery);
