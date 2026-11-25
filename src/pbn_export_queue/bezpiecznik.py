"""Bezpiecznik „lokalna kopia produkcji" dla wysyłki do PBN.

Deweloper odtwarza lokalnie kopię bazy klienta i loguje się do prawdziwego
PBN, żeby przetestować pobieranie albo wysyłkę JEDNEJ pracy. W takiej bazie
leży jednak kolejka eksportu z produkcji, a kod ma kilka automatów, które
wysyłają do PBN bez pytania. Ten moduł trzyma dwie warstwy ochrony:

1. przełącznik ``settings.PBN_WSTRZYMAJ_AUTOMATY`` (:func:`automaty_wstrzymane`)
   — sprawdzany w automatach; ręczna wysyłka go nie czyta. Na instancji
   lokalnej deweloper może automaty świadomie ODBLOKOWAĆ (strona kolejki
   eksportu albo ``run-site run --pbn-automaty wlacz``) — patrz
   :func:`ustaw_odblokowanie`,
2. :func:`wstrzymaj_kolejke` — zamyka wpisy kolejki przyniesione z produkcji
   (wołane przez komendę ``pbn_bezpiecznik_lokalnej_kopii``).

Automaty objęte przełącznikiem (wszystkie miejsca, które wysyłają do PBN bez
jawnego „wyślij ten rekord"):

- ``tasks.kolejka_ponow_wysylke_prac_po_zalogowaniu`` — po zapisaniu tokenu,
- ``tasks.queue_watchdog`` — co 10 minut z Celery beat,
- ``tasks.check_and_send_next_in_queue`` — po każdej udanej wysyłce bierze
  kolejne wpisy,
- ``operacje.zakolejkuj_wycofanie`` / ``zakolejkuj_wysylke`` — kosz
  i przywrócenie z kosza.
"""

from dataclasses import dataclass

from django.conf import settings
from django.db import connection
from django.db.models import F, TextField, Value
from django.db.models.functions import Coalesce, Concat
from django.utils import timezone

from pbn_export_queue.models import PBN_Export_Queue

#: Hosty bazy uznawane za „tę samą maszynę". Pusty host i ścieżka zaczynająca
#: się od ``/`` to gniazdo uniksowe (libpq) — też lokalne.
LOKALNE_HOSTY_BAZY = frozenset({"", "localhost", "127.0.0.1", "::1"})

KOMUNIKAT_WSTRZYMANIA = (
    "Wstrzymane przez bezpiecznik lokalnej kopii produkcji "
    "(pbn_bezpiecznik_lokalnej_kopii) — wpis przyszedł z kopią bazy i nie "
    "został wysłany z tej instancji."
)


#: Klucz constance z decyzją „odblokuj automaty". Zdefiniowany wyłącznie
#: w ``settings/local.py`` — na produkcji nie istnieje.
KLUCZ_ODBLOKOWANIA = "PBN_AUTOMATY_ODBLOKOWANE_LOKALNIE"


class PrzelacznikNiedostepny(Exception):
    """Automatów nie da się przełączać na tej instancji (produkcja, instancja
    nielokalna albo wstrzymanie wyłączone zmienną środowiskową)."""


@dataclass(frozen=True)
class StanAutomatow:
    #: Czy na tej instancji w ogóle działa wstrzymywanie (False = produkcja
    #: albo ``DJANGO_BPP_PBN_WSTRZYMAJ_AUTOMATY=0``).
    wstrzymywanie_wlaczone: bool
    wstrzymane: bool
    #: Czy stan można zmienić przełącznikiem (instancja lokalna).
    przelaczalne: bool


def _wstrzymywanie_wlaczone() -> bool:
    return bool(getattr(settings, "PBN_WSTRZYMAJ_AUTOMATY", False))


def przelacznik_dostepny(dodatkowe_lokalne_hosty=()) -> bool:
    """Przełącznik istnieje tylko tam, gdzie działa wstrzymywanie, jest klucz
    constance (ustawienia lokalne) i instancja przechodzi te same kryteria
    lokalności co komenda bezpiecznika."""
    return (
        _wstrzymywanie_wlaczone()
        and KLUCZ_ODBLOKOWANIA in getattr(settings, "CONSTANCE_CONFIG", {})
        and not powody_nielokalnosci(dodatkowe_lokalne_hosty)
    )


