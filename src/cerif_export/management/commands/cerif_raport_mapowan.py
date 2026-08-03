"""Raport wartości słownikowych wymagających uzupełnienia przez redakcję.

Eksport CERIF/OpenAIRE opiera się na słownikach kontrolowanych (COAR
Resource Types, COAR Access Rights, BCP 47, adresy licencji). Migracja
danych wypełnia tylko to, co da się wyprowadzić jednoznacznie; reszta jest
decyzją merytoryczną. Ta komenda pokazuje, co zostało do uzupełnienia i co
wymaga potwierdzenia, żeby braki nie wychodziły dopiero jako zubożony
eksport.
"""

import re
from dataclasses import dataclass, field

from django.core.management.base import BaseCommand

from cerif_export.slowniki import coar, dostep

from bpp.models import (
    Charakter_Formalny,
    Jezyk,
    Licencja_OpenAccess,
    Rodzaj_Prawa_Patentowego,
    Tryb_OpenAccess_Wydawnictwo_Ciagle,
    Tryb_OpenAccess_Wydawnictwo_Zwarte,
)

# Reguły przepisane z migracji danych `bpp/migrations/0477_cerif_export_pola.py`
# (funkcja `wypelnij_uri_licencji`). Dublujemy je świadomie: migracji nie wolno
# importować z kodu aplikacji (zamarza w czasie), a raport musi umieć odtworzyć
# wartość, którą tamta wyprodukowała, żeby odróżnić ją od decyzji redakcji.
RE_SKROT_CC = re.compile(r"^CC-([A-Z-]+)$")
SKROTY_CC0 = ("CC-ZERO", "CC0", "CC-0")
URI_CC0 = "https://creativecommons.org/publicdomain/zero/1.0/"

# Wersja licencji nie wynika ze skrótu — migracja przyjęła 4.0 jako
# przybliżenie i to właśnie ta wartość wymaga potwierdzenia.
WERSJA_ZGADYWANA = "4.0"

SZEROKOSC_PODSUMOWANIA = 58


@dataclass
class Sekcja:
    """Jedna grupa braków w raporcie."""

    tytul: str
    etykieta_podsumowania: str
    komentarz: str = ""
    pozycje: list = field(default_factory=list)


def _etykieta(obj):
    """Czytelna identyfikacja wiersza słownika.

    ``Rodzaj_Prawa_Patentowego`` dziedziczy ``ModelZNazwa`` i **nie ma**
    pola ``skrot`` — stąd odczyt warunkowy zamiast ``obj.skrot``.
    """
    skrot = (getattr(obj, "skrot", "") or "").strip()
    if skrot:
        return f"{obj.nazwa} [{skrot}]"
    return str(obj.nazwa)


def _uri_wg_reguly_migracji(skrot):
    """URI, jaki dla danego skrótu wyprodukowałaby migracja danych.

    Zwraca ``(uri, czy_wersja_zgadywana)``. Dla skrótu bez reguły —
    ``("", False)``. CC0 ma tylko jedną wersję (1.0), więc jego URI jest
    dokładny i nie wymaga potwierdzenia.
    """
    skrot = (skrot or "").strip().upper()

    if skrot in SKROTY_CC0:
        return URI_CC0, False

    match = RE_SKROT_CC.match(skrot)
    if match is None:
        return "", False

    kod = match.group(1).lower()
    return (
        f"https://creativecommons.org/licenses/{kod}/{WERSJA_ZGADYWANA}/",
        True,
    )


def _braki_coar(model, tytul, etykieta_podsumowania, dozwolone):
    """Wiersze bez ``coar_type`` albo z wartością spoza właściwej gałęzi.

    Wartość z niewłaściwej gałęzi hierarchii (URI patentu przy charakterze
    formalnym i odwrotnie) jest tak samo bezużyteczna jak brak — profil
    ogranicza ``Publication/Type`` i ``Patent/Type`` do rozłącznych
    enumeracji, a eksport i tak podstawi wtedy korzeń gałęzi.
    """
    sekcja = Sekcja(tytul=tytul, etykieta_podsumowania=etykieta_podsumowania)

    for obj in model.objects.all():
        wartosc = (obj.coar_type or "").strip()

        if not wartosc:
            sekcja.pozycje.append(f"{_etykieta(obj)} — brak wartości")
        elif wartosc not in dozwolone:
            sekcja.pozycje.append(
                f"{_etykieta(obj)} — wartość spoza słownika COAR: {wartosc}"
            )

    return sekcja


def _braki_prawa_dostepu(model, tytul, etykieta_podsumowania):
    """Tryby Open Access bez poprawnego COAR Access Right."""
    sekcja = Sekcja(tytul=tytul, etykieta_podsumowania=etykieta_podsumowania)

    for obj in model.objects.all():
        wartosc = (obj.coar_access_right or "").strip()

        if not wartosc:
            sekcja.pozycje.append(f"{_etykieta(obj)} — brak wartości")
        elif wartosc not in dostep.WSZYSTKIE:
            sekcja.pozycje.append(
                f"{_etykieta(obj)} — wartość spoza słownika COAR "
                f"Access Rights: {wartosc}"
            )

    return sekcja


