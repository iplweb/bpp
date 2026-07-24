from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Sum

BRAK = "— brak —"


@dataclass(frozen=True)
class PivotDimension:
    key: str
    label: str
    expr: str
    allow_column: bool = True
    autorzy: bool = False
    label_kind: str = "raw"  # raw|fk|choices_charakter_ogolny|pk_bucket|autor
    fk_model: str | None = None
    fk_label_field: str = "nazwa"

    def resolve_model(self):
        from django.apps import apps

        return apps.get_model(*self.fk_model.split(".")) if self.fk_model else None


@dataclass(frozen=True)
class PivotMetric:
    key: str
    label: str
    field: str | None  # None → Count("id"); inaczej Sum(field)


DEFAULT_ROW = "rok"
DEFAULT_METRIC = "liczba"

# UWAGA: expr dla wymiarów FK to "<pole>_id" — values() zwraca surowe id,
# etykiety dociągamy hurtowo w zbuduj_pivot (label_kind="fk").
DIMENSIONS: dict[str, PivotDimension] = {
    "rok": PivotDimension("rok", "Rok", "rok"),
    "charakter_formalny": PivotDimension(
        "charakter_formalny",
        "Charakter formalny",
        "charakter_formalny_id",
        label_kind="fk",
        fk_model="bpp.Charakter_Formalny",
    ),
    "charakter_ogolny": PivotDimension(
        "charakter_ogolny",
        "Charakter ogólny (rodzaj)",
        "charakter_formalny__charakter_ogolny",
        label_kind="choices_charakter_ogolny",
    ),
    "typ_kbn": PivotDimension(
        "typ_kbn",
        "Typ MNiSW/MEiN",
        "typ_kbn_id",
        label_kind="fk",
        fk_model="bpp.Typ_KBN",
    ),
    "koszyk_pk": PivotDimension(
        "koszyk_pk",
        "Koszyk punktów PK",
        "punkty_kbn",
        label_kind="pk_bucket",
    ),
    "jezyk": PivotDimension(
        "jezyk",
        "Język",
        "jezyk_id",
        label_kind="fk",
        fk_model="bpp.Jezyk",
    ),
    "zrodlo": PivotDimension(
        "zrodlo",
        "Źródło",
        "zrodlo_id",
        allow_column=False,
        label_kind="fk",
        fk_model="bpp.Zrodlo",
    ),
    "jednostka": PivotDimension(
        "jednostka",
        "Jednostka",
        "autorzy__jednostka_id",
        allow_column=False,
        autorzy=True,
        label_kind="fk",
        fk_model="bpp.Jednostka",
    ),
    "dyscyplina": PivotDimension(
        "dyscyplina",
        "Dyscyplina naukowa",
        "autorzy__dyscyplina_naukowa_id",
        autorzy=True,
        label_kind="fk",
        fk_model="bpp.Dyscyplina_Naukowa",
    ),
    "autor": PivotDimension(
        "autor",
        "Autor",
        "autorzy__autor_id",
        allow_column=False,
        autorzy=True,
        label_kind="autor",
        fk_model="bpp.Autor",
    ),
}

METRICS: dict[str, PivotMetric] = {
    "liczba": PivotMetric("liczba", "Liczba prac", None),
    "punkty_kbn": PivotMetric("punkty_kbn", "Σ punkty PK", "punkty_kbn"),
    "impact_factor": PivotMetric("impact_factor", "Σ Impact Factor", "impact_factor"),
    "liczba_cytowan": PivotMetric(
        "liczba_cytowan", "Σ liczba cytowań", "liczba_cytowan"
    ),
    "punktacja_wewnetrzna": PivotMetric(
        "punktacja_wewnetrzna", "Σ punktacja wewnętrzna", "punktacja_wewnetrzna"
    ),
}


def parse_pivot_params(GET):
    row = DIMENSIONS.get(GET.get("pivot_row") or "", DIMENSIONS[DEFAULT_ROW])
    metric = METRICS.get(GET.get("pivot_val") or "", METRICS[DEFAULT_METRIC])
    col_key = GET.get("pivot_col") or ""
    col = DIMENSIONS.get(col_key)
    if col is not None and (not col.allow_column or col.key == row.key):
        col = None
    return row, col, metric


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


def _annotate(metric):
    return Count("id") if metric.field is None else Sum(metric.field)


def zbuduj_pivot(base_qs, row_dim, col_dim, metric):
    # KRYTYCZNE: bez wyczyszczenia orderingu, Meta.ordering/wejściowy
    # order_by() wchodzi do GROUP BY i rozbija grupy na mikro-grupy (K3).
    base_qs = base_qs.order_by()
    has_autorzy = row_dim.autorzy or bool(col_dim and col_dim.autorzy)
    triples = (
        _pairs_strategy(base_qs, row_dim, col_dim, metric)
        if has_autorzy
        else _dedup_strategy(base_qs, row_dim, col_dim, metric)
    )
    return _build_matrix(triples, row_dim, col_dim, metric, has_autorzy)


def _dedup_strategy(base_qs, row_dim, col_dim, metric):
    """Strategia A: żaden z wymiarów nie idzie przez JOIN do autorzy — JOIN-y
    z filtrów wejściowego queryset'u mogą jednak mnożyć wiersze rekordu
    (K1), więc najpierw dedupujemy PK-i rekordów, a dopiero potem grupujemy
    (świeży queryset bez wcześniejszych JOIN-ów)."""
    from bpp.models.cache import Rekord

    deduped = Rekord.objects.filter(pk__in=base_qs.values("pk")).order_by()
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
    for p in pairs:
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
        col_totals[ck] = col_totals.get(ck, 0) + val
        grand += val
        row_keys.add(rk)
        if col_dim:
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
    if dim.label_kind in ("fk", "autor"):
        ids = [k for k in keys if k is not None]
        model = dim.resolve_model()
        objs = model.objects.in_bulk(ids)
        out = {None: BRAK}
        for k in ids:
            obj = objs.get(k)
            out[k] = str(obj) if obj is not None else BRAK
        return out
    return {k: str(k) for k in keys}