def automaty_wstrzymane() -> bool:
    """Czy automaty wysyłające do PBN mają na tej instancji milczeć.

    Produkcja (``PBN_WSTRZYMAJ_AUTOMATY = False``): zawsze ``False``, bez
    czytania czegokolwiek z bazy — przełącznik nie ma tam żadnego wpływu.
    Instancja lokalna: wstrzymane, chyba że deweloper je odblokował. Stan
    odblokowania leży w bazie (constance), bo pytają o niego osobne procesy
    — web i worker Celery.
    """
    if not _wstrzymywanie_wlaczone():
        return False
    if not przelacznik_dostepny():
        return True
    from constance import config

    return not getattr(config, KLUCZ_ODBLOKOWANIA)


def stan_automatow() -> StanAutomatow:
    return StanAutomatow(
        wstrzymywanie_wlaczone=_wstrzymywanie_wlaczone(),
        wstrzymane=automaty_wstrzymane(),
        przelaczalne=przelacznik_dostepny(),
    )


def ustaw_odblokowanie(odblokowane: bool, dodatkowe_lokalne_hosty=()) -> None:
    """Odblokowuje (``True``) albo wstrzymuje (``False``) automaty lokalnie."""
    if not przelacznik_dostepny(dodatkowe_lokalne_hosty):
        raise PrzelacznikNiedostepny(
            "Automatów wysyłki do PBN nie da się przełączać na tej instancji."
        )
    from constance import config

    setattr(config, KLUCZ_ODBLOKOWANIA, bool(odblokowane))


def host_bazy() -> str:
    return str(connection.settings_dict.get("HOST") or "")


def powody_nielokalnosci(dodatkowe_lokalne_hosty=()) -> list[str]:
    """Lista powodów, dla których instancja NIE wygląda na lokalną.

    Pusta lista = wygląda na lokalną. Oba warunki są twarde: produkcja ma
    ``DEBUG = False`` (``settings/production.py``) i bazę na innym hoście
    (``dbserver`` albo serwer zewnętrzny), więc do pomyłki musiałyby zawieść
    oba naraz.
    """
    powody = []
    if not settings.DEBUG:
        powody.append("DEBUG jest wyłączony (ustawienia produkcyjne)")

    host = host_bazy()
    lokalne = LOKALNE_HOSTY_BAZY | set(dodatkowe_lokalne_hosty)
    if not (host in lokalne or host.startswith("/")):
        powody.append(
            f"baza danych jest na hoście {host!r}, a nie na tej maszynie "
            "(localhost / gniazdo uniksowe)"
        )
    return powody


def wstrzymaj_kolejke() -> dict[str, int]:
    """Zamyka wszystkie niezakończone wpisy kolejki eksportu do PBN.

    Wpisów nie kasujemy: zlecenia wycofania są nieusuwalne z założenia,
    a zamknięty wpis wysyłki deweloper może świadomie ponowić z poziomu
    kolejki. ``rodzaj_bledu`` zostaje pusty, żeby wpisy nie trafiły do alarmu
    o błędach technicznych.

    Zwraca liczby zamkniętych wpisów per operacja.
    """
    aktywne = PBN_Export_Queue.objects.filter(wysylke_zakonczono=None)
    wynik = {}
    for operacja in PBN_Export_Queue.Operacja:
        naglowek = (
            f"{timezone.now()}\n"
            "===============================================================\n"
            f"{KOMUNIKAT_WSTRZYMANIA}\n\n"
        )
        wynik[operacja.value] = aktywne.filter(operacja=operacja).update(
            wysylke_zakonczono=timezone.now(),
            zakonczono_pomyslnie=False,
            retry_after_user_authorised=None,
            komunikat=Concat(
                Value(naglowek),
                Coalesce(F("komunikat"), Value(""), output_field=TextField()),
                output_field=TextField(),
            ),
        )
    return wynik
