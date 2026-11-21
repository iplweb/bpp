"""Generator fałszywego eksportu POL-on dla uczelni demo.

Zapisuje plik XLSX w formacie „Rozszerzone zestawienie pracowników podmiotu"
(43 kolumny, arkusz ``Output``, wszystkie komórki jako napisy — jak w
prawdziwym eksporcie), który da się zaimportować przez „operacje → import
z POLON" (aplikacja ``import_polon``) na bazie demo. Po imporcie dla lat
2022–2025 „Oblicz liczbę N" daje liczbę N >= 12 w dyscyplinach z dużym
celem FTE i < 12 w dyscyplinie z małym celem.

Kluczowe ograniczenia importera (``import_polon.core.import_polon``):

- ``ZATRUDNIENIE`` musi zaczynać się DOKŁADNIE od ``uczelnia.nazwa``;
- autor dopasowywany jest po ORCID albo po imionach i nazwisku — przy
  remisie (powtarzające się nazwiska z puli motywu) wynik to ``None``,
  dlatego do pliku trafiają tylko autorzy o UNIKALNEJ parze
  (imiona, nazwisko), z aktualną jednostką tej uczelni, sprawdzeni
  prawdziwym ``matchuj_autora``;
- nazwy dyscyplin muszą być identyczne z ``Dyscyplina_Naukowa.nazwa``.

Generator ma WŁASNY RNG (``random.Random(f"{seed}-polon")``) — nie pobiera
liczb z RNG reszty ``create_demo_data``, więc dołożenie pliku POL-on nie
zmienia żadnego innego rekordu wygenerowanego dla danego ``--seed``.
"""

from __future__ import annotations

import datetime
import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

from bpp.demo_data.themes.base import Theme

# Pełny, 43-kolumnowy nagłówek prawdziwego eksportu (kolejność ma znaczenie
# wyłącznie dla realizmu — importer czyta kolumny po nazwie).
NAGLOWKI: tuple[str, ...] = (
    "UUID",
    "STOPIEN_TYTUL_AKTUALNY_NA_DZIEN_WYGENEROWANIA_RAPORTU",
    "IMIE",
    "DRUGIE",
    "NAZWISKO",
    "PESEL_NR_DOK_TOZSAM",
    "CUDZOZIEMIEC",
    "OBYWATELSTWO",
    "PLEC",
    "KRAJ_URODZENIA",
    "ROK_URODZENIA",
    "ZATRUDNIENIE",
    "PODSTAWOWE_MIEJSCE_PRACY",
    "INNA_OSOBA_PROWADZACA_ZAJECIA",
    "WYMIAR_ETATU",
    "WIELKOSC_ETATU",
    "WIELKOSC_ETATU_PREZENTACJA_DZIESIETNA",
    "JEDNOSTKA",
    "ZATRUDNIENIE_OD",
    "ZATRUDNIENIE_DO",
    "WARUNKI_OD",
    "WARUNKI_DO",
    "DATA_ZLOZENIA_OSWIADCZENIA",
    "OSWIADCZENIE_O_DYSCYPLINACH",
    "OSWIADCZONA_DYSCYPLINA_PIERWSZA",
    "OSWIADCZONA_DYSCYPLINA_DRUGA",
    "PROCENTOWY_UDZIAL_PIERWSZA_DYSCYPLINA",
    "ILOSC_OSWIADCZONYCH_DYSCYPLIN",
    "OSWIADCZENIE_N",
    "ILOSC_DYSCYPLIN_W_OSWIADCZENIU_N",
    "DYSCYPLINA_N",
    "DYSCYPLINA_N_KOLEJNA",
    "DATA_ZLOZENIA_OSWIADCZENIA_N",
    "DATA_ZAKONCZENIA_OSWIADCZENIA_N",
    "PROPORCJE_W_DYSCYPLINACH",
    "CHARAKTER_PRACY",
    "GRUPA_STANOWISK",
    "STANOWISKO_KOD",
    "STANOWISKO_NAZWA",
    "STANOWISKO_INNE",
    "NOTATKA",
    "IDETYFIKATOR_OSOBY_PBN",
    "ORCID",
)

