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
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.db.models import F
from reversion.models import Version

from bpp.models import Autor, Autor_Jednostka, WybranaPublikacjaAutora
from bpp.zrodlo_zmian import (
    ZRODLO_API,
    ZRODLO_NARZEDZIE,
    ZRODLO_STRONA,
    biezace_zrodlo_zmian,
    wersje_zapisane_hurtowo,
    zrodlo_zmian,
)

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


#: Pola wyłączone z wersji danego modelu (``exclude`` z rejestracji). Przy
#: przywracaniu wersji reversion zapisuje obiekt surowo (``raw=True``), więc
#: pole spoza wersji dostaje wartość domyślną modelu — wolno tu wpisać
#: wyłącznie pola, które baza i tak przelicza (trigger ``BEFORE``, denorm)
#: albo które mogą być puste. Pilnuje tego test przywracania każdego modelu.
POLA_POZA_WERSJA = {
    WybranaPublikacjaAutora: (),
    Autor: ("search", *POLA_KOSZA),
}


def _relacja_odwrotna(model, akcesor):
    """Model po drugiej stronie relacji odwrotnej ``model.<akcesor>``
    (klucz obcy albo ``GenericRelation``)."""
    for relacja in model._meta.related_objects:
        if relacja.get_accessor_name() == akcesor:
            return relacja.related_model
    for pole in model._meta.private_fields:
        if isinstance(pole, GenericRelation) and pole.name == akcesor:
            return pole.related_model
    raise LookupError(f"{model.__name__} nie ma relacji odwrotnej {akcesor!r}")


def zarejestruj_wersjonowanie(model, *, exclude=(), follow=()):
    """Zarejestruj ``model`` w reversion razem z relacjami ``follow``
    (akcesory relacji odwrotnych, np. ``autorzy_set``).

    Modele po drugiej stronie ``follow`` są rejestrowane bez własnych
    relacji — reversion pomija obiekty modeli niezarejestrowanych, więc bez
    tego np. autorzy publikacji nie trafiliby do wersji. Pola kosza są
    wyłączane zawsze (patrz ``POLA_KOSZA``). Ponowne wywołanie nic nie robi.
    """
    if reversion.is_registered(model):
        return
    if hasattr(model, "deleted_objects"):
        exclude = (*exclude, *POLA_KOSZA)
    for akcesor in follow:
        powiazany = _relacja_odwrotna(model, akcesor)
        if not reversion.is_registered(powiazany):
            wylaczone = POLA_KOSZA if hasattr(powiazany, "deleted_objects") else ()
            reversion.register(powiazany, exclude=wylaczone)
            FOLLOW_REVERSION.setdefault(powiazany, ())
            POLA_POZA_WERSJA.setdefault(powiazany, wylaczone)
    reversion.register(model, exclude=tuple(exclude), follow=tuple(follow))
    FOLLOW_REVERSION[model] = tuple(follow)
    POLA_POZA_WERSJA[model] = tuple(exclude)


# --- Modele edytowane w adminie (FD#587) -----------------------------------
#
# Publikacje: razem z rekordem wersjonowani są autorzy (z dyscypliną,
# afiliacją, kolejnością), streszczenia, dodatkowe tytuły, zewnętrzne bazy
# danych, granty, nagrody, pliki repozytorium (wiersze, nie treść plików)
# i powiązania ze słowami kluczowymi — przywrócenie wersji przywraca też te
# listy (pozycje dopisane później są usuwane; formularz przywracania
# pokazuje je wcześniej).
#
# Z wersji wyłączone są pola wyliczane: indeks wyszukiwania i klucz
# sortowania (trigger ``BEFORE``) oraz cache opisu i punktów (denorm,
# przeliczane przy zapisie formularza po przywróceniu).
POLA_WYLICZANE_PUBLIKACJI = (
    "search_index",
    "tytul_oryginalny_sort",
    "cached_punkty_dyscyplin",
    "opis_bibliograficzny_cache",
    "opis_bibliograficzny_autorzy_cache",
    "opis_bibliograficzny_zapisani_autorzy_cache",
)


def _pola_istniejace(model, pola):
    nazwy = {f.name for f in model._meta.concrete_fields}
    return tuple(p for p in pola if p in nazwy)


