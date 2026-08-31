"""Generyczny silnik tabel krzyżowych (pivot) — bez wiedzy o konkretnym
modelu bazowym. Rejestry wymiarów/metryk per model (np. Rekord) żyją w
osobnych modułach obok (patrz `bpp.pivot.rekord`)."""

from dataclasses import dataclass, replace
from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Count, Sum

BRAK = "— brak —"

# Sortowanie wierszy macierzy. "etykieta" = kolejność naturalna wymiaru
# (rok/koszyk malejąco liczbowo, reszta alfabetycznie) — dokładnie ta, którą
# pivot miał od zawsze, więc jest domyślna. "suma" = po sumie brzegowej
# wiersza (kolumna RAZEM).
SORT_ETYKIETA = "etykieta"
SORT_SUMA = "suma"
SORTY = (SORT_ETYKIETA, SORT_SUMA)

# Wymiary, których naturalna kolejność jest MALEJĄCA (najnowszy rok u góry).
# Trzymane osobno, bo od tego zależy, czy przy `kierunek="asc"` narysować
# strzałkę w górę czy w dół — inaczej przy roku UI pokazywałby ▲ nad listą
# 2025, 2024, 2023.
WYMIARY_MALEJACE = ("rok", "koszyk_pk")

# Stronicowanie wierszy. Lista dozwolonych rozmiarów jest zamknięta celowo:
# bez niej ?pivot_per_page=999999 unieważnia całą bramkę i wracamy do
# renderowania dwóch tysięcy wierszy naraz.
DOZWOLONE_NA_STRONIE = (25, 50, 100, 250)
DOMYSLNIE_NA_STRONIE = 50


@dataclass(frozen=True)
class PivotDimension:
    key: str
    label: str
    expr: str | dict  # str = jedna ścieżka; dict = ścieżka per baza agregacji
    allow_column: bool = True
    autorzy: bool = False
    label_kind: str = "raw"  # raw | fk | choices_charakter_ogolny | pk_bucket | bool
    fk_model: str | None = None
    # Wyrażenie ORM dokładane przez annotate() PRZED grupowaniem. Konieczne
    # dla wymiarów, które nie są kolumną (np. „ma ORCID": grupowanie po
    # surowym polu dałoby tysiące grup, po jednej na wartość).
    annotation: object | None = None
    # Czy wartość wymiaru przypisuje PRACĘ do dokładnie jednej grupy (bo jest
    # atrybutem samego rekordu, np. rok albo charakter formalny). Fałsz =
    # grupy dzielą populację inaczej niż po pracach (np. po jednostce autora),
    # więc ta sama praca wpada do kilku grup i sumy komórek przewyższają
    # liczbę unikatowych prac — wtedy pod tabelą MUSI stanąć adnotacja o
    # dublowaniu (PivotResult.has_autorzy_dim). Czyta to rejestr autorski
    # (`bpp.pivot.autor`); w rejestrze rekordowym tę samą rolę pełni flaga
    # `autorzy`, bo tam grupy dzielą populację prac wprost.
    atrybut_rekordu: bool = False

    def resolve_model(self):
        from django.apps import apps

        return apps.get_model(*self.fk_model.split(".")) if self.fk_model else None

    def expr_dla(self, baza=None):
        """Ścieżka ORM w danej bazie agregacji; None = niedostępny.

        Rejestr rekordowy (`bpp.pivot.rekord`) przekazuje `expr` jako zwykły
        `str` — dla niego ta metoda zwraca ten sam `expr` niezależnie od
        argumentu (a widok woła ją z `metric.baza`, czyli domyślnym "K", dla
        OBU rejestrów — patrz ZapytanieView._pivot_context).
        """
        if isinstance(self.expr, dict):
            return self.expr.get(baza)
        return self.expr

    def alias(self, baza=None):
        """Nazwa pola do values()/GROUP BY — alias adnotacji albo ścieżka."""
        return self.key if self.annotation is not None else self.expr_dla(baza)


@dataclass(frozen=True)
class PivotMetric:
    key: str
    label: str
    field: str | None  # None → Count("id"); inaczej Sum(field)
    baza: str = "K"  # która baza agregacji (rejestr autorski); rekordowy: "K"
    distinct_field: str | None = None  # ustawione → Count(field, distinct=True)


