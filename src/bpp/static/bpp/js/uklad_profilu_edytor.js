/* Kafelkowy edytor układu profilu autora (§3.2).
 *
 * Inicjuje jquery-ui .sortable() na liście kafelków i re-serializuje stan
 * (kolejność + widoczność + limit) do ukrytego inputa na KAŻDĄ zmianę:
 * drag-drop, toggle checkboxa, zmiana limitu. Serializowany kształt to ten
 * sam schemat JSON, który konsumuje reszta kodu:
 *   [{"klucz": str, "widoczna": bool, "limit": int|null}, ...]
 *
 * Dependency-light: tylko django.jQuery (admin) + jquery-ui sortable.
 */
(function () {
    "use strict";

    var $ = (window.django && window.django.jQuery) || window.jQuery;
    if (!$) {
        return;
    }

    function serializuj($edytor) {
        var dane = [];
        $edytor.find(".uklad-profilu-kafelek").each(function () {
            var $kafelek = $(this);
            var klucz = $kafelek.data("klucz");
            var widoczna = $kafelek.find(".uklad-widoczna").prop("checked");
            var $select = $kafelek.find(".uklad-limit-select");
            var limit = null;
            if ($select.length) {
                limit = parseInt($select.val(), 10);
            }
            dane.push({
                klucz: String(klucz),
                widoczna: !!widoczna,
                limit: limit
            });
        });
        $edytor.find(".uklad-profilu-wartosc").val(JSON.stringify(dane));
    }

    function inicjuj($edytor) {
        var $lista = $edytor.find(".uklad-profilu-lista");

        if ($.fn.sortable) {
            $lista.sortable({
                handle: ".uklad-uchwyt",
                axis: "y",
                update: function () {
                    serializuj($edytor);
                }
            });
        }

        $edytor.on(
            "change",
            ".uklad-widoczna, .uklad-limit-select",
            function () {
                serializuj($edytor);
            }
        );

        /* Stan początkowy ukrytego inputa jest już poprawny (render),
         * ale serializujemy raz, żeby zniwelować ewentualną rozbieżność
         * porządku DOM vs. wartość. */
        serializuj($edytor);
    }

    $(function () {
        $(".uklad-profilu-edytor").each(function () {
            inicjuj($(this));
        });
    });
})();
