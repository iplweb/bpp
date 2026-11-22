"""Dyscypliny autorów bez przypisania na rok pracy (FD#620).

W kroku „Dopasowanie autorów" operator może wybrać autorowi, który nie ma
przypisanej dyscypliny na rok publikacji, jedną z typowych dyscyplin uczelni
(``bpp.util.typowe_dyscypliny``). Walidacja rekordu ``*_Autor`` wymaga, żeby
autor miał na ten rok przypisanie do wybranej dyscypliny
(``Autor_Dyscyplina``) — dlatego przy tworzeniu rekordu zakładamy takie
przypisanie, z wpisem w historii autora.

Autora, który MA przypisanie na ten rok (do innej dyscypliny), nie ruszamy:
zmiana jego dyscyplin to decyzja kadrowa, nie importu.
"""

from bpp.models import Autor_Dyscyplina
from bpp.wersjonowanie import zapewnij_wersje_poczatkowa

from .historia import komunikat_dyscypliny, zapisz_utworzenie, zapisz_zmiane
from .models import ImportedAuthor


def ma_przypisanie_na_rok(autor, rok):
    """Czy autor ma jakiekolwiek przypisanie dyscypliny na ``rok``."""
    if autor is None or not rok:
        return True
    return Autor_Dyscyplina.all_objects.filter(autor=autor, rok=rok).exists()


def przypisz_brakujace_dyscypliny(session, record, user):
    """Utwórz ``Autor_Dyscyplina`` (autor, rok pracy, wybrana dyscyplina)
    dla dopasowanych autorów sesji, którzy nie mają przypisania na rok
    ``record``.

    Wołać w transakcji tworzenia rekordu (już zapisanego), PRZED dodaniem
    autorów do rekordu. Każde przypisanie dostaje wpis w historii (dodanie
    przypisania + zmiana autora) w imieniu ``user`` — operatora importu,
    który wybrał dyscyplinę. Zwraca listę utworzonych przypisań.
    """
    utworzone = []
    rok = record.rok
    if not rok:
        return utworzone

    autorzy = (
        session.authors.exclude(match_status=ImportedAuthor.MatchStatus.UNMATCHED)
        .exclude(matched_autor=None)
        .exclude(matched_jednostka=None)
        .exclude(matched_dyscyplina=None)
        .select_related("matched_autor", "matched_dyscyplina")
        .order_by("order")
    )
    for imported in autorzy:
        autor = imported.matched_autor
        if ma_przypisanie_na_rok(autor, rok):
            continue
        zapewnij_wersje_poczatkowa(autor)
        ad = Autor_Dyscyplina.objects.create(
            autor=autor,
            rok=rok,
            dyscyplina_naukowa=imported.matched_dyscyplina,
        )
        komunikat = komunikat_dyscypliny(
            session, record, imported.matched_dyscyplina, rok, user
        )
        zapisz_utworzenie(user, ad, komunikat)
        zapisz_zmiane(user, autor, komunikat)
        utworzone.append(ad)
    return utworzone
