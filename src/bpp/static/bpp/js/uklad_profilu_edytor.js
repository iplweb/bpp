/* Kafelkowy edytor układu profilu autora — DWIE połączone strefy (§3.2).
 *
 * Inicjuje jquery-ui .sortable({connectWith}) na OBU listach (lewa / prawa),
 * tak że kafelki da się przeciągać MIĘDZY kolumnami, i re-serializuje stan
 * (kolumna + kolejność + widoczność + limit) do ukrytego inputa na KAŻDĄ
 * zmianę: drag-drop (w obrębie listy i między listami), toggle checkboxa,
 * zmiana limitu. Kolumna kafelka wynika z `data-kolumna` listy, w której
 * kafelek aktualnie jest. Serializowany kształt:
 *   [{"klucz": str, "kolumna": "lewa"|"prawa", "widoczna": bool,
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
        $edytor.find(".uklad-profilu-lista").each(function () {
            var kolumna = $(this).data("kolumna");
            $(this).find(".uklad-profilu-kafelek").each(function () {
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
                    kolumna: String(kolumna),
                    widoczna: !!widoczna,
                    limit: limit
                });
            });
        });
        $edytor.find(".uklad-profilu-wartosc").val(JSON.stringify(dane));
    }

    function inicjuj($edytor) {
        var $listy = $edytor.find(".uklad-profilu-lista");

        if ($.fn.sortable) {
            $listy.sortable({
                handle: ".uklad-uchwyt",
                /* Połącz obie strefy, by przenosić kafelki między kolumnami. */
                connectWith: ".uklad-profilu-lista",
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
