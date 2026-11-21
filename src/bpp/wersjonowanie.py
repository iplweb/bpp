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

import getpass
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from types import SimpleNamespace

import reversion
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
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

    Blok dostaje obiekt z polem ``pomin``; ustaw ``pomin = True``, gdy
    okazało się, że nic się nie zmieniło — wtedy nic nie zostanie zapisane.
    ``user=None`` — operator z ``jako_uzytkownik`` albo konto systemowe.
    Nie wołać wewnątrz aktywnego ``reversion.create_revision``.
    """
    if reversion.is_registered(type(obj)):
        zapewnij_wersje_poczatkowa(obj)
    zmiana = SimpleNamespace(pomin=False)
    yield zmiana
    if zmiana.pomin:
        return
    user = user or uzytkownik_historii()
    _zapisz_wersje(user, obj, komentarz)
    LogEntry.objects.log_actions(
        user.pk,
        [obj],
        CHANGE,
        change_message=komentarz,
        single_object=True,
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