# Domyślne dyscypliny = te same co w ``bin/docs-demo-sloty.py``. Cel FTE
# (suma etat × udział N na rok): trzy dyscypliny powyżej progu 12,
# „nauki teologiczne" celowo poniżej (dyscyplina nieraportowana).
DOMYSLNE_DYSCYPLINY: tuple[tuple[str, Decimal], ...] = (
    ("filozofia", Decimal("16")),
    ("nauki teologiczne", Decimal("5")),
    ("biotechnologia", Decimal("15")),
    ("archeologia", Decimal("14")),
)
DOMYSLNY_CEL_FTE = Decimal("15")

GRUPA_BADAWCZO_DYDAKTYCZNA = "Pracownik badawczo-dydaktyczny"
GRUPA_DYDAKTYCZNA = "Pracownik dydaktyczny"
CHARAKTER_PRACY = "Nauczyciel akademicki"

# (prezentacja dziesiętna, WYMIAR_ETATU, WIELKOSC_ETATU, wartość, waga)
_ETATY = (
    ("1", "Pełny", "1/1", Decimal("1"), 8),
    ("0,5", "Niepełny", "1/2", Decimal("0.5"), 1),
    ("0,75", "Niepełny", "3/4", Decimal("0.75"), 1),
)
# Kody stanowisk przybliżone (kilka zaobserwowanych w prawdziwym eksporcie).
_STANOWISKA_BADAWCZE = (
    ("149", "Profesor"),
    ("150", "Profesor uczelni"),
    ("147", "Adiunkt"),
    ("147", "Adiunkt"),
    ("148", "Asystent"),
)
_STANOWISKA_DYDAKTYCZNE = (("162", "Adiunkt"), ("164", "Wykładowca"))
_TYTULY = ("dr", "dr", "dr hab.", "prof. dr hab.", "mgr")

# Wiersze celowo błędne (``bledne_wiersze=True``):
DYSCYPLINA_SPOZA_SLOWNIKA = "eliksirologia stosowana"
OSOBA_SPOZA_BPP = ("Nieznana", "Spoza-Bazy-Demo")
OBCA_UCZELNIA_DOMYSLNA = "Uniwersytet Spoza Demo"

# Ułamki rodzajów (wobec liczby wierszy N): ~10% B i ~10% Z całości.
UDZIAL_B = Decimal("0.14")
UDZIAL_Z = Decimal("0.14")
ILE_DWUDYSCYPLINOWYCH = 3
PROPORCJA_DWUDYSCYPLINOWA = (60, 40)


def domyslna_nazwa_pliku(dzien: datetime.date | None = None) -> str:
    dzien = dzien or datetime.date.today()
    return (
        "rozszerzone_zestawienie_pracownikow_podmiotu_na_dzien_"
        f"wygenerowania_raportu_{dzien.isoformat()}.xlsx"
    )


def parsuj_dyscypliny(wartosci: Iterable[str] | None) -> list[tuple[str, Decimal]]:
    """``["filozofia=16", "archeologia"]`` → ``[("filozofia", 16), ...]``.

    Brak ``=FTE`` → ``DOMYSLNY_CEL_FTE``. ``None``/pusta lista →
    ``DOMYSLNE_DYSCYPLINY``.
    """
    if not wartosci:
        return list(DOMYSLNE_DYSCYPLINY)
    wynik = []
    for wartosc in wartosci:
        nazwa, sep, cel = wartosc.partition("=")
        nazwa = nazwa.strip()
        if not nazwa:
            raise ValueError(f"Pusta nazwa dyscypliny w '{wartosc}'.")
        wynik.append((nazwa, Decimal(cel.strip()) if sep else DOMYSLNY_CEL_FTE))
    return wynik