@dataclass(frozen=True)
class PivotWidok:
    """Jak POKAZAĆ policzoną macierz — kolejność wierszy i wycinek strony.

    Świadomie odsunięte od `PivotResult` (co policzono) i od rejestrów
    (`bpp.pivot.rekord` / `.autor`): dzięki temu `parse_params()` i jej pięć
    miejsc wywołania zostają nietknięte, a sortowanie/stronicowanie jest
    jedną, wspólną implementacją dla obu wejść (multiseek i /zapytanie/).
    """

    sort: str = SORT_ETYKIETA
    kierunek: str | None = None  # "asc" | "desc"; None = naturalny dla sortu
    strona: int = 1
    na_stronie: int = DOMYSLNIE_NA_STRONIE  # 0 = bez stronicowania (eksport)

    @property
    def kierunek_efektywny(self):
        """Kierunek po rozwinięciu `None`. Dla etykiety naturalny jest
        rosnący (czyli kolejność z `_labels`), dla sumy — malejący, bo
        „kto ma najwięcej" to jedyne pytanie, które ludzie zadają."""
        if self.kierunek in ("asc", "desc"):
            return self.kierunek
        return "desc" if self.sort == SORT_SUMA else "asc"

    def bez_stronicowania(self):
        """Kopia z wyłączonym stronicowaniem — eksport respektuje sortowanie,
        ale zawsze zapisuje PEŁNĄ macierz (dlatego UI nie ma „pokaż
        wszystkie": od tego jest właśnie plik)."""
        return replace(self, na_stronie=0, strona=1)


def parse_widok(GET):
    """`PivotWidok` z parametrów GET (pivot_sort/pivot_dir/pivot_page/
    pivot_per_page). Każda wartość spoza whitelisty cicho degraduje do
    domyślnej — parametry są publiczne i wpisywane ręcznie."""
    sort = GET.get("pivot_sort")
    if sort not in SORTY:
        sort = SORT_ETYKIETA

    kierunek = GET.get("pivot_dir")
    if kierunek not in ("asc", "desc"):
        kierunek = None

    try:
        strona = int(GET.get("pivot_page") or 1)
    except (TypeError, ValueError):
        strona = 1
    strona = max(strona, 1)

    try:
        na_stronie = int(GET.get("pivot_per_page") or DOMYSLNIE_NA_STRONIE)
    except (TypeError, ValueError):
        na_stronie = DOMYSLNIE_NA_STRONIE
    if na_stronie not in DOZWOLONE_NA_STRONIE:
        na_stronie = DOMYSLNIE_NA_STRONIE

    return PivotWidok(
        sort=sort, kierunek=kierunek, strona=strona, na_stronie=na_stronie
    )


