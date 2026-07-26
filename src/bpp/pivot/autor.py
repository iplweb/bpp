"""Rejestr tabeli krzyżowej dla modelu Autor.

Trzy bazy agregacji, bo metryka decyduje o ścieżce JOIN-u:

* K (kadrowa) — sam bpp_autor, metryka „liczba autorów";
* P (prace)   — przez `autorzy` (mat. view) do rekordu, metryka „liczba prac";
* U (udziały) — przez `cache_punktacja_autora_query` (ma FK do Rekordu, więc
  widzi rok), metryki Σ slotów i Σ pkdaut.

Ten moduł implementuje TYLKO bazę K — Zadanie 8 planu. Bazy P i U (wraz z
wymiarami publikacyjnymi o `expr` per-bazowym: rok, dyscyplina, jednostka
pracy, typ odpowiedzialności, charakter formalny) to Zadanie 10.

Świadomie NIE ma Σ IF / Σ PK / Σ cytowań: to wartości rekordowe, które
sumowane per autor zwielokrotniają się między współautorami. Kto ich chce,
używa pivota REKORDOWEGO z wymiarem „jednostka" — tam strategia par liczy je
poprawnie.
"""

from django.db.models import BooleanField, Case, Count, Sum, Value, When

from . import core
from .core import PivotDimension, PivotMetric, PivotTooLargeError, buduj_macierz

BAZA_KADROWA = "K"
BAZA_PRACE = "P"
BAZA_UDZIALY = "U"
WSZYSTKIE_BAZY = (BAZA_KADROWA, BAZA_PRACE, BAZA_UDZIALY)

DEFAULT_ROW = "jednostka"
DEFAULT_METRIC = "liczba_autorow"


def _ma_wartosc(pole):
    """Adnotacja TAK/NIE dla pola tekstowego, które bywa puste albo NULL."""
    return Case(
        When(**{f"{pole}__isnull": True}, then=Value(False)),
        When(**{pole: ""}, then=Value(False)),
        default=Value(True),
        output_field=BooleanField(),
    )


def _ma_wypelnione(pole):
    """Adnotacja TAK/NIE dla pola, które bywa NULL, ale nigdy pustym stringiem
    (FK-i oraz `system_kadrowy_id`, który mimo nazwy jest zwykłym
    PositiveIntegerField, nie FK-iem)."""
    return Case(
        When(**{f"{pole}__isnull": True}, then=Value(False)),
        default=Value(True),
        output_field=BooleanField(),
    )


def _autorski(expr):
    """Wymiar autorski — ta sama ścieżka we wszystkich bazach."""
    return {baza: expr for baza in WSZYSTKIE_BAZY}


DIMENSIONS: dict[str, PivotDimension] = {
    "jednostka": PivotDimension(
        "jednostka",
        "Aktualna jednostka",
        _autorski("aktualna_jednostka_id"),
        allow_column=False,
        label_kind="fk",
        fk_model="bpp.Jednostka",
    ),
    "tytul": PivotDimension(
        "tytul",
        "Tytuł naukowy",
        _autorski("tytul_id"),
        label_kind="fk",
        fk_model="bpp.Tytul",
    ),
    "stopien_sluzbowy": PivotDimension(
        "stopien_sluzbowy",
        "Stopień służbowy",
        _autorski("stopien_sluzbowy_id"),
        label_kind="fk",
        fk_model="bpp.StopienSluzbowy",
    ),
    "funkcja": PivotDimension(
        "funkcja",
        "Aktualna funkcja",
        _autorski("aktualna_funkcja_id"),
        label_kind="fk",
        fk_model="bpp.Funkcja_Autora",
    ),
    "plec": PivotDimension(
        "plec",
        "Płeć",
        _autorski("plec_id"),
        label_kind="fk",
        fk_model="bpp.Plec",
    ),
    "ma_orcid": PivotDimension(
        "ma_orcid",
        "Ma ORCID",
        _autorski("ma_orcid"),
        label_kind="bool",
        annotation=_ma_wartosc("orcid"),
    ),
    "orcid_w_pbn": PivotDimension(
        "orcid_w_pbn",
        "ORCID w PBN",
        # Prawdziwy BooleanField(null=True) na modelu — bez adnotacji: grupa
        # None (nieustawione) renderuje się jako BRAK w _label_mapping.
        _autorski("orcid_w_pbn"),
        label_kind="bool",
    ),
    "ma_pbn_uid": PivotDimension(
        "ma_pbn_uid",
        "Ma PBN UID",
        _autorski("ma_pbn_uid"),
        label_kind="bool",
        annotation=_ma_wypelnione("pbn_uid"),
    ),
    "ma_email": PivotDimension(
        "ma_email",
        "Ma e-mail",
        _autorski("ma_email"),
        label_kind="bool",
        annotation=_ma_wartosc("email"),
    ),
    "ma_id_kadrowy": PivotDimension(
        "ma_id_kadrowy",
        "Ma ID kadrowy",
        _autorski("ma_id_kadrowy"),
        label_kind="bool",
        annotation=_ma_wypelnione("system_kadrowy_id"),
    ),
    "rok_urodzenia": PivotDimension(
        "rok_urodzenia",
        "Rok urodzenia",
        _autorski("urodzony__year"),
    ),
    "autor": PivotDimension(
        "autor",
        "Autor",
        _autorski("pk"),
        allow_column=False,
        label_kind="fk",
        fk_model="bpp.Autor",
    ),
}