def orcid_z_suma_kontrolna(cyfry15: str) -> str:
    """Dopisuje cyfrę kontrolną ISO 7064 MOD 11-2 i formatuje XXXX-XXXX-…"""
    if len(cyfry15) != 15 or not cyfry15.isdigit():
        raise ValueError("ORCID: oczekiwano 15 cyfr")
    total = 0
    for ch in cyfry15:
        total = (total + int(ch)) * 2
    reszta = (12 - total % 11) % 11
    pelny = cyfry15 + ("X" if reszta == 10 else str(reszta))
    return "-".join(pelny[i : i + 4] for i in range(0, 16, 4))


def obca_uczelnia_dla(uczelnia_nazwa: str, theme: Theme | None = None) -> str:
    """Nazwa „drugiej" uczelni motywu — do wiersza, który importer pominie.

    Bez motywu zgadujemy go po nazwie uczelni (``Demo — <nazwa motywu>``).
    """
    from bpp.demo_data.themes.registry import THEMES

    kandydaci = [theme] if theme is not None else list(THEMES.values())
    for t in kandydaci:
        if len(t.uczelnia_nazwy) > 1 and uczelnia_nazwa.endswith(t.uczelnia_nazwy[0]):
            obca = t.uczelnia_nazwy[1]
            if not obca.startswith(uczelnia_nazwa):
                return obca
    return OBCA_UCZELNIA_DOMYSLNA


@dataclass
class PolonPodsumowanie:
    plik: Path
    wierszy: int = 0
    wierszy_n: int = 0
    wierszy_b: int = 0
    wierszy_z: int = 0
    fte_n: dict[str, Decimal] = field(default_factory=dict)
    cele_fte: dict[str, Decimal] = field(default_factory=dict)
    bledne_wiersze: list[str] = field(default_factory=list)
    ostrzezenia: list[str] = field(default_factory=list)

    def tekst(self) -> str:
        linie = [
            f"[OK] Plik POL-on: {self.plik}",
            f"     Wierszy: {self.wierszy} (N: {self.wierszy_n}, "
            f"B: {self.wierszy_b}, Z: {self.wierszy_z}, "
            f"celowo błędnych: {len(self.bledne_wiersze)})",
        ]
        for nazwa, fte in self.fte_n.items():
            prog = "≥ 12" if fte >= 12 else "< 12 (nieraportowana)"
            linie.append(f"     FTE N / rok — {nazwa}: {fte:.2f} {prog}")
        for opis in self.bledne_wiersze:
            linie.append(f"     Błędny wiersz: {opis}")
        for ostrzezenie in self.ostrzezenia:
            linie.append(f"[UWAGA] {ostrzezenie}")
        linie.append(
            "     Zaimportuj plik osobno dla lat 2022, 2023, 2024 i 2025 "
            "(operacje → import z POLON), potem: ewaluacja → liczba N → "
            "Oblicz liczbę N."
        )
        return "\n".join(linie) + "\n"


def _kandydaci(uczelnia, wykluczone_pk: set[int]):
    """Autorzy uczelni o unikalnej parze (imiona, nazwisko), po pk.

    Unikalność liczona względem WSZYSTKICH autorów w bazie — importer
    dopasowuje globalnie.
    """
    from collections import Counter

    from bpp.models import Autor

    licznik = Counter(
        (imiona.strip().lower(), nazwisko.strip().lower())
        for imiona, nazwisko in Autor.objects.values_list("imiona", "nazwisko")
    )
    for autor in (
        Autor.objects.filter(
            aktualna_jednostka__uczelnia=uczelnia,
            aktualna_jednostka__skupia_pracownikow=True,
        )
        .select_related("tytul")
        .order_by("pk")
    ):
        if autor.pk in wykluczone_pk:
            continue
        klucz = ((autor.imiona or "").strip().lower(), autor.nazwisko.strip().lower())
        if licznik[klucz] == 1 and klucz[0]:
            yield autor


def _dopasowuje_sie(autor) -> bool:
    """Czy importer (``matchuj_autora`` po imionach i nazwisku) trafi TEGO autora."""
    from import_common.core import matchuj_autora

    return matchuj_autora(imiona=autor.imiona, nazwisko=autor.nazwisko) == autor


