"""Wersjonowanie rekordów (django-reversion) — rejestracja i pomocniki.

Historia zmian ``Autor`` jest widoczna w adminie (przycisk „Historia" na
stronie edycji autora) i pozwala przywrócić dowolną wcześniejszą wersję —
zarówno po edycji w adminie, jak i po samodzielnej edycji profilu przez
autora na stronie (biogram, zdjęcie, profile zewnętrzne, wyróżnione prace).

Rejestracja jest jawna (a nie automatyczna przez ``VersionAdmin``), bo:

* ``search`` (tsvector) liczy trigger bazy — nie ma sensu go przechowywać
  ani przywracać (trigger i tak go nadpisze przy zapisie),
* ``IloscUdzialowDlaAutoraZaRok`` to dane wyliczane (inline tylko do
  odczytu) — przywrócenie wersji z ``delete=True`` skasowałoby nowsze
  wyliczenia, więc NIE są śledzone razem z autorem.
"""

from contextlib import contextmanager

import reversion
from django.contrib.admin.models import CHANGE, LogEntry
from django.db import transaction
from reversion.models import Version

from bpp.models import (
    Autor,
    Autor_Absencja,
    Autor_Dyscyplina,
    Autor_Jednostka,
    WybranaPublikacjaAutora,
)

KOMENTARZ_WERSJI_POCZATKOWEJ = (
    "Stan sprzed pierwszej zarejestrowanej zmiany (zapisany automatycznie)."
)

for _model in (
    Autor_Jednostka,
    Autor_Dyscyplina,
    Autor_Absencja,
    WybranaPublikacjaAutora,
):
    if not reversion.is_registered(_model):
        reversion.register(_model)

if not reversion.is_registered(Autor):
    reversion.register(
        Autor,
        exclude=("search",),
        follow=(
            "autor_jednostka_set",
            "autor_dyscyplina_set",
            "autor_absencja_set",
            "wybrane_publikacje",
        ),
    )


def zapewnij_wersje_poczatkowa(obj):
    """Zapisz bieżący (sprzed zmiany) stan ``obj``, jeśli nie ma on wersji.

    Rekordy sprzed włączenia wersjonowania nie mają żadnej wersji, a
    reversion zapisuje stan PO zmianie — bez tego pierwszej edycji nie
    dałoby się cofnąć. Wołać PRZED zapisem i POZA aktywnym blokiem
    ``create_revision`` (zagnieżdżony blok scaliłby się z zewnętrznym
    i zapisał stan po zmianie).
    """
    if obj is None or obj.pk is None:
        return
    if Version.objects.get_for_object(obj).exists():
        return
    swiezy = type(obj)._default_manager.filter(pk=obj.pk).first()
    if swiezy is None:
        return
    with transaction.atomic(), reversion.create_revision():
        reversion.add_to_revision(swiezy)
        # Bez użytkownika — to nie jest niczyja zmiana, tylko punkt odniesienia.
        reversion.set_comment(KOMENTARZ_WERSJI_POCZATKOWEJ)


@contextmanager
def zmiana_ze_strony(user, obj, komentarz):
    """Zarejestruj zmianę ``obj`` wykonaną poza adminem (np. samodzielna
    edycja profilu): nowa wersja w reversion + wpis ``LogEntry``.

    Dzięki temu zmiana jest widoczna na stronie „Historia" w adminie (kto,
    kiedy, co) i można z niej wrócić do poprzedniego stanu, a filtry/statystyki
    oparte o ``LogEntry`` widzą ją tak samo jak edycję w adminie. Wersję
    zapisuje się PO wykonaniu bloku, więc odzwierciedla stan po zmianie
    (łącznie ze śledzonymi relacjami, np. wyróżnionymi pracami).
    """
    zapewnij_wersje_poczatkowa(obj)
    with transaction.atomic(), reversion.create_revision():
        yield
        reversion.add_to_revision(obj)
        reversion.set_user(user)
        reversion.set_comment(komentarz)
        LogEntry.objects.log_actions(
            user.pk,
            [obj],
            CHANGE,
            change_message=komentarz,
            single_object=True,
        )