def _braki_jezykow():
    sekcja = Sekcja(
        tytul="Języki bez kodu BCP 47",
        etykieta_podsumowania="języki",
        komentarz=(
            "Bez kodu elementy w tym języku wyjdą bez atrybutu xml:lang."
        ),
    )

    for obj in Jezyk.objects.all():
        if not (obj.kod_bcp47 or "").strip():
            sekcja.pozycje.append(_etykieta(obj))

    return sekcja


def _licencje():
    """Dwie sekcje: licencje bez URI oraz te z URI do potwierdzenia."""
    bez_uri = Sekcja(
        tytul="Licencje Open Access bez adresu URI",
        etykieta_podsumowania="licencje bez adresu URI",
        komentarz=(
            "Bez adresu prace na tej licencji wyjdą bez odnośnika do jej "
            "treści."
        ),
    )
    do_potwierdzenia = Sekcja(
        tytul=(
            "Licencje Open Access z adresem URI wygenerowanym automatycznie "
            "— wymagają potwierdzenia"
        ),
        etykieta_podsumowania="licencje do potwierdzenia",
        komentarz=(
            "Skrót licencji nie niesie jej wersji, więc migracja danych "
            f"przyjęła {WERSJA_ZGADYWANA} jako przybliżenie. Część zbiorów "
            "używa 3.0 albo 2.5 — proszę zweryfikować i poprawić ręcznie."
        ),
    )

    for obj in Licencja_OpenAccess.objects.all():
        wartosc = (obj.uri or "").strip()

        if not wartosc:
            bez_uri.pozycje.append(_etykieta(obj))
            continue

        z_migracji, wersja_zgadywana = _uri_wg_reguly_migracji(obj.skrot)
        if wersja_zgadywana and wartosc == z_migracji:
            do_potwierdzenia.pozycje.append(f"{_etykieta(obj)} — {wartosc}")

    return bez_uri, do_potwierdzenia


class Command(BaseCommand):
    help = (
        "Wypisuje wartości słownikowe wymagające uzupełnienia lub "
        "potwierdzenia przed eksportem CERIF/OpenAIRE."
    )

    def handle(self, *args, **options):
        licencje_bez_uri, licencje_do_potwierdzenia = _licencje()

        sekcje = [
            _braki_coar(
                Charakter_Formalny,
                "Charaktery formalne bez poprawnego typu COAR",
                "charaktery formalne",
                coar.TYPY_TEKSTOWE,
            ),
            _braki_coar(
                Rodzaj_Prawa_Patentowego,
                "Rodzaje praw patentowych bez poprawnego typu COAR",
                "rodzaje praw patentowych",
                coar.TYPY_PATENTOWE,
            ),
            _braki_jezykow(),
            licencje_bez_uri,
            licencje_do_potwierdzenia,
            _braki_prawa_dostepu(
                Tryb_OpenAccess_Wydawnictwo_Ciagle,
                "Tryby Open Access wyd. ciągłych bez prawa dostępu COAR",
                "tryby OA wyd. ciągłych",
            ),
            _braki_prawa_dostepu(
                Tryb_OpenAccess_Wydawnictwo_Zwarte,
                "Tryby Open Access wyd. zwartych bez prawa dostępu COAR",
                "tryby OA wyd. zwartych",
            ),
        ]

        self._naglowek()

        for sekcja in sekcje:
            self._wypisz_sekcje(sekcja)

        self._podsumowanie(sekcje, licencje_do_potwierdzenia)

    def _naglowek(self):
        tytul = "Raport mapowań słowników na wartości CERIF / OpenAIRE"
        self.stdout.write(tytul)
        self.stdout.write("=" * len(tytul))

    def _wypisz_sekcje(self, sekcja):
        if not sekcja.pozycje:
            return

        self.stdout.write("")
        self.stdout.write(f"{sekcja.tytul} ({len(sekcja.pozycje)}):")

        if sekcja.komentarz:
            self.stdout.write(f"  {sekcja.komentarz}")

        for pozycja in sekcja.pozycje:
            self.stdout.write(f"  * {pozycja}")

    def _podsumowanie(self, sekcje, licencje_do_potwierdzenia):
        self.stdout.write("")
        self.stdout.write("Podsumowanie")
        self.stdout.write("------------")

        for sekcja in sekcje:
            etykieta = sekcja.etykieta_podsumowania
            kropki = "." * max(
                1, SZEROKOSC_PODSUMOWANIA - len(etykieta) - 2
            )
            self.stdout.write(f"  {etykieta} {kropki} {len(sekcja.pozycje)}")

        razem = sum(len(sekcja.pozycje) for sekcja in sekcje)
        self.stdout.write("")
        self.stdout.write(f"RAZEM pozycji wymagających uwagi redakcji: {razem}")

        if razem == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "Wszystkie wartości słownikowe są uzupełnione."
                )
            )
            return

        if licencje_do_potwierdzenia.pozycje:
            self.stdout.write(
                f"w tym adresy licencji do potwierdzenia: "
                f"{len(licencje_do_potwierdzenia.pozycje)}"
            )