#: Relacje generyczne śledzone przy każdej publikacji, która je ma.
RELACJE_GENERYCZNE_PUBLIKACJI = (
    "granty_rekordu",
    "nagrody",
    "elementy_repozytorium",
    "slowa_kluczowe_powiazania",
)


def _relacje_istniejace(model, akcesory):
    nazwy = {f.name for f in model._meta.private_fields}
    return tuple(a for a in akcesory if a in nazwy)


def _zarejestruj_modele_bpp():
    from bpp.models import (
        Jednostka,
        Konferencja,
        Patent,
        Praca_Doktorska,
        Praca_Habilitacyjna,
        Seria_Wydawnicza,
        Wydawca,
        Wydawnictwo_Ciagle,
        Wydawnictwo_Zwarte,
        Zrodlo,
    )

    for model, follow in (
        (
            Wydawnictwo_Ciagle,
            (
                "autorzy_set",
                "streszczenia",
                "dodatkowe_tytuly",
                "zewnetrzna_baza_danych",
            ),
        ),
        (
            Wydawnictwo_Zwarte,
            (
                "autorzy_set",
                "streszczenia",
                "dodatkowe_tytuly",
                "zewnetrzna_baza_danych",
            ),
        ),
        (Patent, ("autorzy_set",)),
        (Praca_Doktorska, ()),
        (Praca_Habilitacyjna, ("publikacja_habilitacyjna_set",)),
    ):
        zarejestruj_wersjonowanie(
            model,
            exclude=_pola_istniejace(model, POLA_WYLICZANE_PUBLIKACJI),
            follow=(
                *follow,
                *_relacje_istniejace(model, RELACJE_GENERYCZNE_PUBLIKACJI),
            ),
        )

    # Słowniki. ``search`` liczy trigger; poziomy i liczbę aliasów wydawcy —
    # denorm.
    zarejestruj_wersjonowanie(
        Zrodlo,
        exclude=("search",),
        follow=("punktacja_zrodla_set", "redakcja_zrodla_set", "dyscyplina_zrodla_set"),
    )
    zarejestruj_wersjonowanie(
        Wydawca,
        exclude=("lista_poziomow", "ile_aliasow"),
        follow=("poziom_wydawcy_set",),
    )
    zarejestruj_wersjonowanie(Konferencja)
    zarejestruj_wersjonowanie(Seria_Wydawnicza)

    # Struktura. Pola drzewa MPTT (``lft``/``rght``/``tree_id``/``level``)
    # są w wersji, bo nie mogą być puste — po przywróceniu wersji drzewo
    # jest przebudowywane (``JednostkaAdmin.po_przywroceniu_wersji``).
    # Zatrudnienie autorów NIE jest śledzone (jak przy ``Autor``).
    zarejestruj_wersjonowanie(Jednostka, exclude=("search",))


_zarejestruj_modele_bpp()


@contextmanager
def _zrodlo_narzedzia():
    """Pomocniki historii zmian poza formularzami (importy, scalanie,
    przemapowania) oznaczają rewizje jako „import lub narzędzie” — chyba
    że wołający jest klientem API/MCP (wtedy zostaje jego źródło)."""
    if biezace_zrodlo_zmian()["zrodlo"] == ZRODLO_API:
        yield
        return
    with zrodlo_zmian(ZRODLO_NARZEDZIE):
        yield


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

    # Bez użytkownika — to nie jest niczyja zmiana, tylko punkt odniesienia.
    zapisz_wersje_osobno(obiekty, komentarz=KOMENTARZ_WERSJI_POCZATKOWEJ)


def _pola_wersji(model):
    """Pola zapisywane w wersji ``model`` — jak liczy je
    ``reversion.register`` (lokalne pola i m2m minus ``exclude``)."""
    if model not in POLA_POZA_WERSJA:
        raise LookupError(
            f"{model.__name__}: brak wpisu w POLA_POZA_WERSJA — zarejestruj "
            "model przez zarejestruj_wersjonowanie albo HistoriaWersjiMixin."
        )
    wylaczone = set(POLA_POZA_WERSJA[model])
    opts = model._meta.concrete_model._meta
    return tuple(
        pole.name
        for pole in opts.local_fields + opts.local_many_to_many
        if pole.name not in wylaczone
    )


