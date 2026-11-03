"""Porządki sortowania raportu — wybierane przez użytkownika w formularzu.

Domyślnie kolejność wierszy jest własnością tabeli ``flexible_reports.Table``
(inline ``ColumnOrder``: rok malejąco, potem opis). FD467 poprosił o spis
uporządkowany wg nazwisk autorów — czyli o wybór w czasie generowania, nie o
drugą tabelę. Realizuje to ``Report.set_order_by()``, który nadpisuje
``ColumnOrder`` na jeden render.

Moduł jest wspólnym źródłem prawdy dla formularza (etykiety wyborów) i widoku
(pola ORM), analogicznie do ``poziomy.py``. Rozdzielenie ich groziłoby cichym
rozjechaniem: formularz oferowałby wariant, którego widok nie zna, i raport po
prostu wychodziłby posortowany domyślnie.
"""

DOMYSLNE = "domyslne"
WG_AUTOROW = "autorzy"

WYBORY = [
    (DOMYSLNE, "Rok (malejąco), potem opis bibliograficzny"),
    (WG_AUTOROW, "Nazwiska autorów (alfabetycznie)"),
]

# ``opis_bibliograficzny_autorzy_cache`` to ArrayField ["Nazwisko Imiona", ...]
# w kolejności autorstwa, a PostgreSQL porównuje tablice element po elemencie —
# sortowanie po nim daje więc porządek wg nazwiska PIERWSZEGO autora, z
# kolejnymi autorami jako rozstrzygnięciem remisu.
#
# To jedyne miejsce, w którym "nazwisko pierwszego autora" jest sortowalnym
# skalarem. Przez relację (``autorzy__autor__nazwisko``) sortować się NIE da:
# JOIN po relacji wielowartościowej zduplikowałby wiersze, a ``Column.clean()``
# i tak odrzuca taką ścieżkę w dot-notation.
#
# ``tytul_oryginalny_sort`` na końcu nie jest ozdobą: bez niego dwie prace tego
# samego autora z tego samego roku mają kolejność niezdeterminowaną, więc ten
# sam raport wygenerowany dwa razy potrafiłby się różnić.
WG_AUTOROW_POLA = (
    "opis_bibliograficzny_autorzy_cache",
    "rok",
    "tytul_oryginalny_sort",
)

# Tylko warianty nadpisujące. Brak klucza (w tym ``DOMYSLNE``) = zostaw
# ``ColumnOrder`` tabeli w spokoju.
PORZADKI = {
    WG_AUTOROW: WG_AUTOROW_POLA,
}


def pola_dla(wybor):
    """Pola ORM dla wariantu z querystringa, albo ``None`` gdy bez nadpisania."""
    return PORZADKI.get(wybor)