class _Pula:
    """Leniwy, deterministyczny strumień autorów gotowych do pliku."""

    def __init__(self, uczelnia, rng: random.Random):
        lista = list(_kandydaci(uczelnia, set()))
        rng.shuffle(lista)
        self._lista = lista
        self._i = 0

    def nastepny(self):
        while self._i < len(self._lista):
            autor = self._lista[self._i]
            self._i += 1
            if _dopasowuje_sie(autor):
                return autor
        return None


class _Orcidy:
    def __init__(self, rng: random.Random, wlacz: bool):
        from bpp.models import Autor

        self._rng = rng
        self._wlacz = wlacz
        self._zajete = set(
            Autor.objects.exclude(orcid=None)
            .exclude(orcid="")
            .values_list("orcid", flat=True)
        )

    def dla(self, autor) -> str | None:
        if autor.orcid:
            return autor.orcid
        if not self._wlacz:
            return None
        while True:
            orcid = orcid_z_suma_kontrolna(
                "00000002" + "".join(str(self._rng.randint(0, 9)) for _ in range(7))
            )
            if orcid not in self._zajete:
                self._zajete.add(orcid)
                return orcid


def _wiersz(**pola) -> dict[str, str | None]:
    nieznane = set(pola) - set(NAGLOWKI)
    if nieznane:
        raise KeyError(f"Nieznane kolumny: {sorted(nieznane)}")
    wiersz = dict.fromkeys(NAGLOWKI)
    wiersz.update(pola)
    return wiersz


def _osoba(autor, rng: random.Random, orcidy: _Orcidy) -> dict[str, str | None]:
    imie, _, drugie = (autor.imiona or "").strip().partition(" ")
    tytul = autor.tytul.skrot if autor.tytul_id else rng.choice(_TYTULY)
    return dict(
        STOPIEN_TYTUL_AKTUALNY_NA_DZIEN_WYGENEROWANIA_RAPORTU=tytul,
        IMIE=imie,
        DRUGIE=drugie or None,
        NAZWISKO=autor.nazwisko,
        ORCID=orcidy.dla(autor),
    )


def _zatrudnienie(
    uczelnia_nazwa: str,
    grupa: str,
    etat,
    rng: random.Random,
) -> dict[str, str | None]:
    """Kolumny zatrudnienia; start zawsze przed 2022 (cały okres ewaluacji)."""
    prezentacja, wymiar, wielkosc, _, _ = etat
    od = f"{rng.randint(1995, 2021)}-{rng.choice(('10', '10', '03', '02'))}-01"
    stanowiska = (
        _STANOWISKA_DYDAKTYCZNE if grupa == GRUPA_DYDAKTYCZNA else _STANOWISKA_BADAWCZE
    )
    kod, nazwa = rng.choice(stanowiska)
    return dict(
        CUDZOZIEMIEC="Nie",
        ZATRUDNIENIE=f"{uczelnia_nazwa} ({CHARAKTER_PRACY}>{grupa})",
        PODSTAWOWE_MIEJSCE_PRACY="Tak",
        INNA_OSOBA_PROWADZACA_ZAJECIA="Nie",
        WYMIAR_ETATU=wymiar,
        WIELKOSC_ETATU=wielkosc,
        WIELKOSC_ETATU_PREZENTACJA_DZIESIETNA=prezentacja,
        ZATRUDNIENIE_OD=od,
        WARUNKI_OD=od,
        CHARAKTER_PRACY=CHARAKTER_PRACY,
        GRUPA_STANOWISK=grupa,
        STANOWISKO_KOD=kod,
        STANOWISKO_NAZWA=nazwa,
    )


