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


#: Relacje śledzone razem z modelem (``follow`` z ``reversion.register``).
#: Trzymane po stronie BPP, bo reversion nie udostępnia ich publicznie —
#: potrzebne do ``prefetch_related`` przy hurtowym zapisie wersji. Modele
#: rejestrowane automatycznie przez ``VersionAdmin`` dopisuje tu
#: ``HistoriaWersjiMixin.reversion_register``; brak wpisu = brak prefetchu
#: (wolniej, ale poprawnie). Zgodność z ``reversion.register`` wyżej
#: pilnuje test (wersja autora zawiera jego wyróżnione prace).
FOLLOW_REVERSION = {
    WybranaPublikacjaAutora: (),
    Autor: ("wybrane_publikacje",),
}


def sledzone_relacje(model):
    """Relacje ``model`` zapisywane w wersjach razem z nim (do prefetchu)."""
    return FOLLOW_REVERSION.get(model, ())


class WersjaPoczatkowaWAktywnejRewizji(RuntimeError):
    """``zapewnij_wersje_poczatkowe`` zawołane wewnątrz aktywnej rewizji."""


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

    NIE wolno wołać wewnątrz aktywnego ``create_revision``: zagnieżdżony
    blok reversion scala się z zewnętrznym, a późniejsze ``add_to_revision``
    tego samego obiektu nadpisałoby stan „przed” stanem „po” — po cichu
    znikałaby możliwość cofnięcia zmiany. Dlatego wtedy rzucamy
    ``WersjaPoczatkowaWAktywnejRewizji``. Akcje masowe admina oznaczone
    ``zapisuje_historie`` wykonują się bez rewizji z ``changelist_view``
    (patrz ``HistoriaWersjiMixin.create_revision``).
    """
    if reversion.is_active():
        raise WersjaPoczatkowaWAktywnejRewizji(
            "Wersję początkową trzeba zapisać PRZED otwarciem rewizji "
            "reversion — w aktywnej rewizji stan „przed” scaliłby się ze "
            "stanem „po”."
        )
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
    obiekty = list(
        model._default_manager.filter(pk__in=brakujace)
        .select_related(*select_related)
        .prefetch_related(*sledzone_relacje(model))
    )
    if not obiekty:
        return

    with transaction.atomic(), reversion.create_revision():
        for obiekt in obiekty:
            reversion.add_to_revision(obiekt)
        # Bez użytkownika — to nie jest niczyja zmiana, tylko punkt
        # odniesienia.
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
