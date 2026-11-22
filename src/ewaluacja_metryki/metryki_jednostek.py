"""Metryki jednostki i wydziału — dane zestawienia PDF (FD#617).

Raport ma być doradcą dla kierownika jednostki (np. kliniki): na bazie
``MetrykaAutora`` pokazuje, kto wypełnia sloty, kto pisze lepsze prace na tle
jednostki, gdzie leży niewykorzystany potencjał i jak wygląda struktura
punktacji prac. Wszystko liczone osobno dla każdej dyscypliny — średnie za slot
w różnych dyscyplinach nie są porównywalne.

To samo zestawienie da się zbudować dla całego wydziału (korzeń drzewa
jednostek) — wtedy mediany i „realia” liczone są na tle wydziału, a dochodzi
podsumowanie jednostek wydziału.

Moduł nie zna HTML-a ani PDF-a: zwraca czyste struktury danych, które szablon
(i generator SVG w ``metryki_jednostek_svg``) zamienia na wydruk.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from statistics import median

from django.db.models import Sum

from .models import MetrykaAutora
from .uczelnia_scope import scope_metryki

# Wypełnienie slotów (w %) — progi bezwzględne: „pełne sloty” to cel
# niezależny od realiów jednostki.
PROG_WYPELNIENIA_DOBRY = Decimal("90")
PROG_WYPELNIENIA_SREDNI = Decimal("50")

# Jakość prac (średnia punktów za slot) — względem MEDIANY dyscypliny
# w jednostce, czyli „zeskalowana do realiów jednostki”.
PROG_JAKOSCI_WYSOKI = Decimal("1.10")
PROG_JAKOSCI_NISKI = Decimal("0.90")

# Podział wykresu bąbelkowego: oś wypełnienia slotów.
PROG_KWADRANTU_WYPELNIENIE = Decimal("80")

# Przedziały punktacji prac (od najwyżej punktowanych).
PRZEDZIALY_PUNKTOW = (
    (Decimal("200"), "200 i więcej"),
    (Decimal("140"), "140–199"),
    (Decimal("100"), "100–139"),
    (Decimal("70"), "70–99"),
    (Decimal("40"), "40–69"),
    (Decimal("0"), "poniżej 40"),
)
# Prace poniżej tego progu traktujemy w wnioskach jako „słabo punktowane”.
PROG_SLABYCH_PRAC = Decimal("70")

DOBRY = "dobry"
SREDNI = "sredni"
SLABY = "slaby"
BRAK = "brak"

KWADRANT_FILAR = "filar"
KWADRANT_ILOSC = "ilosc"
KWADRANT_POTENCJAL = "potencjal"
KWADRANT_WSPARCIE = "wsparcie"
KWADRANT_BRAK = "brak"

OPIS_KWADRANTU = {
    KWADRANT_FILAR: "Filar {dopelniacz}",
    KWADRANT_ILOSC: "Pełne sloty, słabsze prace",
    KWADRANT_POTENCJAL: "Dobre prace, niewykorzystane sloty",
    KWADRANT_WSPARCIE: "Wymaga wsparcia",
    KWADRANT_BRAK: "Brak prac w okresie",
}

ZALECENIE_DLA_GRUPY = {
    KWADRANT_FILAR: (
        "Utrzymać poziom. To naturalni liderzy zespołów i współautorzy-mentorzy "
        "dla osób z pozostałych grup."
    ),
    KWADRANT_POTENCJAL: (
        "Piszą dobre prace, ale za mało, żeby wypełnić sloty. Największy zwrot "
        "z wsparcia: czas na pisanie, włączenie do projektów i zespołów filarów."
    ),
    KWADRANT_ILOSC: (
        "Sloty pełne, ale słabiej punktowanymi pracami. Celować w czasopisma "
        "wyżej punktowane — każda lepsza praca wypiera słabszą ze slotu."
    ),
    KWADRANT_WSPARCIE: (
        "Niskie wypełnienie i jakość poniżej mediany {dopelniacz}. Rozmowa "
        "o planach publikacyjnych, współautorstwo z filarami."
    ),
    KWADRANT_BRAK: (
        "Brak prac zaliczonych do ewaluacji. Najpierw sprawdzić kompletność "
        "danych (przypisanie dyscypliny, afiliacje), potem plany publikacyjne."
    ),
}

ZERO = Decimal("0")

MIN_OSOB_NA_WYKRES = 3
MIN_OSOB_NOWA_STRONA = 6
# Na wykresie bąbelkowym podpisujemy najwyżej tylu osób (największe punkty).
MAX_PODPISOW_WYKRESU = 30

RODZAJ_JEDNOSTKA = "jednostka"
RODZAJ_WYDZIAL = "wydzial"

# Odmiana nazwy obiektu zestawienia w tekstach wniosków i szablonu.
SLOWA = {
    RODZAJ_JEDNOSTKA: {
        "mianownik": "Jednostka",
        "dopelniacz": "jednostki",
        "miejscownik": "jednostce",
        "odbiorca": "kierownika jednostki",
    },
    RODZAJ_WYDZIAL: {
        "mianownik": "Wydział",
        "dopelniacz": "wydziału",
        "miejscownik": "wydziale",
        "odbiorca": "władz wydziału",
    },
}


def _d(wartosc) -> Decimal:
    return wartosc if wartosc is not None else ZERO


def _iloraz(licznik: Decimal, mianownik: Decimal) -> Decimal | None:
    if not mianownik:
        return None
    return licznik / mianownik


@dataclass
class WierszAutora:
    metryka: MetrykaAutora
    wypelnienie: Decimal  # %
    status_wypelnienia: str
    punkty: Decimal
    udzial_w_maksimum_punktow: Decimal  # 0..100, względem najlepszego w grupie
    srednia: Decimal  # punkty za slot (nazbierane)
    wzgledna_jakosc: Decimal | None  # średnia / mediana grupy
    status_jakosci: str
    kwadrant: str
    brakujace_sloty: Decimal
    potencjal_punktow: Decimal
    slowa: dict = field(default_factory=lambda: SLOWA[RODZAJ_JEDNOSTKA])

    @property
    def autor(self):
        return self.metryka.autor

    @property
    def opis_kwadrantu(self):
        return opis_kwadrantu(self.kwadrant, self.slowa)


@dataclass
class PrzedzialPunktow:
    etykieta: str
    liczba_prac: int = 0
    sloty: Decimal = ZERO
    procent_slotow: Decimal = ZERO


@dataclass
class GrupaDyscypliny:
    dyscyplina: object
    wiersze: list[WierszAutora]
    liczba_autorow: int
    slot_maksymalny: Decimal
    slot_nazbierany: Decimal
    punkty: Decimal
    wypelnienie: Decimal | None
    srednia: Decimal | None
    mediana_sredniej: Decimal | None
    srednia_uczelni: Decimal | None
    brakujace_sloty: Decimal
    potencjal_punktow: Decimal
    struktura: list[PrzedzialPunktow]
    procent_slotow_slabych_prac: Decimal | None
    udzial_top3: Decimal | None
    wnioski: list[str] = field(default_factory=list)
    slowa: dict = field(default_factory=lambda: SLOWA[RODZAJ_JEDNOSTKA])

    @property
    def wiersze_wg_sredniej(self):
        return sorted(
            self.wiersze,
            key=lambda w: (-w.srednia, -w.punkty, w.autor.nazwisko or ""),
        )

    @property
    def wiersze_wg_potencjalu(self):
        return [
            w
            for w in sorted(self.wiersze, key=lambda w: -w.potencjal_punktow)
            if w.potencjal_punktow > 0
        ][:10]

    @property
    def osoby_z_pracami(self):
        return sum(1 for w in self.wiersze if w.kwadrant != KWADRANT_BRAK)

    @property
    def pokaz_wykres(self):
        """Wykres bąbelkowy ma sens dopiero od kilku osób z pracami."""
        return self.osoby_z_pracami >= MIN_OSOB_NA_WYKRES

    @property
    def podpisane_wszystkie(self):
        return self.osoby_z_pracami <= MAX_PODPISOW_WYKRESU

    @property
    def mala(self):
        """Mała dyscyplina (1–2 osoby): zwarty układ — karty osób mówią
        wszystko, kafelki i tabela tylko by je powtarzały."""
        return self.liczba_autorow < MIN_OSOB_NA_WYKRES

    @property
    def duza(self):
        """Duża dyscyplina zaczyna się od nowej strony; małe płyną dalej,
        żeby nie zostawiać stron z dwiema linijkami."""
        return self.liczba_autorow >= MIN_OSOB_NOWA_STRONA

    @property
    def zalecenia_wg_grup(self):
        """[(opis grupy, zalecenie, [wiersze]), …] — tylko niepuste grupy."""
        wynik = []
        for kwadrant, zalecenie in ZALECENIE_DLA_GRUPY.items():
            osoby = [w for w in self.wiersze if w.kwadrant == kwadrant]
            if osoby:
                wynik.append(
                    (
                        opis_kwadrantu(kwadrant, self.slowa),
                        zalecenie.format(**self.slowa),
                        osoby,
                    )
                )
        return wynik

    @property
    def status_wypelnienia(self):
        return status_wypelnienia_procent(self.wypelnienie)

    @property
    def max_srednia(self):
        return max((w.srednia for w in self.wiersze), default=ZERO)


@dataclass
class PodsumowanieJednostki:
    """Jednostka w zestawieniu wydziału — sumy po wszystkich dyscyplinach."""

    jednostka: object
    liczba_autorow: int
    slot_maksymalny: Decimal
    slot_nazbierany: Decimal
    punkty: Decimal
    potencjal_punktow: Decimal

    @property
    def wypelnienie(self):
        return _iloraz(self.slot_nazbierany * 100, self.slot_maksymalny)

    @property
    def status_wypelnienia(self):
        return status_wypelnienia_procent(self.wypelnienie)

    @property
    def srednia(self):
        return _iloraz(self.punkty, self.slot_nazbierany)


@dataclass
class MetrykiJednostki:
    """Zestawienie jednostki albo — ``rodzaj == RODZAJ_WYDZIAL`` — wydziału
    (wtedy ``jednostka`` to korzeń drzewa, a ``jednostki`` — podsumowanie
    jednostek wydziału)."""

    jednostka: object
    okres: object
    grupy: list[GrupaDyscypliny]
    rodzaj: str = RODZAJ_JEDNOSTKA
    jednostki: list[PodsumowanieJednostki] = field(default_factory=list)

    @property
    def wydzial(self):
        return self.rodzaj == RODZAJ_WYDZIAL

    @property
    def slowa(self):
        return SLOWA[self.rodzaj]

    @property
    def liczba_autorow(self):
        return len({w.metryka.autor_id for g in self.grupy for w in g.wiersze})

    @property
    def pusty(self):
        return not self.grupy

    @property
    def wiele_dyscyplin(self):
        return len(self.grupy) > 1

    @property
    def punkty(self):
        return sum((g.punkty for g in self.grupy), ZERO)

    @property
    def slot_maksymalny(self):
        return sum((g.slot_maksymalny for g in self.grupy), ZERO)

    @property
    def slot_nazbierany(self):
        return sum((g.slot_nazbierany for g in self.grupy), ZERO)

    @property
    def wypelnienie(self):
        if not self.slot_maksymalny:
            return None
        return self.slot_nazbierany / self.slot_maksymalny * 100

    @property
    def status_wypelnienia(self):
        return status_wypelnienia_procent(self.wypelnienie)

    @property
    def potencjal_punktow(self):
        return sum((g.potencjal_punktow for g in self.grupy), ZERO)

    @property
    def brakujace_sloty(self):
        return sum((g.brakujace_sloty for g in self.grupy), ZERO)


def opis_kwadrantu(kwadrant, slowa) -> str:
    """Nazwa grupy osób, np. „Filar jednostki” / „Filar wydziału”."""
    return OPIS_KWADRANTU[kwadrant].format(**slowa)


def status_wypelnienia_procent(procent: Decimal | None) -> str:
    if not procent:
        return BRAK
    if procent >= PROG_WYPELNIENIA_DOBRY:
        return DOBRY
    if procent >= PROG_WYPELNIENIA_SREDNI:
        return SREDNI
    return SLABY


def _status_wypelnienia(metryka) -> str:
    if not metryka.slot_nazbierany:
        return BRAK
    return status_wypelnienia_procent(_d(metryka.procent_wykorzystania_slotow))


def _status_jakosci(wzgledna: Decimal | None) -> str:
    if wzgledna is None:
        return BRAK
    if wzgledna >= PROG_JAKOSCI_WYSOKI:
        return DOBRY
    if wzgledna <= PROG_JAKOSCI_NISKI:
        return SLABY
    return SREDNI


def _kwadrant(metryka, srednia, mediana) -> str:
    if not metryka.slot_nazbierany:
        return KWADRANT_BRAK
    wysokie_wypelnienie = (
        _d(metryka.procent_wykorzystania_slotow) >= PROG_KWADRANTU_WYPELNIENIE
    )
    dobra_jakosc = mediana is None or srednia >= mediana
    if wysokie_wypelnienie:
        return KWADRANT_FILAR if dobra_jakosc else KWADRANT_ILOSC
    return KWADRANT_POTENCJAL if dobra_jakosc else KWADRANT_WSPARCIE


def _fmt(wartosc: Decimal, miejsca=0) -> str:
    return f"{wartosc:.{miejsca}f}".replace(".", ",")


def _struktura_punktacji(metryki) -> tuple[list[PrzedzialPunktow], Decimal | None]:
    """Rozkład slotów wypełnionych (prace nazbierane) wg punktacji pracy."""
    from bpp.models.cache import Cache_Punktacja_Autora_Query

    pary = {
        (m.autor_id, tuple(rekord_id))
        for m in metryki
        for rekord_id in (m.prace_nazbierane or [])
    }
    if not pary:
        return rozklad_punktacji([])

    dyscyplina_id = metryki[0].dyscyplina_naukowa_id
    # TupleField przyjmuje identyfikatory jako LISTY [content_type, pk] (tak
    # jak przychodzą z JSON-a) — krotki Django rozwija i zapytanie pada na
    # „operator nie istnieje: integer[] = integer”.
    wszystkie_rekordy = [list(rekord_id) for rekord_id in {r for _, r in pary}]
    prace = Cache_Punktacja_Autora_Query.objects.filter(
        dyscyplina_id=dyscyplina_id,
        autor_id__in={autor_id for autor_id, _ in pary},
        rekord_id__in=wszystkie_rekordy,
    ).values_list("autor_id", "rekord_id", "slot", "rekord__punkty_kbn")

    return rozklad_punktacji(
        (slot, punkty_kbn)
        for autor_id, rekord_id, slot, punkty_kbn in prace
        if (autor_id, tuple(rekord_id)) in pary
    )


def rozklad_punktacji(prace) -> tuple[list[PrzedzialPunktow], Decimal | None]:
    """Rozłóż ``prace`` — pary (slot, punktacja pracy) — na przedziały
    punktowe. Zwraca przedziały i procent slotów wypełnionych pracami
    poniżej ``PROG_SLABYCH_PRAC`` (``None``, gdy brak slotów)."""
    przedzialy = [PrzedzialPunktow(etykieta=et) for _, et in PRZEDZIALY_PUNKTOW]
    suma_slotow = ZERO
    slabe = ZERO
    for slot, punkty_kbn in prace:
        slot, punkty_kbn = _d(slot), _d(punkty_kbn)
        for (prog, _), przedzial in zip(PRZEDZIALY_PUNKTOW, przedzialy, strict=True):
            if punkty_kbn >= prog:
                przedzial.liczba_prac += 1
                przedzial.sloty += slot
                break
        suma_slotow += slot
        if punkty_kbn < PROG_SLABYCH_PRAC:
            slabe += slot

    if not suma_slotow:
        return przedzialy, None

    for przedzial in przedzialy:
        przedzial.procent_slotow = przedzial.sloty / suma_slotow * 100
    return przedzialy, slabe / suma_slotow * 100


def _wnioski(grupa: GrupaDyscypliny, slowa: dict) -> list[str]:
    wnioski = []
    nazwa = grupa.dyscyplina.nazwa

    if grupa.wypelnienie is not None:
        wnioski.append(
            f"{slowa['mianownik']} wypełnia {_fmt(grupa.wypelnienie)}% dostępnych slotów "
            f"w dyscyplinie {nazwa} ({_fmt(grupa.slot_nazbierany, 2)} "
            f"z {_fmt(grupa.slot_maksymalny, 2)})."
        )

    if grupa.brakujace_sloty > 0 and grupa.potencjal_punktow > 0:
        wnioski.append(
            f"Niewykorzystane sloty: {_fmt(grupa.brakujace_sloty, 2)}. Przy medianie "
            f"jakości {slowa['dopelniacz']} to szacunkowo "
            f"+{_fmt(grupa.potencjal_punktow)} pkt "
            "— największy potencjał mają osoby z tabeli „Gdzie leży potencjał”."
        )

    if grupa.srednia is not None and grupa.srednia_uczelni:
        roznica = (grupa.srednia / grupa.srednia_uczelni - 1) * 100
        if abs(roznica) < 2:
            porownanie = "na poziomie średniej"
        else:
            kierunek = "powyżej" if roznica > 0 else "poniżej"
            porownanie = f"{_fmt(abs(roznica))}% {kierunek} średniej"
        wnioski.append(
            f"Średnia za slot w {slowa['miejscownik']} ({_fmt(grupa.srednia, 1)} pkt) jest "
            f"{porownanie} całej uczelni w tej dyscyplinie "
            f"({_fmt(grupa.srednia_uczelni, 1)} pkt)."
        )

    if (
        grupa.udzial_top3 is not None
        and grupa.liczba_autorow > 5
        and grupa.udzial_top3 >= 50
    ):
        wnioski.append(
            f"Trzy osoby dają {_fmt(grupa.udzial_top3)}% punktów {slowa['dopelniacz']} — "
            "wynik zależy od wąskiej grupy; odejście jednej z nich byłoby "
            "odczuwalne."
        )

    if grupa.procent_slotow_slabych_prac is not None and (
        grupa.procent_slotow_slabych_prac >= 25
    ):
        wnioski.append(
            f"{_fmt(grupa.procent_slotow_slabych_prac)}% wypełnionych slotów to "
            "prace za mniej niż 70 pkt — zastąpienie ich pracami za 100+ pkt "
            "najszybciej podnosi wynik."
        )

    bez_prac = [w for w in grupa.wiersze if w.kwadrant == KWADRANT_BRAK]
    if bez_prac:
        wnioski.append(
            f"Osoby bez żadnej pracy zaliczonej do ewaluacji: {len(bez_prac)} "
            f"z {grupa.liczba_autorow}."
        )

    return wnioski


def _srednia_uczelni(uczelnia, okres, dyscyplina_id) -> Decimal | None:
    agg = scope_metryki(
        MetrykaAutora.objects.filter(dyscyplina_naukowa_id=dyscyplina_id),
        uczelnia,
        okres,
    ).aggregate(p=Sum("punkty_nazbierane"), s=Sum("slot_nazbierany"))
    return _iloraz(_d(agg["p"]), _d(agg["s"]))


def _grupa(metryki, uczelnia, okres, slowa) -> GrupaDyscypliny:
    srednie_niezerowe = [
        _d(m.srednia_za_slot_nazbierana) for m in metryki if m.slot_nazbierany
    ]
    mediana = Decimal(median(srednie_niezerowe)) if srednie_niezerowe else None
    max_punktow = max((_d(m.punkty_nazbierane) for m in metryki), default=ZERO)
    # Szacunek wartości wolnego slotu: mediana jakości w jednostce (realne
    # tempo, a nie najlepszy autor).
    wartosc_slotu = mediana or ZERO

    wiersze = []
    for m in metryki:
        srednia = _d(m.srednia_za_slot_nazbierana)
        wzgledna = srednia / mediana if (mediana and m.slot_nazbierany) else None
        brakujace = max(_d(m.slot_maksymalny) - _d(m.slot_nazbierany), ZERO)
        potencjal = brakujace * wartosc_slotu
        kwadrant = _kwadrant(m, srednia, mediana)
        wiersze.append(
            WierszAutora(
                metryka=m,
                wypelnienie=_d(m.procent_wykorzystania_slotow),
                status_wypelnienia=_status_wypelnienia(m),
                punkty=_d(m.punkty_nazbierane),
                udzial_w_maksimum_punktow=(
                    _d(m.punkty_nazbierane) / max_punktow * 100 if max_punktow else ZERO
                ),
                srednia=srednia,
                wzgledna_jakosc=wzgledna,
                status_jakosci=_status_jakosci(wzgledna),
                kwadrant=kwadrant,
                brakujace_sloty=brakujace,
                potencjal_punktow=potencjal,
                slowa=slowa,
            )
        )

    slot_max = sum((_d(m.slot_maksymalny) for m in metryki), ZERO)
    slot_nazb = sum((_d(m.slot_nazbierany) for m in metryki), ZERO)
    punkty = sum((_d(m.punkty_nazbierane) for m in metryki), ZERO)
    top3 = sum(sorted((w.punkty for w in wiersze), reverse=True)[:3], ZERO)
    struktura, procent_slabych = _struktura_punktacji(metryki)

    grupa = GrupaDyscypliny(
        dyscyplina=metryki[0].dyscyplina_naukowa,
        wiersze=sorted(wiersze, key=lambda w: (-w.punkty, w.autor.nazwisko or "")),
        liczba_autorow=len(metryki),
        slot_maksymalny=slot_max,
        slot_nazbierany=slot_nazb,
        punkty=punkty,
        wypelnienie=(slot_nazb / slot_max * 100 if slot_max else None),
        srednia=_iloraz(punkty, slot_nazb),
        mediana_sredniej=mediana,
        srednia_uczelni=_srednia_uczelni(
            uczelnia, okres, metryki[0].dyscyplina_naukowa_id
        ),
        brakujace_sloty=sum((w.brakujace_sloty for w in wiersze), ZERO),
        potencjal_punktow=sum((w.potencjal_punktow for w in wiersze), ZERO),
        struktura=struktura,
        procent_slotow_slabych_prac=procent_slabych,
        udzial_top3=(top3 / punkty * 100) if punkty else None,
        slowa=slowa,
    )
    grupa.wnioski = _wnioski(grupa, slowa)
    return grupa


def _zbuduj(obiekt, metryki, uczelnia, okres, rodzaj) -> MetrykiJednostki:
    metryki = scope_metryki(
        metryki.select_related("autor", "dyscyplina_naukowa", "jednostka"),
        uczelnia,
        okres,
    )
    wg_dyscypliny = defaultdict(list)
    for m in metryki:
        wg_dyscypliny[m.dyscyplina_naukowa_id].append(m)

    slowa = SLOWA[rodzaj]
    grupy = [_grupa(lista, uczelnia, okres, slowa) for lista in wg_dyscypliny.values()]
    grupy.sort(key=lambda g: (-g.punkty, g.dyscyplina.nazwa))
    return MetrykiJednostki(jednostka=obiekt, okres=okres, grupy=grupy, rodzaj=rodzaj)


def zbuduj_metryki_jednostki(jednostka, uczelnia, okres) -> MetrykiJednostki:
    """Zbuduj raport dla ``jednostka`` w ``okres`` (zawężony do ``uczelnia``)."""
    return _zbuduj(
        jednostka,
        MetrykaAutora.objects.filter(jednostka=jednostka),
        uczelnia,
        okres,
        RODZAJ_JEDNOSTKA,
    )


def podsumowanie_jednostek(grupy) -> list[PodsumowanieJednostki]:
    """Sumy wierszy wszystkich dyscyplin wg jednostki autora, od największej
    liczby punktów. Potencjał liczony medianą WYDZIAŁU w danej dyscyplinie."""
    wg_jednostki = defaultdict(list)
    for grupa in grupy:
        for w in grupa.wiersze:
            wg_jednostki[w.metryka.jednostka_id].append(w)

    wynik = [
        PodsumowanieJednostki(
            jednostka=wiersze[0].metryka.jednostka,
            liczba_autorow=len({w.metryka.autor_id for w in wiersze}),
            slot_maksymalny=sum((_d(w.metryka.slot_maksymalny) for w in wiersze), ZERO),
            slot_nazbierany=sum((_d(w.metryka.slot_nazbierany) for w in wiersze), ZERO),
            punkty=sum((w.punkty for w in wiersze), ZERO),
            potencjal_punktow=sum((w.potencjal_punktow for w in wiersze), ZERO),
        )
        for wiersze in wg_jednostki.values()
    ]
    wynik.sort(key=lambda p: (-p.punkty, p.jednostka.nazwa))
    return wynik


def zbuduj_metryki_wydzialu(wydzial, uczelnia, okres) -> MetrykiJednostki:
    """Zbuduj raport całego wydziału — ``wydzial`` to korzeń drzewa jednostek;
    wchodzą metryki autorów z wszystkich jednostek tego drzewa."""
    from bpp.models import Jednostka

    # tree_id z bazy, nie z obiektu: MPTT przenumerowuje drzewa przy
    # wstawianiu korzeni, więc wartość w pamięci bywa nieaktualna.
    tree_id = Jednostka.objects.values_list("tree_id", flat=True).get(pk=wydzial.pk)
    raport = _zbuduj(
        wydzial,
        MetrykaAutora.objects.filter(jednostka__tree_id=tree_id),
        uczelnia,
        okres,
        RODZAJ_WYDZIAL,
    )
    raport.jednostki = podsumowanie_jednostek(raport.grupy)
    return raport
