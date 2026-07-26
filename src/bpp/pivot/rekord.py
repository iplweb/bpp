"""Rejestr wymiarów/metryk pivota dla modelu Rekord (cache denormalizacji).

Historycznie to jedyny konsument silnika (`bpp.pivot.core`) — strona
multiseeka i strona „Wyszukiwanie zapytaniem" (`postac=pivot`, model=rekord)
dzielą ten sam rejestr."""

from bpp.pivot.core import PivotDimension, PivotMetric
from bpp.pivot.core import zbuduj_pivot as _zbuduj_pivot

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
        label_kind="fk",
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


def zbuduj_pivot_rekordu(base_qs, row_dim, col_dim, metric):
    """Cienki wrapper na `core.zbuduj_pivot` z modelem Rekord — ujednolica
    sygnaturę z `bpp.pivot.autor.zbuduj_pivot_autora`, żeby widok i eksport
    mogły wołać oba rejestry przez wspólny alias `zbuduj` (patrz
    `bpp.pivot.wybierz_rejestr_pivota`)."""
    from bpp.models.cache import Rekord

    return _zbuduj_pivot(base_qs, row_dim, col_dim, metric, model=Rekord)


# Aliasy zgodności interfejsu — patrz docstring wybierz_rejestr_pivota().
parse_params = parse_pivot_params
zbuduj = zbuduj_pivot_rekordu
