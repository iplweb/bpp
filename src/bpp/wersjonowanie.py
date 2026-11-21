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
* ``IloscUdzialowDlaAutoraZaRok`` to dane wyliczane — nieśledzone,
* pola soft-delete (``deleted_at``, ``restored_at``, ``transaction_id``)
  NIE są wersjonowane. Kosz to osobny przepływ (``Autor.delete()`` /
  ``restore()``: guard, ``SoftDeleteLog``, kolejka PBN). Gdyby te pola były
  w wersji, „przywróć wersję" sprzed skasowania po cichu wyjąłby autora
  z kosza (albo do niego wrzucił) z pominięciem tego przepływu.

``aktualna_jednostka``/``aktualna_funkcja`` wylicza trigger na
``bpp_autor_jednostka``; po przywróceniu wersji trzeba je przeliczyć
(``przelicz_aktualna_jednostke``), bo wersja zawiera wartości historyczne.
"""

import getpass
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from types import SimpleNamespace

import reversion
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import F
from reversion.models import Version

from bpp.models import Autor, Autor_Jednostka, WybranaPublikacjaAutora

KOMENTARZ_WERSJI_POCZATKOWEJ = (
    "Stan sprzed pierwszej zarejestrowanej zmiany (zapisany automatycznie)."
)

if not reversion.is_registered(WybranaPublikacjaAutora):
    reversion.register(WybranaPublikacjaAutora)

#: Pola kosza NIE wchodzą do wersji żadnego modelu z koszem: przywrócenie
#: wersji „z kosza" żywego rekordu (albo odwrotnie) ominęłoby
#: ``delete()``/``restore()`` i zderzyło się z triggerem zamrożenia kosza.
#: Modele rejestrowane przez ``VersionAdmin`` (np. ``Uczelnia``) wyłączają je
#: w ``HistoriaWersjiMixin.reversion_register``.
POLA_KOSZA = ("deleted_at", "restored_at", "transaction_id")

if not reversion.is_registered(Autor):
    reversion.register(
        Autor,
        exclude=("search", *POLA_KOSZA),
        follow=("wybrane_publikacje",),
    )


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


# Użytkownik, któremu przypisuje się historię rekordów tworzonych poza
# adminem (importy, zadania Celery). Ustawiany przez ``jako_uzytkownik``
# na wejściu do importu, w którym znamy operatora (widok, sesja importu,
# właściciel pliku). Gdy nie jest ustawiony — konto systemowe.
_uzytkownik_historii = ContextVar("uzytkownik_historii", default=None)

ZNACZNIK_KONTA_SYSTEMOWEGO = (
    "Konto systemowe: autor wpisów historii rekordów utworzonych przez "
    "importy uruchomione bez zalogowanego użytkownika (polecenia "
    "manage.py, zadania w tle). Utworzone automatycznie; nie służy do "
    "logowania."
)


@contextmanager
def jako_uzytkownik(user):
    """Przypisz historię rekordów tworzonych w bloku do ``user``.

    ``user=None`` nic nie zmienia (zostaje wartość zewnętrzna albo konto
    systemowe) — wygodne, gdy wołający ma użytkownika tylko czasem."""
    if user is None:
        yield
        return
    token = _uzytkownik_historii.set(user)
    try:
        yield
    finally:
        _uzytkownik_historii.reset(token)


def _login_systemowy():
    """Login konta systemu operacyjnego, z którego uruchomiono proces."""
    try:
        login = getpass.getuser()
    except OSError:
        # Brak LOGNAME/USER i wpisu w passwd — np. kontener uruchomiony
        # z dowolnym UID.
        login = f"uid{os.getuid()}"
    return re.sub(r"[^\w.@+-]", "_", login)[:100] or "nieznany"


def konto_systemowe():
    """Konto, któremu przypisuje się historię, gdy nie znamy operatora.

    Tworzone leniwie (dopiero przy pierwszym rekordzie, który trzeba
    zapisać w historii), nazwane od loginu systemowego, z którego
    uruchomiono import: ``system-user-<login>``. Gdy ta nazwa jest zajęta
    przez zwykłe konto, dokłada kolejny numer (``system-user-<login>-2``…).
    Konto jest nieaktywne i bez hasła — nie da się na nie zalogować.
    """
    User = get_user_model()
    baza = f"system-user-{_login_systemowy()}"
    numer = 1
    while True:
        nazwa = baza if numer == 1 else f"{baza}-{numer}"
        istniejace = User.objects.filter(username=nazwa).first()
        if istniejace is not None:
            if istniejace.adnotacje == ZNACZNIK_KONTA_SYSTEMOWEGO:
                return istniejace
            numer += 1
            continue
        konto = User(
            username=nazwa,
            first_name="Import",
            last_name="(konto systemowe)",
            is_active=False,
            adnotacje=ZNACZNIK_KONTA_SYSTEMOWEGO,
        )
        konto.set_unusable_password()
        try:
            with transaction.atomic():
                konto.save()
        except IntegrityError:
            # Równoległy import utworzył to konto w międzyczasie — następny
            # obieg pętli je odczyta (i użyje, jeśli to konto systemowe).
            # Jeśli konta nadal nie ma, błąd dotyczył czegoś innego.
            if not User.objects.filter(username=nazwa).exists():
                raise
            continue
        return konto


def uzytkownik_historii():
    """Operator ustawiony przez ``jako_uzytkownik`` albo konto systemowe."""
    return _uzytkownik_historii.get() or konto_systemowe()


def _zapisz_wersje(user, obj, komentarz):
    """Nowa wersja ``obj`` w reversion (dla modeli wersjonowanych), ze
    świeżego odczytu z bazy — żeby zawierała pola wyliczane przez triggery
    (np. ``aktualna_jednostka`` autora, przeliczaną po każdej zmianie
    zatrudnienia)."""
    if not reversion.is_registered(type(obj)):
        return
    swiezy = type(obj)._default_manager.get(pk=obj.pk)
    with transaction.atomic(), reversion.create_revision():
        reversion.add_to_revision(swiezy)
        reversion.set_user(user)
        reversion.set_comment(komentarz)


def zarejestruj_utworzenie(user, obj, komentarz):
    """Zarejestruj rekord ``obj`` utworzony poza adminem (importer, task itp.):
    wpis ``LogEntry`` ADDITION + — dla modeli wersjonowanych — pierwsza
    wersja w reversion.

    Bez tego rekord „pojawia się znikąd": strona „Historia" w adminie jest
    pusta, nie wiadomo kto i kiedy go dodał. Wołać PO zapisie (i po zapisie
    powiązań, które mają być w wersji).

    ``user=None`` — operator z ``jako_uzytkownik`` albo konto systemowe.

    Nie wołać wewnątrz aktywnego bloku ``reversion.create_revision`` —
    zagnieżdżony blok scaliłby się z zewnętrznym (jedna rewizja z
    użytkownikiem i komentarzem ostatniego wywołania)."""
    user = user or uzytkownik_historii()
    _zapisz_wersje(user, obj, komentarz)
    LogEntry.objects.log_actions(
        user.pk,
        [obj],
        ADDITION,
        change_message=komentarz,
        single_object=True,
    )


@contextmanager
def zmiana_rekordu(user, obj, komentarz):
    """Zarejestruj zmianę ``obj`` wykonaną w bloku poza adminem (importer,
    task itp.): wpis ``LogEntry`` CHANGE + — dla modeli wersjonowanych —
    nowa wersja w reversion.

    Wersja jest konieczna, nie tylko ozdobna: strona „Historia" modeli
    wersjonowanych pokazuje wersje, a ``LogEntry`` wyłącznie sprzed pierwszej
    wersji (``HistoriaWersjiMixin``) — sam ``LogEntry`` byłby tam niewidoczny.
    Przed blokiem zapisuje stan wyjściowy (``zapewnij_wersje_poczatkowa``),
    żeby pierwszą taką zmianę dało się cofnąć.

    Blok dostaje obiekt z polami ``pomin`` i ``komentarz``; ustaw
    ``pomin = True``, gdy okazało się, że nic się nie zmieniło — wtedy nic nie
    zostanie zapisane. ``komentarz`` można uzupełnić w bloku (np. o liczby
    przeniesionych rekordów, znane dopiero po zmianie).
    ``user=None`` — operator z ``jako_uzytkownik`` albo konto systemowe.
    Nie wołać wewnątrz aktywnego ``reversion.create_revision``.
    """
    if reversion.is_registered(type(obj)):
        zapewnij_wersje_poczatkowa(obj)
    zmiana = SimpleNamespace(pomin=False, komentarz=komentarz)
    yield zmiana
    if zmiana.pomin:
        return
    user = user or uzytkownik_historii()
    _zapisz_wersje(user, obj, zmiana.komentarz)
    LogEntry.objects.log_actions(
        user.pk,
        [obj],
        CHANGE,
        change_message=zmiana.komentarz,
        single_object=True,
    )


@contextmanager
def zmiany_rekordow(user, model, pks, komentarz, select_related=()):
    """Hurtowy wariant ``zmiana_rekordu`` dla zbiorczych zmian poza adminem
    (przemapowania, scalanie, ``.update()`` na wielu rekordach): po bloku
    każdy rekord ``model`` o kluczu z ``pks`` dostaje wpis ``LogEntry``
    CHANGE (jeden ``bulk_create``), a dla modeli wersjonowanych — wersję
    początkową przed blokiem (``zapewnij_wersje_poczatkowe``) i własną
    wersję po nim (``zapisz_wersje_utworzenia`` — osobna rewizja na rekord,
    żeby cofnięcie jednego nie cofało pozostałych).

    Pola ``pomin``/``komentarz`` obiektu z bloku — jak w ``zmiana_rekordu``.
    ``select_related`` — relacje potrzebne do ``__str__`` (``object_repr``).
    Nie wołać wewnątrz aktywnego ``reversion.create_revision``.
    """
    pks = list(pks)
    wersjonowany = reversion.is_registered(model)
    if wersjonowany and pks:
        zapewnij_wersje_poczatkowe(model, pks, select_related=select_related)
    zmiana = SimpleNamespace(pomin=False, komentarz=komentarz)
    yield zmiana
    if zmiana.pomin or not pks:
        return
    user = user or uzytkownik_historii()
    if wersjonowany:
        zapisz_wersje_utworzenia(
            model,
            pks,
            user=user,
            komentarz=zmiana.komentarz,
            select_related=select_related,
        )
    obiekty = list(
        model._default_manager.filter(pk__in=pks).select_related(*select_related)
    )
    if obiekty:
        LogEntry.objects.log_actions(
            user.pk,
            obiekty,
            CHANGE,
            change_message=zmiana.komentarz,
            single_object=False,
        )


def zarejestruj_usuniecie(user, obj, komentarz):
    """Wpis ``LogEntry`` DELETION dla rekordu usuwanego poza adminem. Wołać
    PRZED ``delete()`` (potrzebny ``pk`` i ``str(obj)``)."""
    user = user or uzytkownik_historii()
    LogEntry.objects.log_actions(
        user.pk, [obj], DELETION, change_message=komentarz, single_object=True
    )


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


def zapisz_wersje_utworzenia(model, pks, *, user, komentarz, select_related=()):
    """Zapisz wersję „utworzenia” rekordów ``model`` o kluczach ``pks``,
    stworzonych z pominięciem ``save()`` (np. ``bulk_create`` w generatorze
    danych demo) — dzięki niej strona „Historia" pokazuje, kto i czym
    utworzył rekord.

    KAŻDY rekord dostaje WŁASNĄ rewizję. Rewizja zbiorcza byłaby tańsza,
    ale przywrócenie wersji w adminie odwraca CAŁĄ rewizję
    (``revision.revert``) — cofnięcie jednego rekordu po cichu cofnęłoby
    wszystkie pozostałe z tej samej paczki. Koszt to kilka zapytań na
    rekord; śledzone relacje i ``select_related`` (relacje potrzebne do
    ``__str__``) są pobierane hurtowo, raz na wywołanie.

    Jak ``zapewnij_wersje_poczatkowe`` — nie wolno wołać wewnątrz aktywnej
    rewizji.
    """
    if reversion.is_active():
        raise WersjaPoczatkowaWAktywnejRewizji(
            "Wersję utworzenia trzeba zapisać poza aktywną rewizją reversion."
        )
    obiekty = list(
        model._default_manager.filter(pk__in=list(pks))
        .select_related(*select_related)
        .prefetch_related(*sledzone_relacje(model))
    )
    for obiekt in obiekty:
        with transaction.atomic(), reversion.create_revision():
            reversion.add_to_revision(obiekt)
            reversion.set_user(user)
            reversion.set_comment(komentarz)
