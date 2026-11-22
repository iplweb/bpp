"""Motywy kolorystyczne z plików konfiguracji ``src/bpp/static/scss/motywy/*.json``.

Każdy plik to konfig z konfiguratora wyglądu. Task Grunta ``motywy`` kompiluje
go do ``src/bpp/static/scss/app-<nazwa>.css``; tu tylko dopisujemy motyw do
listy ``BPP_THEMES`` (wybór w adminie uczelni). Pełna walidacja konfiga
(kolory, kontrast) żyje w ``motyw-konfig.js`` i odpala się przy kompilacji.
"""

import functools
import json
import re
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

KATALOG_MOTYWOW = Path(__file__).resolve().parent.parent / "bpp/static/scss/motywy"

RE_NAZWA = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")


def wczytaj_motywy(katalog=KATALOG_MOTYWOW, zajete=()):
    """Zwraca listę ``(wartość, etykieta)`` dla motywów z konfiguracji.

    ``zajete`` to wartości motywów pisanych ręcznie — konfig nie może
    nadpisać żadnego z nich.
    """
    wynik = []
    widziane = set(zajete)
    for plik in sorted(Path(katalog).glob("*.json")):
        try:
            konfig = json.loads(plik.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ImproperlyConfigured(f"Motyw {plik}: niepoprawny JSON ({e}).") from e

        nazwa = konfig.get("nazwa", "")
        if not RE_NAZWA.match(nazwa):
            raise ImproperlyConfigured(f"Motyw {plik}: niepoprawna nazwa {nazwa!r}.")
        if plik.stem != nazwa:
            raise ImproperlyConfigured(
                f"Motyw {plik}: nazwa pliku musi być równa polu „nazwa” ({nazwa})."
            )

        wartosc = f"app-{nazwa}"
        if wartosc in widziane:
            raise ImproperlyConfigured(
                f"Motyw {plik}: nazwa {wartosc} jest już zajęta przez inny motyw."
            )
        widziane.add(wartosc)
        wynik.append((wartosc, konfig.get("opis") or nazwa))
    return wynik


@functools.lru_cache(maxsize=64)
def tryb_kolorow_motywu(wartosc, katalog=KATALOG_MOTYWOW):
    """``tryb_kolorow`` motywu z pliku konfiguracji (``app-<nazwa>``) albo
    None, gdy to nie jest motyw z konfiguracji. Brak pola = „jasny”
    (domyślna wartość konfiguratora)."""
    if not wartosc.startswith("app-"):
        return None
    plik = Path(katalog) / f"{wartosc[len('app-') :]}.json"
    try:
        konfig = json.loads(plik.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None  # motyw pisany ręcznie (scss), nie z konfiguracji
    return konfig.get("tryb_kolorow") or "jasny"
