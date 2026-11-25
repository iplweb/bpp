"""Blokada wiersza rekordu na czas zapisu spoza formularza admina."""


def zablokuj_rekord(rekord):
    """``SELECT … FOR UPDATE`` na wierszu rekordu — wołać jako PIERWSZE
    zapytanie transakcji, która zmienia rekord albo jego autorów.

    Zapis rekordu z punktacją dyscyplin najpierw przelicza tabele pamięci
    podręcznej, potem blokuje wiersz rekordu; zadanie przeliczające w tle
    robi odwrotnie. Formularz rekordu blokuje więc rekord na samym początku
    (``bpp.admin.helpers.mixins.BlokujRekordPrzedZapisemMixin``, Rollbar
    #5363) — zapis poza formularzem musi zachować tę samą kolejność blokad."""
    list(
        type(rekord)
        ._base_manager.select_for_update(of=("self",))
        .filter(pk=rekord.pk)
        .values_list("pk", flat=True)
    )