def _ze_sledzonymi(obiekt, odwiedzone=None):
    """``obiekt`` i rekurencyjnie obiekty z jego śledzonych relacji
    (``FOLLOW_REVERSION``; korzysta z ``prefetch_related``)."""
    odwiedzone = set() if odwiedzone is None else odwiedzone
    klucz = (type(obiekt), obiekt.pk)
    if klucz in odwiedzone:
        return
    odwiedzone.add(klucz)
    yield obiekt
    for akcesor in sledzone_relacje(type(obiekt)):
        for powiazany in getattr(obiekt, akcesor).all():
            yield from _ze_sledzonymi(powiazany, odwiedzone)


def zapisz_wersje_osobno(obiekty, *, user=None, komentarz=""):
    """Zapisz bieżący stan każdego z ``obiekty`` jako OSOBNĄ rewizję
    (z wersjami śledzonych relacji), stałą liczbą zapytań.

    Po co osobno: przywrócenie wersji w adminie odwraca CAŁĄ rewizję
    (``revision.revert``), więc wspólna rewizja akcji masowej sprawiłaby, że
    cofnięcie jednego rekordu po cichu cofa wszystkie pozostałe — także
    z innych uczelni. ``reversion.create_revision`` na rekord kosztowałby
    kilka zapytań na rekord; tu rewizje i wersje idą dwoma ``bulk_create``.
    Śledzone relacje warto mieć w ``prefetch_related`` (``sledzone_relacje``).

    Wersje budujemy sami (format ``json``, pola jak w ``reversion.register``
    — ``_pola_wersji``), bo reversion nie ma publicznego API do hurtowego
    zapisu. Sygnały ``pre/post_revision_commit`` nie są wysyłane (BPP ich
    nie używa). Nie wołać wewnątrz aktywnej rewizji.
    """
    from django.core import serializers
    from django.utils import timezone
    from reversion.models import Revision

    if reversion.is_active():
        raise WersjaPoczatkowaWAktywnejRewizji(
            "Wersje rekordów trzeba zapisać poza aktywną rewizją reversion."
        )
    obiekty = [o for o in obiekty if o.pk is not None]
    if not obiekty:
        return

    def wersja(obiekt, rewizja):
        model = type(obiekt)
        return Version(
            revision=rewizja,
            content_type=ContentType.objects.get_for_model(model),
            object_id=str(obiekt.pk),
            db="default",
            format="json",
            serialized_data=serializers.serialize(
                "json", (obiekt,), fields=_pola_wersji(model)
            ),
            object_repr=str(obiekt),
        )

    teraz = timezone.now()
    with transaction.atomic():
        rewizje = Revision.objects.bulk_create(
            [
                Revision(date_created=teraz, user=user, comment=komentarz)
                for _ in obiekty
            ]
        )
        Version.objects.bulk_create(
            [
                wersja(powiazany, rewizja)
                for rewizja, obiekt in zip(rewizje, obiekty, strict=True)
                for powiazany in _ze_sledzonymi(obiekt)
                if reversion.is_registered(type(powiazany))
            ]
        )
        wersje_zapisane_hurtowo.send(sender=zapisz_wersje_osobno, rewizje=rewizje)


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


def opis_uzytkownika(user):
    """„Imię Nazwisko (login)” albo sam login — do treści wpisów historii."""
    if user is None:
        return "system"
    pelne = (user.get_full_name() or "").strip()
    return f"{pelne} ({user.username})" if pelne else user.username


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
    with _zrodlo_narzedzia():
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
    with _zrodlo_narzedzia():
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
        with _zrodlo_narzedzia():
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
    with (
        zrodlo_zmian(ZRODLO_STRONA),
        transaction.atomic(),
        reversion.create_revision(),
    ):
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

    KAŻDY rekord dostaje WŁASNĄ rewizję (``zapisz_wersje_osobno``) —
    cofnięcie jednego rekordu nie może cofać pozostałych z tej samej paczki.
    Śledzone relacje i ``select_related`` (relacje potrzebne do
    ``__str__``) są pobierane hurtowo, raz na wywołanie.

    Jak ``zapewnij_wersje_poczatkowe`` — nie wolno wołać wewnątrz aktywnej
    rewizji.
    """
    obiekty = list(
        model._default_manager.filter(pk__in=list(pks))
        .select_related(*select_related)
        .prefetch_related(*sledzone_relacje(model))
    )
    zapisz_wersje_osobno(obiekty, user=user, komentarz=komentarz)