@dataclass
class PivotResult:
    rows: list
    cols: list
    cells: dict
    row_totals: dict
    col_totals: dict
    grand_total: object
    row_dim: PivotDimension
    col_dim: PivotDimension | None
    metric: PivotMetric
    has_autorzy_dim: bool

    def posortowane_wiersze(self, widok):
        """`self.rows` (już w kolejności naturalnej z `_labels`) przestawione
        wg `widok`.

        Rozstrzyganie remisów po etykiecie NIE jest kosmetyką: bez porządku
        totalnego dwa wiersze o równych sumach mogą wypaść w innej kolejności
        przy kolejnym żądaniu, a wtedy przy stronicowaniu ten sam wiersz
        pokazuje się na dwóch stronach albo znika z obu.
        """
        rosnaco = widok.kierunek_efektywny == "asc"
        if widok.sort == SORT_SUMA:
            znak = 1 if rosnaco else -1
            return sorted(
                self.rows,
                key=lambda p: (znak * (self.row_totals.get(p[0]) or 0), p[1].lower()),
            )
        # SORT_ETYKIETA: kolejność naturalna wymiaru albo jej odwrotność.
        return list(self.rows) if rosnaco else list(reversed(self.rows))

    def _naglowki_sortowania(self, widok):
        """Stan i cele linków sortujących. Liczone w Pythonie, bo szablon
        Django nie ma jak wyrazić „kliknięcie aktywnego nagłówka odwraca
        kierunek, nieaktywnego — bierze jego domyślny"."""
        eff = widok.kierunek_efektywny
        etykieta_aktywna = widok.sort == SORT_ETYKIETA
        suma_aktywna = widok.sort == SORT_SUMA
        # Dla roku kolejność naturalna ("asc") jest malejąca po wartości,
        # więc strzałkę trzeba odwrócić, inaczej ▲ stoi nad 2025, 2024, 2023.
        odwrocona = self.row_dim.key in WYMIARY_MALEJACE
        etykieta_rosnaco = (eff == "asc") != odwrocona
        return {
            "sort": widok.sort,
            "kierunek": eff,
            "sort_etykieta_aktywny": etykieta_aktywna,
            "sort_suma_aktywny": suma_aktywna,
            "sort_etykieta_strzalka": (
                ("▲" if etykieta_rosnaco else "▼") if etykieta_aktywna else ""
            ),
            "sort_etykieta_rosnaco": etykieta_rosnaco,
            "sort_suma_strzalka": (
                ("▲" if eff == "asc" else "▼") if suma_aktywna else ""
            ),
            "sort_suma_rosnaco": eff == "asc",
            "sort_etykieta_link": (
                "desc" if etykieta_aktywna and eff == "asc" else "asc"
            ),
            "sort_suma_link": "asc" if suma_aktywna and eff == "desc" else "desc",
        }

    def as_table(self, widok=None):
        """Zwraca strukturę gotową do iteracji w szablonie (bez indeksowania
        słownika po zmiennym kluczu). Puste komórki → ``None`` (szablon
        renderuje pustkę).

        Bez `widok` zachowuje się dokładnie tak, jak przed wprowadzeniem
        stronicowania — z tego wariantu korzysta m.in. eksport, gdy nie
        podano widoku.

        Z `widok` wiersze są przestawione i przycięte do jednej strony, ale
        `col_totals`/`grand_total` NADAL dotyczą całego zbioru (semantyka
        Excela). Szablon musi to napisać pod tabelą — inaczej redaktor
        zsumuje widoczną kolumnę i uzna, że liczby się nie zgadzają.
        """
        col_keys = [ck for ck, _ in self.cols]
        wiersze = self.rows if widok is None else self.posortowane_wiersze(widok)

        paginator = page_obj = None
        if widok is not None and widok.na_stronie:
            paginator = Paginator(wiersze, widok.na_stronie)
            # get_page(), nie page(): strona poza zakresem ma dać ostatnią,
            # a nie 404 — użytkownik potrafi zostać na ?pivot_page=40 po
            # zawężeniu filtra.
            page_obj = paginator.get_page(widok.strona)
            wiersze = list(page_obj.object_list)

        out = {
            "row_header": self.row_dim.label,
            "col_headers": [label for _, label in self.cols],
            "has_cols": bool(self.cols),
            "rows": [
                {
                    "label": rlabel,
                    "cells": (
                        [self.cells.get((rk, ck)) for ck in col_keys]
                        if col_keys
                        else [self.cells.get((rk, None))]
                    ),
                    "total": self.row_totals.get(rk),
                }
                for rk, rlabel in wiersze
            ],
            "col_totals": [self.col_totals.get(ck) for ck in col_keys],
            "grand_total": self.grand_total,
            "wszystkich_wierszy": len(self.rows),
        }
        if widok is not None:
            out.update(self._naglowki_sortowania(widok))
            out["paginator"] = paginator
            out["page_obj"] = page_obj
            out["is_paginated"] = bool(paginator and paginator.num_pages > 1)
            out["na_stronie"] = widok.na_stronie
            out["page_range"] = _zakres_stron(paginator, page_obj)
            out["dozwolone_na_stronie"] = DOZWOLONE_NA_STRONIE
        return out


# Bezpieczniki rozmiaru — pivot jest publiczny i celowo omija bramkę 25000
# oraz cap eksportu 5000. Bez tych limitów anonim z np. ?pivot_row=autor na
# pustym filtrze zbudowałby macierz z dziesiątkami tysięcy wierszy i (w
# strategii B) wciągnął miliony par autorstw do RAM-u.
# 50 000: przed wprowadzeniem stronicowania limit chronił głównie przed
# wypluciem gigantycznego HTML-a (cała macierz szła do DOM-u naraz). Teraz
# renderuje się co najwyżej `PivotWidok.na_stronie` wierszy, więc wąskim
# gardłem zostaje pamięć — a tę pilnuje PIVOT_MAX_PAIRS niżej.
PIVOT_MAX_CELLS = 50000  # maks. liczba niepustych komórek (rozmiar macierzy)
PIVOT_MAX_PAIRS = 200000  # maks. par (wymiar, rekord) w strategii B (pamięć)