def _oswiadczenia(
    pierwsza: str,
    druga: str | None,
    procent: int,
    *,
    w_n: bool,
) -> dict[str, str | None]:
    ile = "2" if druga else "1"
    data = "2022-01-15"
    pola = dict(
        DATA_ZLOZENIA_OSWIADCZENIA=data,
        OSWIADCZENIE_O_DYSCYPLINACH="Tak",
        OSWIADCZONA_DYSCYPLINA_PIERWSZA=pierwsza,
        OSWIADCZONA_DYSCYPLINA_DRUGA=druga,
        PROCENTOWY_UDZIAL_PIERWSZA_DYSCYPLINA=str(procent),
        ILOSC_OSWIADCZONYCH_DYSCYPLIN=ile,
        OSWIADCZENIE_N="Tak" if w_n else "Nie",
        ILOSC_DYSCYPLIN_W_OSWIADCZENIU_N=ile if w_n else "0",
        PROPORCJE_W_DYSCYPLINACH="Tak",
    )
    if w_n:
        pola.update(
            DYSCYPLINA_N=pierwsza,
            DYSCYPLINA_N_KOLEJNA=druga,
            DATA_ZLOZENIA_OSWIADCZENIA_N=data,
        )
    return pola


def _losuj_etat(rng: random.Random):
    return rng.choices(_ETATY, weights=[e[4] for e in _ETATY])[0]


def _sprawdz_dyscypliny(nazwy: Sequence[str]) -> None:
    from bpp.models import Dyscyplina_Naukowa

    istniejace = set(
        Dyscyplina_Naukowa.objects.filter(nazwa__in=nazwy).values_list(
            "nazwa", flat=True
        )
    )
    brak = [n for n in nazwy if n not in istniejace]
    if brak:
        raise ValueError(
            "Brak dyscyplin w słowniku Dyscyplina_Naukowa (wymagana dokładna "
            f"nazwa): {', '.join(brak)}"
        )


