"""Testy DETERMINIZMU kluczy Postgresowych advisory locków.

Sedno: klucz musi wyjść IDENTYCZNY w każdym procesie Pythona. Assert
`klucz == klucz` w obrębie jednego procesu nie dowodzi NICZEGO — wbudowany
`hash()` jest stabilny wewnątrz procesu, a psuje się dopiero między
procesami (sól `PYTHONHASHSEED` losowana przy starcie interpretera).
Dlatego testy niżej odpalają obliczenie w OSOBNYCH procesach z jawnie
różnymi ziarnami.
"""

import os
import subprocess
import sys
import textwrap

import pytest

from django_bpp.db_locks import advisory_lock_id

# Jawnie różne ziarna soli. `0` wyłącza losowanie, pozostałe wymuszają
# konkretne, różne sole — gdyby klucz zależał od `hash()`, każdy z tych
# procesów zwróciłby inną liczbę.
ZIARNA = ["0", "1", "42", "1000", "123456"]

SRC = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _w_osobnym_procesie(kod: str, ziarno: str) -> str:
    """Odpal `kod` w świeżym interpreterze z zadanym PYTHONHASHSEED."""
    env = dict(os.environ, PYTHONHASHSEED=ziarno, PYTHONPATH=SRC)
    wynik = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(kod)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=True,
    )
    return wynik.stdout.strip()


def test_klucz_jest_identyczny_miedzy_procesami():
    """Ten sam klucz w pięciu procesach o różnych PYTHONHASHSEED."""
    kod = """
        from django_bpp.db_locks import advisory_lock_id
        print(advisory_lock_id("pbn_wysylka_oswiadczen.test"))
    """
    wyniki = {_w_osobnym_procesie(kod, z) for z in ZIARNA}

    assert len(wyniki) == 1, (
        f"klucz advisory locka RÓŻNI SIĘ między procesami: {sorted(wyniki)} "
        "— wzajemne wykluczanie nie zachodzi"
    )
    # I zgadza się z wartością liczoną w procesie testowym.
    assert wyniki == {str(advisory_lock_id("pbn_wysylka_oswiadczen.test"))}


def test_wbudowany_hash_rozjezdza_sie_miedzy_procesami():
    """Kontrola metody: dowód, że test wyżej ma zęby.

    Stara implementacja (`abs(hash(nazwa)) % 2**31`) uruchomiona w tych
    samych warunkach MUSI dać różne wartości — inaczej test determinizmu
    przechodziłby również na zepsutym kodzie i nic by nie sprawdzał.
    """
    kod = """
        print(abs(hash("pbn_wysylka_oswiadczen.test")) % (2**31))
    """
    wyniki = {_w_osobnym_procesie(kod, z) for z in ZIARNA}

    assert len(wyniki) > 1, (
        "PYTHONHASHSEED nie wpłynął na hash() — metodyka testu determinizmu "
        "jest nieważna, popraw ją zanim uwierzysz w zielony wynik"
    )


def _kod_bez_komentarzy(modul: str) -> str:
    """Źródło modułu z wyciętymi komentarzami, docstringami i literałami.

    Interesuje nas WYWOŁANIE `hash(...)` w kodzie. Komentarze w tych plikach
    cytują antywzorzec dosłownie, więc skan po surowym tekście dawałby
    fałszywy alarm. Literały pomijamy przy okazji — klucz locka nigdy nie
    bierze się z treści stringa.
    """
    import importlib
    import inspect
    import io
    import tokenize

    pomijane = {tokenize.COMMENT, tokenize.STRING}
    # Python 3.12+ rozbija f-stringi na osobne typy tokenów.
    for nazwa in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END"):
        if hasattr(tokenize, nazwa):
            pomijane.add(getattr(tokenize, nazwa))

    zrodlo = inspect.getsource(importlib.import_module(modul))
    return " ".join(
        tok.string
        for tok in tokenize.generate_tokens(io.StringIO(zrodlo).readline)
        if tok.type not in pomijane
    )


@pytest.mark.parametrize(
    "modul",
    [
        "pbn_downloader_app.tasks",
        "pbn_wysylka_oswiadczen.views",
        "deduplikator_autorow.tasks",
    ],
)
def test_produkcyjne_miejsca_nie_uzywaja_wbudowanego_hash(modul):
    """Regresja: żadne z miejsc liczących klucz locka nie wraca do `hash()`.

    Skanujemy KOD, nie surowy tekst — komentarze w tych plikach objaśniają
    właśnie ten antywzorzec i cytują `abs(hash(...))` dosłownie.
    """
    assert "hash(" not in _kod_bez_komentarzy(modul), (
        f"{modul} znowu liczy klucz advisory locka wbudowanym hash() — "
        "to jest solone PYTHONHASHSEED-em i nie wyklucza niczego"
    )


def test_scan_slot_lock_id_bez_zmiany_wartosci():
    """Refaktor #629 na wspólny helper nie mógł zmienić klucza.

    Gdyby zmienił, wdrożenie mieszane (stary worker + nowy) chwilowo
    używałoby dwóch różnych kluczy i slot skanu przestałby wykluczać.
    """
    from deduplikator_autorow.tasks import SCAN_SLOT_LOCK_ID

    assert SCAN_SLOT_LOCK_ID == 8081800802642310148


def test_klucze_nie_koliduja_ze_soba():
    """Jedno-argumentowe advisory locki dzielą JEDNĄ globalną przestrzeń.

    Kolizja = dwa niepowiązane podsystemy blokują się nawzajem. Wariant
    dwu-argumentowy (migracje 0421/0428/0429/0432, kluczowane
    `(classid, objid)`) ma przestrzeń osobną i tu nie wchodzi.
    """
    from deduplikator_autorow.tasks import SCAN_SLOT_LOCK_ID

    klucze = [
        SCAN_SLOT_LOCK_ID,
        advisory_lock_id("pbn_wysylka_oswiadczen.views.PbnWysylkaOswiadczenTask"),
    ]
    for nazwa_modelu in (
        "PbnDownloadTask",
        "PbnInstitutionPeopleTask",
        "PbnJournalsDownloadTask",
    ):
        klucze.append(
            advisory_lock_id(f"pbn_downloader_app.create_task_with_lock.{nazwa_modelu}")
        )

    assert len(set(klucze)) == len(klucze), f"kolizja kluczy: {klucze}"
    # Wszystkie mieszczą się w dodatnim bigint (dziedzina jedno-arg. wariantu).
    assert all(0 < k < 2**63 for k in klucze)