class PivotTooLargeError(Exception):
    """Pivot dałby zbyt dużą macierz / zbiór par — trzeba zawęzić zapytanie."""

    def __init__(self, count, limit, kind):
        self.count = count
        self.limit = limit
        self.kind = kind  # "cells" | "pairs"
        super().__init__(f"Pivot przekroczył limit ({kind}): {count} > {limit}.")


def _annotate(metric):
    return Count("id") if metric.field is None else Sum(metric.field)


def zbuduj_pivot(base_qs, row_dim, col_dim, metric, *, model=None):
    if model is None:
        from bpp.models.cache import Rekord

        model = Rekord

    # KRYTYCZNE: bez wyczyszczenia orderingu, Meta.ordering/wejściowy
    # order_by() wchodzi do GROUP BY i rozbija grupy na mikro-grupy (K3).
    base_qs = base_qs.order_by()
    has_autorzy = row_dim.autorzy or bool(col_dim and col_dim.autorzy)
    group = [row_dim.expr] + ([col_dim.expr] if col_dim else [])

    # Bramka rozmiaru macierzy (tanie COUNT DISTINCT po stronie DB): liczba
    # niepustych komórek = liczba unikatowych kombinacji (wiersz, kolumna).
    n_cells = base_qs.values(*group).distinct().count()
    if n_cells > PIVOT_MAX_CELLS:
        raise PivotTooLargeError(n_cells, PIVOT_MAX_CELLS, "cells")

    # Strategia B agreguje w Pythonie po unikatowych parach (wymiar, rekord) —
    # ogranicz też ich liczbę, bo mało liczny wymiar wierszy (np. jednostka)
    # przy ogromnym zbiorze źródłowym i tak wciągnąłby wszystkie pary.
    if has_autorzy:
        n_pairs = base_qs.values(*group, "id").distinct().count()
        if n_pairs > PIVOT_MAX_PAIRS:
            raise PivotTooLargeError(n_pairs, PIVOT_MAX_PAIRS, "pairs")

    triples = (
        _pairs_strategy(base_qs, row_dim, col_dim, metric)
        if has_autorzy
        else _dedup_strategy(base_qs, row_dim, col_dim, metric, model)
    )
    return _build_matrix(triples, row_dim, col_dim, metric, has_autorzy)


def _dedup_strategy(base_qs, row_dim, col_dim, metric, model):
    """Strategia A: żaden z wymiarów nie idzie przez JOIN do autorzy — JOIN-y
    z filtrów wejściowego queryset'u mogą jednak mnożyć wiersze rekordu
    (K1), więc najpierw dedupujemy PK-i rekordów, a dopiero potem grupujemy
    (świeży queryset modelu bazowego bez wcześniejszych JOIN-ów)."""
    deduped = model.objects.filter(pk__in=base_qs.values("pk")).order_by()
    group = [row_dim.expr] + ([col_dim.expr] if col_dim else [])
    rows = deduped.values(*group).annotate(val=_annotate(metric))
    for r in rows:
        rk = r[row_dim.expr]
        ck = r[col_dim.expr] if col_dim else None
        yield rk, ck, r["val"] or 0


def _pairs_strategy(base_qs, row_dim, col_dim, metric):
    """Strategia B: co najmniej jeden wymiar idzie przez JOIN do autorzy.
    Liczymy unikatowe pary (wymiar, rekord) — rekord liczony raz per
    wartość wymiaru; Σ metryki po unikatowych parach (rekord, wymiar).
    Dublowanie MIĘDZY różnymi wartościami wymiaru jest zamierzone (§7)."""
    group = [row_dim.expr] + ([col_dim.expr] if col_dim else [])
    fields = group + ["id"] + ([metric.field] if metric.field else [])
    pairs = base_qs.values(*fields).distinct()
    seen = {}  # (rk, ck) -> set(rekord id) dla liczby
    sums = {}  # (rk, ck) -> Σ metryki po unikatowych rekordach
    # .iterator(): nie buduj _result_cache — liczbę par i tak ogranicza
    # bramka PIVOT_MAX_PAIRS w zbuduj_pivot().
    for p in pairs.iterator(chunk_size=2000):
        rk = p[row_dim.expr]
        ck = p[col_dim.expr] if col_dim else None
        rid = tuple(p["id"]) if isinstance(p["id"], list) else p["id"]
        s = seen.setdefault((rk, ck), set())
        if rid in s:
            continue
        s.add(rid)
        if metric.field is None:
            sums[(rk, ck)] = sums.get((rk, ck), 0) + 1
        else:
            sums[(rk, ck)] = sums.get((rk, ck), 0) + (p[metric.field] or 0)
    for (rk, ck), val in sums.items():
        yield rk, ck, val