class _Budowniczy:
    """Składa wiersze pliku w ustalonej kolejności (determinizm przy seedzie)."""

    def __init__(self, *, uczelnia, dyscypliny, rng, orcid):
        self.uczelnia = uczelnia
        self.rng = rng
        self.nazwy = [n for n, _ in dyscypliny]
        self.cele = dict(dyscypliny)
        self.fte = dict.fromkeys(self.nazwy, Decimal("0"))
        self.pula = _Pula(uczelnia, rng)
        self.orcidy = _Orcidy(rng, orcid)
        self.wiersze: list[dict[str, str | None]] = []
        self.podsumowanie = PolonPodsumowanie(plik=Path(), cele_fte=dict(self.cele))
        self.zabraklo = False

    def _autor(self):
        autor = None if self.zabraklo else self.pula.nastepny()
        if autor is None:
            self.zabraklo = True
        return autor

    def _wiersz_autora(self, autor, grupa, etat, oswiadczenia):
        return _wiersz(
            **_osoba(autor, self.rng, self.orcidy),
            **_zatrudnienie(self.uczelnia.nazwa, grupa, etat, self.rng),
            **oswiadczenia,
        )

    def _dodaj_n(self, pierwsza, druga, procent, etat) -> bool:
        autor = self._autor()
        if autor is None:
            return False
        self.wiersze.append(
            self._wiersz_autora(
                autor,
                GRUPA_BADAWCZO_DYDAKTYCZNA,
                etat,
                _oswiadczenia(pierwsza, druga, procent, w_n=True),
            )
        )
        self.fte[pierwsza] += etat[3] * procent / 100
        if druga:
            self.fte[druga] += etat[3] * (100 - procent) / 100
        self.podsumowanie.wierszy_n += 1
        return True

    def dwudyscyplinowi(self):
        """Kilku autorów N w dwóch dyscyplinach (60/40) — pierwsza z dużym
        celem (>= 12, a gdy takich brak — z największym), druga dowolna inna."""
        if len(self.nazwy) < 2:
            return
        duze = [n for n in self.nazwy if self.cele[n] >= 12] or [
            max(self.nazwy, key=self.cele.get)
        ]
        for i in range(ILE_DWUDYSCYPLINOWYCH):
            pierwsza = duze[i % len(duze)]
            druga = self.rng.choice([n for n in self.nazwy if n != pierwsza])
            if not self._dodaj_n(
                pierwsza, druga, PROPORCJA_DWUDYSCYPLINOWA[0], _ETATY[0]
            ):
                return

    def dopelnij_do_celow(self):
        """Autorzy jednodyscyplinowi, aż FTE N dyscypliny osiągnie cel."""
        for nazwa in self.nazwy:
            while self.fte[nazwa] < self.cele[nazwa]:
                if not self._dodaj_n(nazwa, None, 100, _losuj_etat(self.rng)):
                    return

    def spoza_n(self):
        """Pracownicy badawczo-dydaktyczni spoza N (B) i dydaktyczni (Z)."""
        for grupa, udzial in (
            (GRUPA_BADAWCZO_DYDAKTYCZNA, UDZIAL_B),
            (GRUPA_DYDAKTYCZNA, UDZIAL_Z),
        ):
            for _ in range(max(1, int(self.podsumowanie.wierszy_n * udzial))):
                autor = self._autor()
                if autor is None:
                    return
                self.wiersze.append(
                    self._wiersz_autora(
                        autor,
                        grupa,
                        _losuj_etat(self.rng),
                        _oswiadczenia(
                            self.rng.choice(self.nazwy), None, 100, w_n=False
                        ),
                    )
                )
                if grupa == GRUPA_DYDAKTYCZNA:
                    self.podsumowanie.wierszy_z += 1
                else:
                    self.podsumowanie.wierszy_b += 1

    def _wiersz_osoby(self, imie, nazwisko, zatrudnienie_w):
        pola = _zatrudnienie(
            self.uczelnia.nazwa, GRUPA_BADAWCZO_DYDAKTYCZNA, _ETATY[0], self.rng
        )
        pola["ZATRUDNIENIE"] = (
            f"{zatrudnienie_w} ({CHARAKTER_PRACY}>{GRUPA_BADAWCZO_DYDAKTYCZNA})"
        )
        self.wiersze.append(
            _wiersz(
                STOPIEN_TYTUL_AKTUALNY_NA_DZIEN_WYGENEROWANIA_RAPORTU="dr",
                IMIE=imie,
                NAZWISKO=nazwisko,
                **pola,
                **_oswiadczenia(self.nazwy[0], None, 100, w_n=True),
            )
        )

    def bledne(self, obca_uczelnia: str | None):
        """Celowo błędne wiersze — po jednym z każdego rodzaju."""
        opisy = self.podsumowanie.bledne_wiersze
        obca = obca_uczelnia or OBCA_UCZELNIA_DOMYSLNA
        if obca.startswith(self.uczelnia.nazwa):
            obca = OBCA_UCZELNIA_DOMYSLNA

        self._wiersz_osoby("Gościnny", "Pracownik-Obcej-Uczelni", obca)
        opisy.append(
            f"ZATRUDNIENIE w innej uczelni ('{obca}') — importer pominie wiersz"
        )

        imie, nazwisko = OSOBA_SPOZA_BPP
        self._wiersz_osoby(imie, nazwisko, self.uczelnia.nazwa)
        opisy.append(f"osoba spoza BPP ({imie} {nazwisko}) — brak dopasowania autora")

        # Dwa ostatnie potrzebują PRAWDZIWEGO autora (błąd ma wyjść dopiero
        # po dopasowaniu). Nie liczą się do FTE — importer ich nie zapisze.
        autor = self._autor()
        if autor is not None:
            self.wiersze.append(
                self._wiersz_autora(
                    autor,
                    GRUPA_BADAWCZO_DYDAKTYCZNA,
                    _ETATY[0],
                    _oswiadczenia(DYSCYPLINA_SPOZA_SLOWNIKA, None, 100, w_n=True),
                )
            )
            opisy.append(
                f"dyscyplina spoza słownika ('{DYSCYPLINA_SPOZA_SLOWNIKA}') — "
                f"{autor.imiona} {autor.nazwisko}"
            )
        autor = self._autor()
        if autor is not None:
            wiersz = self._wiersz_autora(
                autor,
                GRUPA_BADAWCZO_DYDAKTYCZNA,
                _ETATY[0],
                _oswiadczenia(self.nazwy[0], None, 100, w_n=True),
            )
            wiersz["WIELKOSC_ETATU_PREZENTACJA_DZIESIETNA"] = None
            self.wiersze.append(wiersz)
            opisy.append(
                f"pusty wymiar etatu w wierszu N — {autor.imiona} {autor.nazwisko}"
            )

    def wynik(self):
        # Prawdziwy eksport jest posortowany alfabetycznie.
        self.wiersze.sort(
            key=lambda w: ((w["NAZWISKO"] or "").lower(), w["IMIE"] or "")
        )
        p = self.podsumowanie
        p.wierszy = len(self.wiersze)
        p.fte_n = self.fte
        if self.zabraklo:
            p.ostrzezenia.append(
                "Zabrakło autorów o unikalnym imieniu i nazwisku w tej uczelni — "
                "cele FTE mogą nie zostać osiągnięte. Wygeneruj dane demo z "
                "większą liczbą autorów albo motywem z większą pulą nazwisk."
            )
        for nazwa in self.nazwy:
            if self.fte[nazwa] < self.cele[nazwa]:
                p.ostrzezenia.append(
                    f"{nazwa}: FTE N {self.fte[nazwa]:.2f} < cel {self.cele[nazwa]}."
                )
        return self.wiersze, p