METRICS: dict[str, PivotMetric] = {
    "liczba_autorow": PivotMetric(
        "liczba_autorow",
        "Liczba autorów",
        None,
        baza=BAZA_KADROWA,
        distinct_field="pk",
    ),
}


def parse_pivot_params_autor(GET):
    """Wiersz/kolumna/metryka dla pivota autorskiego.

    Metryka wybiera bazę; wymiar niedostępny w tej bazie jest cicho
    zastępowany domyślnym (analogicznie do allow_column w pivocie
    rekordowym) — parametry przychodzą z linków i zakładek, więc twardy
    błąd byłby wrogi.
    """
    metric = METRICS.get(GET.get("pivot_val") or "", METRICS[DEFAULT_METRIC])
    row = DIMENSIONS.get(GET.get("pivot_row") or "", DIMENSIONS[DEFAULT_ROW])
    if row.expr_dla(metric.baza) is None:
        row = DIMENSIONS[DEFAULT_ROW]
    col = DIMENSIONS.get(GET.get("pivot_col") or "")
    if col is not None and (
        not col.allow_column or col.key == row.key or col.expr_dla(metric.baza) is None
    ):
        col = None
    return row, col, metric


def zbuduj_pivot_autora(base_qs, row_dim, col_dim, metric):
    """Macierz pivota autorskiego — czysty SQL (COUNT DISTINCT / SUM).

    Dedup: agregujemy na ŚWIEŻYM querysecie Autora zawężonym do PK-ów
    wejściowego zbioru, bo filtry DjangoQL mogą łączyć relacje do-wielu
    i zwielokrotniać wiersze autora (ta sama zasada, co _dedup_strategy
    w pivocie rekordowym).

    UWAGA o nośności dedupu: w bazie K (metryka Count(pk, distinct=True))
    dedup jest jeszcze REDUNDANTNY — DISTINCT w agregacie sam zwija
    zwielokrotnione wiersze, co sprawdzono empirycznie (po usunięciu tej
    linii cała suita test_pivot_autor.py nadal przechodzi). Staje się
    nośny dopiero dla metryk Σ (bazy P/U), bo Sum nie ma jak rozpoznać
    duplikatu wiersza. Zostaje tu świadomie: jest poprawny, tani (podzapytanie
    po PK) i jednakowy dla wszystkich baz.
    """
    from bpp.models import Autor

    qs = Autor.objects.filter(pk__in=base_qs.values("pk")).order_by()
    baza = metric.baza

    adnotacje = {}
    for dim in (row_dim, col_dim):
        if dim is not None and dim.annotation is not None:
            adnotacje[dim.key] = dim.annotation
    if adnotacje:
        qs = qs.annotate(**adnotacje)

    grupy = [row_dim.alias(baza)]
    if col_dim is not None:
        grupy.append(col_dim.alias(baza))

    n_cells = qs.values(*grupy).distinct().count()
    if n_cells > core.PIVOT_MAX_CELLS:
        raise PivotTooLargeError(n_cells, core.PIVOT_MAX_CELLS, "cells")

    if metric.distinct_field:
        agregat = Count(metric.distinct_field, distinct=True)
    else:
        agregat = Sum(metric.field)

    triples = []
    for wiersz in qs.values(*grupy).annotate(val=agregat):
        rk = wiersz[row_dim.alias(baza)]
        ck = wiersz[col_dim.alias(baza)] if col_dim is not None else None
        val = wiersz["val"] or 0
        if baza != BAZA_KADROWA and not val:
            # Autor bez dorobku wchodzi przez LEFT JOIN z NULL-em — nie
            # zapychamy nim macierzy.
            continue
        triples.append((rk, ck, val))

    return buduj_macierz(triples, row_dim, col_dim, metric, False)


# Aliasy zgodności interfejsu — patrz docstring
# bpp.pivot.wybierz_rejestr_pivota().
parse_params = parse_pivot_params_autor
zbuduj = zbuduj_pivot_autora
