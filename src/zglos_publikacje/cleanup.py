"""Rdzeń czyszczenia porzuconych plików tymczasowych kreatora zgłoszeń.

Wspólny dla management-commandy `wyczysc_zglos_tmp` (ręczne/ops runy) oraz
celery-taska `zglos_publikacje.tasks.wyczysc_zglos_tmp_pliki` (cykliczny beat).
Kasuje pliki starsze niż `older_than_hours` WYŁĄCZNIE z katalogu tmp
(`zglos_tmp_dir()`), tego samego punktu prawdy co wizard.

Bezpieczeństwo wobec nakazu klienta „nigdy nie kasuj plików realnych zgłoszeń"
opiera się na KONSTRUKCJI: trwałe pliki ukończonych zgłoszeń lądują w OSOBNYM
katalogu (`protected/zglos_publikacje/`), którego tu nie dotykamy. Dodatkowo
strażnik równości basename odmawia działania, gdy rozwiązany katalog celu nie
jest dokładnie skonfigurowanym katalogiem tmp.
"""

from __future__ import annotations

import pathlib
import time

from zglos_publikacje.storage import ZGLOS_TMP_DIRNAME, zglos_tmp_dir


class ZglosTmpGuardError(Exception):
    """Strażnik ścieżki: katalog celu nie jest skonfigurowanym katalogiem tmp."""


def wyczysc_tmp_pliki(older_than_hours: int = 24, dry_run: bool = False) -> dict:
    """Skasuj porzucone pliki tmp starsze niż `older_than_hours`.

    Zwraca dict `{skasowane, skasowane_bajty, pominiete, katalog_nieobecny}`.
    Rzuca `ValueError` dla ujemnego progu, `ZglosTmpGuardError` gdy strażnik
    ścieżki odmawia (katalog o innym basename niż tmp).
    """
    if older_than_hours < 0:
        # Ujemny próg → prog w przyszłości → skasowałby WSZYSTKO, łącznie
        # z plikami in-flight żywych sesji. Odmawiamy (błąd wywołującego).
        raise ValueError("older_than_hours musi być >= 0.")

    # realpath — neutralizuje symlink i trailing slash zanim porównamy basename.
    tmp = pathlib.Path(zglos_tmp_dir()).resolve()

    wynik = {
        "skasowane": 0,
        "skasowane_bajty": 0,
        "pominiete": 0,
        "katalog_nieobecny": False,
    }

    if not tmp.exists():
        # Świeża instalacja, zero uploadów — nie ma czego czyścić. NIE wołamy
        # iterdir() (rzuciłby FileNotFoundError).
        wynik["katalog_nieobecny"] = True
        return wynik

    # STRAŻNIK: równość basename (nie endswith). Zabezpieczenie przed
    # skasowaniem złego katalogu, gdyby punkt prawdy został podmieniony.
    if tmp.name != ZGLOS_TMP_DIRNAME:
        raise ZglosTmpGuardError(
            f"Katalog docelowy '{tmp}' nie jest katalogiem tmp "
            f"'{ZGLOS_TMP_DIRNAME}' — odmawiam działania."
        )

    prog = time.time() - older_than_hours * 3600

    for e in tmp.iterdir():
        # lstat — nie podążaj za linkiem; kasuj tylko zwykłe pliki, nigdy
        # symlinki (mogłyby wskazywać na plik trwały) ani katalogi.
        if not e.is_file() or e.is_symlink():
            wynik["pominiete"] += 1
            continue
        try:
            st = e.lstat()
            if st.st_mtime < prog:
                if not dry_run:
                    e.unlink()
                wynik["skasowane"] += 1
                wynik["skasowane_bajty"] += st.st_size
            else:
                wynik["pominiete"] += 1
        except FileNotFoundError:
            # Żywa sesja kreatora skasowała swój plik równolegle (między
            # iterdir a lstat/unlink) — nie nasz problem, nie wywalaj przebiegu.
            wynik["pominiete"] += 1

    return wynik