def zbuduj_wiersze(
    *,
    uczelnia,
    dyscypliny: Sequence[tuple[str, Decimal]],
    rng: random.Random,
    bledne_wiersze: bool = True,
    obca_uczelnia: str | None = None,
    orcid: bool = True,
) -> tuple[list[dict[str, str | None]], PolonPodsumowanie]:
    """Buduje wiersze pliku (bez zapisu). Zwraca (wiersze, podsumowanie).

    Kolejność: autorzy N (najpierw dwudyscyplinowi, potem dopełnienie każdej
    dyscypliny do celu FTE), potem B i Z, na końcu celowo błędne wiersze —
    przy braku autorów cierpią najpierw dodatki, a nie liczba N.
    """
    _sprawdz_dyscypliny([n for n, _ in dyscypliny])
    b = _Budowniczy(uczelnia=uczelnia, dyscypliny=dyscypliny, rng=rng, orcid=orcid)
    b.dwudyscyplinowi()
    b.dopelnij_do_celow()
    b.spoza_n()
    if bledne_wiersze:
        b.bledne(obca_uczelnia)
    return b.wynik()


def write_polon_file(
    out: Path | str | None = None,
    *,
    uczelnia=None,
    dyscypliny: Sequence[tuple[str, Decimal]] | None = None,
    seed: int | str | None = None,
    bledne_wiersze: bool = True,
    theme: Theme | None = None,
    orcid: bool = True,
    dzien: datetime.date | None = None,
) -> PolonPodsumowanie:
    """Zapisuje plik POL-on i zwraca podsumowanie.

    ``out`` — ścieżka pliku albo katalog (wtedy nazwa domyślna, jak
    w prawdziwym eksporcie); ``None`` = bieżący katalog.
    """
    from bpp.models import Uczelnia

    if uczelnia is None:
        uczelnia = Uczelnia.objects.order_by("pk").first()
        if uczelnia is None:
            raise ValueError("Brak uczelni w bazie — najpierw create_demo_data.")

    out = Path(out) if out is not None else Path.cwd()
    if out.is_dir():
        out = out / domyslna_nazwa_pliku(dzien)

    rng = random.Random(f"{seed}-polon")
    wiersze, podsumowanie = zbuduj_wiersze(
        uczelnia=uczelnia,
        dyscypliny=list(dyscypliny or DOMYSLNE_DYSCYPLINY),
        rng=rng,
        bledne_wiersze=bledne_wiersze,
        obca_uczelnia=obca_uczelnia_dla(uczelnia.nazwa, theme),
        orcid=orcid,
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Output"
    ws.append(list(NAGLOWKI))
    for wiersz in wiersze:
        ws.append([wiersz[k] for k in NAGLOWKI])
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)

    podsumowanie.plik = out
    return podsumowanie
