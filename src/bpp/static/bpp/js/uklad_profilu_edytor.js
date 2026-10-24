/* Kafelkowy edytor układu profilu autora — jedna lista w kolejności strony.
 *
 * Inicjuje jquery-ui .sortable na liście kafelków i re-serializuje stan
 * (kolejność + szerokość + widoczność + limit) do ukrytego inputa na KAŻDĄ
 * zmianę: drag-drop, toggle checkboxa, zmiana szerokości lub limitu.
 * Serializowany kształt:
 *   [{"klucz": str, "szerokosc": "pol"|"cala", "widoczna": bool,
 *     "limit": int|null}, ...]
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
            var $limit = $kafelek.find(".uklad-limit-select");
            var limit = null;
            if ($limit.length) {
                limit = parseInt($limit.val(), 10);
            }
            dane.push({
                klucz: String($kafelek.data("klucz")),
                szerokosc: String($kafelek.find(".uklad-szerokosc-select").val()),
                widoczna: !!$kafelek.find(".uklad-widoczna").prop("checked"),
                limit: limit
            });
        });
        $edytor.find(".uklad-profilu-wartosc").val(JSON.stringify(dane));
    }

    function inicjuj($edytor) {
        if ($.fn.sortable) {
            $edytor.find(".uklad-profilu-lista").sortable({
                handle: ".uklad-uchwyt",
                update: function () {
                    serializuj($edytor);
                }
            });
        }

        $edytor.on(
            "change",
            ".uklad-widoczna, .uklad-szerokosc-select, .uklad-limit-select",
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
