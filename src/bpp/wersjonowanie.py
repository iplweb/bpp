"""Wersjonowanie rekordów (django-reversion) — rejestracja i pomocniki.

Historia zmian ``Autor`` jest widoczna w adminie (przycisk „Historia" na
stronie edycji autora) i pozwala przywrócić dowolną wcześniejszą wersję —
zarówno po edycji w adminie, jak i po samodzielnej edycji profilu przez
autora na stronie (biogram, zdjęcie, profile zewnętrzne, wyróżnione prace).

Rejestracja jest jawna (a nie automatyczna przez ``VersionAdmin``), bo:

* ``search`` (tsvector) liczy bezwarunkowy trigger ``BEFORE INSERT OR
  UPDATE`` — nie ma sensu go przechowywać (trigger i tak go przeliczy),
* razem z autorem śledzone są TYLKO wyróżnione prace. Miejsca pracy,
  dyscypliny i absencje NIE: przywrócenie wersji z ``delete=True``
  nadpisałoby/skasowało także wiersze innych uczelni (inline zatrudnienia
  jest zawężony per uczelnia, FD#390) oraz cofnęłoby po cichu przypisania
  dyscyplin zrobione w międzyczasie (ewaluacja, sloty). Ich zmiany są
  widoczne w historii (komentarz z ``LogEntry``), ale się ich nie cofa,
* ``IloscUdzialowDlaAutoraZaRok`` to dane wyliczane — nieśledzone.

``aktualna_jednostka``/``aktualna_funkcja`` wylicza trigger na
``bpp_autor_jednostka``; po przywróceniu wersji trzeba je przeliczyć
(``przelicz_aktualna_jednostke``), bo wersja zawiera wartości historyczne.
"""

from contextlib import contextmanager

import reversion
from django.contrib.admin.models import CHANGE, LogEntry
from django.db import transaction
from django.db.models import F
from reversion.models import Version
from reversion.revisions import _stack as _stos_rewizji

from bpp.models import Autor, Autor_Jednostka, WybranaPublikacjaAutora

KOMENTARZ_WERSJI_POCZATKOWEJ = (
    "Stan sprzed pierwszej zarejestrowanej zmiany (zapisany automatycznie)."
)

if not reversion.is_registered(WybranaPublikacjaAutora):
    reversion.register(WybranaPublikacjaAutora)

if not reversion.is_registered(Autor):
    reversion.register(Autor, exclude=("search",), follow=("wybrane_publikacje",))


def przelicz_aktualna_jednostke(autor_id):
    """Przelicz ``aktualna_jednostka``/``aktualna_funkcja`` autora z bieżących
    wpisów zatrudnienia — tym samym triggerem bazy co przy zwykłej edycji
    (pusty UPDATE jednego wiersza ``bpp_autor_jednostka`` go odpala; trigger
    i tak przegląda wszystkie wpisy autora)."""
    pierwszy = (
        Autor_Jednostka.objects.filter(autor_id=autor_id)
        .values_list("pk", flat=True)
        .first()
    )
    if pierwszy is None:
        Autor.objects.filter(pk=autor_id).update(
            aktualna_jednostka=None, aktualna_funkcja=None
        )
        return
    Autor_Jednostka.objects.filter(pk=pierwszy).update(autor_id=F("autor_id"))


def zapewnij_wersje_poczatkowa(obj):
    """Zapisz bieżący (sprzed zmiany) stan ``obj``, jeśli nie ma on wersji.

    Rekordy sprzed włączenia wersjonowania nie mają żadnej wersji, a
    reversion zapisuje stan PO zmianie — bez tego pierwszej edycji nie
    dałoby się cofnąć. Wołać PRZED zapisem. Patrz
    ``zapewnij_wersje_poczatkowe``.
    """
    if obj is None or obj.pk is None:
        return
    zapewnij_wersje_poczatkowe(type(obj), [obj.pk])


def zapewnij_wersje_poczatkowe(model, pks, select_related=()):
    """Hurtowy wariant ``zapewnij_wersje_poczatkowa``: zapisz bieżący stan
    tych rekordów ``model`` o kluczach ``pks``, które nie mają żadnej wersji.

    Stała liczba zapytań niezależnie od liczby rekordów: jedno o rekordy
    z wersjami, jedno (+ prefetch śledzonych relacji) o rekordy bez wersji
    i jedna rewizja z wieloma wersjami. ``select_related`` — relacje
    potrzebne do ``__str__`` (``object_repr`` wersji), żeby nie pytać
    o nie osobno dla każdego rekordu.

    Wolno wołać także wewnątrz aktywnego ``create_revision`` (np. akcja
    admina — ``VersionAdmin.changelist_view`` owija ją w rewizję): wersję
    początkową zapisujemy wtedy z pustym stosem rewizji reversion. Inaczej
    zagnieżdżony blok scaliłby się z zewnętrznym, a późniejsze
    ``add_to_revision`` tego samego obiektu nadpisałoby stan „przed” stanem
    „po”. Transakcja bazy jest ta sama.
    """
    pks = list(pks)
    if not pks:
        return
    z_wersjami = set(
        Version.objects.get_for_model(model)
        .filter(object_id__in=[str(pk) for pk in pks])
        .values_list("object_id", flat=True)
    )
    brakujace = [pk for pk in pks if str(pk) not in z_wersjami]
    if not brakujace:
        return
    follow = reversion.revisions._get_options(model).follow
    obiekty = list(
        model._default_manager.filter(pk__in=brakujace)
        .select_related(*select_related)
        .prefetch_related(*follow)
    )
    if not obiekty:
        return

    def _zapisz():
        with transaction.atomic(), reversion.create_revision():
            for obiekt in obiekty:
                reversion.add_to_revision(obiekt)
            # Bez użytkownika — to nie jest niczyja zmiana, tylko punkt
            # odniesienia.
            reversion.set_comment(KOMENTARZ_WERSJI_POCZATKOWEJ)

    if not reversion.is_active():
        _zapisz()
        return
    # Odłóż stos rewizji na czas zapisu i przywróć go potem. Celowo NIE
    # ``contextvars.Context().run``: w świeżym kontekście Django potrafi
    # dać INNE połączenie z bazą (poza bieżącą transakcją) — zapis wersji
    # by przepadł albo poszedł obok transakcji.
    token = _stos_rewizji.set([])
    try:
        _zapisz()
    finally:
        _stos_rewizji.reset(token)


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