def _build_matrix(triples, row_dim, col_dim, metric, has_autorzy):
    cells, row_totals, col_totals = {}, {}, {}
    row_keys, col_keys, grand = set(), set(), 0
    for rk, ck, val in triples:
        cells[(rk, ck)] = cells.get((rk, ck), 0) + val
        row_totals[rk] = row_totals.get(rk, 0) + val
        grand += val
        row_keys.add(rk)
        if col_dim:
            col_totals[ck] = col_totals.get(ck, 0) + val
            col_keys.add(ck)
    rows = _labels(row_keys, row_dim)
    cols = _labels(col_keys, col_dim) if col_dim else []
    return PivotResult(
        rows=rows,
        cols=cols,
        cells=cells,
        row_totals=row_totals,
        col_totals=col_totals,
        grand_total=grand,
        row_dim=row_dim,
        col_dim=col_dim,
        metric=metric,
        has_autorzy_dim=has_autorzy,
    )


def _labels(keys, dim):
    """Zwraca posortowaną listę (key, label). Rok/koszyk malejąco liczbowo,
    słowniki alfabetycznie po etykiecie."""
    mapping = _label_mapping(keys, dim)
    pairs = [(k, mapping.get(k, BRAK if k is None else str(k))) for k in keys]
    if dim.key in ("rok", "koszyk_pk"):
        pairs.sort(key=lambda p: (p[0] is None, -(p[0] or 0)))
    else:
        pairs.sort(key=lambda p: (p[1] == BRAK, p[1].lower()))
    return pairs


def _format_pk_bucket(value):
    """Formatuje wartość Decimal bez zbędnych zer i bez notacji naukowej
    (`Decimal(...).normalize()` + format 'g' daje np. "4E+1" dla 40 —
    nieczytelne w UI)."""
    d = Decimal(value)
    s = f"{d:f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def _label_mapping(keys, dim):
    if dim.label_kind == "raw":
        return {k: (BRAK if k is None else str(k)) for k in keys}
    if dim.label_kind == "pk_bucket":
        return {k: (BRAK if k is None else _format_pk_bucket(k)) for k in keys}
    if dim.label_kind == "choices_charakter_ogolny":
        from bpp.models.system.charakter_formalny import CHARAKTER_OGOLNY_CHOICES

        d = dict(CHARAKTER_OGOLNY_CHOICES)
        return {k: (BRAK if k is None else d.get(k, str(k))) for k in keys}
    if dim.label_kind == "fk":
        ids = [k for k in keys if k is not None]
        model = dim.resolve_model()
        objs = model.objects.in_bulk(ids)
        out = {None: BRAK}
        for k in ids:
            obj = objs.get(k)
            out[k] = str(obj) if obj is not None else BRAK
        return out
    if dim.label_kind == "bool":
        return {k: etykieta_bool(k) for k in keys}
    return {k: str(k) for k in keys}


def etykieta_bool(value):
    """Jedyny słownik TAK/NIE/brak dla wartości logicznych w wyjściach
    zapytania — wspólny dla pivota i dla eksportu listy autorów
    (`bpp.views.multiseek_export`). Bez niego to samo `orcid_w_pbn` jechało
    w macierzy jako „TAK", a w CSV-ce z tej samej strony jako „True"."""
    if value is True:
        return "TAK"
    if value is False:
        return "NIE"
    return BRAK


def _zakres_stron(paginator, page_obj):
    """Okno numerów stron do pagera; `None` oznacza wielokropek.

    `Paginator.get_elided_page_range()` przyjmuje argument, a szablon Django
    nie umie wywołać metody z argumentem — dlatego lista powstaje tutaj.
    """
    if paginator is None or page_obj is None:
        return []
    return [
        None if p == paginator.ELLIPSIS else p
        for p in paginator.get_elided_page_range(page_obj.number)
    ]


# Alias publiczny: nowy kod (np. bpp.pivot.autor) nie powinien wołać
# prywatnych nazw silnika.
buduj_macierz = _build_matrix
