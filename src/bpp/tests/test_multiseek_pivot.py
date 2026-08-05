import pytest
from model_bakery import baker

from bpp.const import CHARAKTER_OGOLNY_ARTYKUL, CHARAKTER_OGOLNY_ROZDZIAL
from bpp.models import Charakter_Formalny, Jednostka, Wydawnictwo_Ciagle
from bpp.multiseek_registry import pivot
from bpp.pivot import core as pivot_core


def _wyd(**kw):
    kw.setdefault("tytul_oryginalny", f"Tytul {kw.get('rok')} {kw.get('punkty_kbn')}")
    kw.setdefault("tytul", kw["tytul_oryginalny"])
    kw.setdefault("uwagi", "Uwagi testowe")
    return baker.make(Wydawnictwo_Ciagle, **kw)


@pytest.fixture
def rekordy_pivot(
    db,
    denorms,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    from bpp.models.cache import Rekord

    art = baker.make(Charakter_Formalny, charakter_ogolny=CHARAKTER_OGOLNY_ARTYKUL)
    roz = baker.make(Charakter_Formalny, charakter_ogolny=CHARAKTER_OGOLNY_ROZDZIAL)

    # 2024/art: 2 rekordy (40 + 20 pkt) -> liczba=2, suma pkt=60
    _wyd(rok=2024, charakter_formalny=art, punkty_kbn=40)
    _wyd(rok=2024, charakter_formalny=art, punkty_kbn=20)
    # 2024/roz: 1 rekord (10 pkt)
    _wyd(rok=2024, charakter_formalny=roz, punkty_kbn=10)
    # 2023/art: 1 rekord (5 pkt)
    _wyd(rok=2023, charakter_formalny=art, punkty_kbn=5)

    denorms.flush()
    return Rekord.objects.all()


def test_parse_pivot_params_defaults_when_empty():
    row, col, metric = pivot.parse_pivot_params({})
    assert row.key == "rok"
    assert col is None
    assert metric.key == "liczba"


def test_parse_pivot_params_unknown_keys_fall_back():
    row, col, metric = pivot.parse_pivot_params(
        {"pivot_row": "xxx", "pivot_col": "yyy", "pivot_val": "zzz"}
    )
    assert row.key == "rok"
    assert col is None
    assert metric.key == "liczba"


def test_parse_pivot_params_column_must_allow_column():
    # "jednostka" jest tylko wierszem (allow_column=False) → col=None
    row, col, metric = pivot.parse_pivot_params(
        {"pivot_row": "rok", "pivot_col": "jednostka", "pivot_val": "liczba"}
    )
    assert col is None


def test_parse_pivot_params_column_equal_to_row_dropped():
    row, col, metric = pivot.parse_pivot_params(
        {"pivot_row": "rok", "pivot_col": "rok"}
    )
    assert col is None


def test_parse_pivot_params_valid_crosstab():
    row, col, metric = pivot.parse_pivot_params(
        {"pivot_row": "rok", "pivot_col": "charakter_ogolny", "pivot_val": "punkty_kbn"}
    )
    assert (row.key, col.key, metric.key) == ("rok", "charakter_ogolny", "punkty_kbn")


@pytest.mark.django_db
def test_zbuduj_pivot_a_liczba(rekordy_pivot):
    res = pivot.zbuduj_pivot(
        rekordy_pivot,
        pivot.DIMENSIONS["rok"],
        pivot.DIMENSIONS["charakter_ogolny"],
        pivot.METRICS["liczba"],
    )
    assert res.cells[(2024, CHARAKTER_OGOLNY_ARTYKUL)] == 2
    assert res.cells[(2024, CHARAKTER_OGOLNY_ROZDZIAL)] == 1
    assert res.cells[(2023, CHARAKTER_OGOLNY_ARTYKUL)] == 1
    assert res.grand_total == 4
    assert res.has_autorzy_dim is False


@pytest.mark.django_db
def test_zbuduj_pivot_k1_filtr_mnozacy_nie_zawyza(
    rekordy_pivot, jednostka, autor_jan_kowalski, autor_jan_nowak, denorms
):
    """Rekord z wieloma autorami w tej samej jednostce + filtr po
    autorach/jednostce (JOIN mnożący) liczony po wymiarze REKORDOWYM (rok)
    = raz, nie N razy."""
    from bpp.models.cache import Rekord

    w = _wyd(rok=2022, punkty_kbn=1)
    w.dodaj_autora(autor_jan_kowalski, jednostka)
    w.dodaj_autora(autor_jan_nowak, jednostka)
    denorms.flush()

    base_qs = Rekord.objects.filter(autorzy__jednostka=jednostka)
    # Płaski COUNT po tym JOIN-ie zawyżyłby wynik do 2 (bez dedup) — sanity
    # check, że queryset rzeczywiście mnoży wiersze.
    assert base_qs.count() == 2

    res = pivot.zbuduj_pivot(
        base_qs, pivot.DIMENSIONS["rok"], None, pivot.METRICS["liczba"]
    )
    assert res.cells[(2022, None)] == 1
    assert res.has_autorzy_dim is False


@pytest.mark.django_db
def test_zbuduj_pivot_k3_ordering_nie_rozbija_grup(rekordy_pivot):
    """Wejściowy queryset z .order_by('-rok', ...) (albo Meta.ordering) nie
    rozbija GROUP BY na mikro-grupy — liczba wierszy = liczba unikatowych
    lat."""
    qs = rekordy_pivot.order_by("-rok", "tytul_oryginalny_sort")
    res = pivot.zbuduj_pivot(qs, pivot.DIMENSIONS["rok"], None, pivot.METRICS["liczba"])
    assert len(res.rows) == len({r["rok"] for r in rekordy_pivot.values("rok")})
    assert len(res.rows) == 2


@pytest.mark.django_db
def test_zbuduj_pivot_b_k2_trzej_autorzy_jedna_klinika(
    db,
    denorms,
    jednostka,
    autor_jan_kowalski,
    autor_jan_nowak,
    autor_maker,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    """Rekord z 3 autorami z tej samej jednostki -> komórka = 1 praca,
    Σ punkty = punkty rekordu RAZ (nie ×3)."""
    from bpp.models.cache import Rekord

    trzeci = autor_maker(imiona="Anna", nazwisko="Wiśniewska")
    w = _wyd(rok=2021, punkty_kbn=40)
    w.dodaj_autora(autor_jan_kowalski, jednostka)
    w.dodaj_autora(autor_jan_nowak, jednostka)
    w.dodaj_autora(trzeci, jednostka)
    denorms.flush()

    base_qs = Rekord.objects.filter(autorzy__jednostka=jednostka)

    res_liczba = pivot.zbuduj_pivot(
        base_qs, pivot.DIMENSIONS["jednostka"], None, pivot.METRICS["liczba"]
    )
    assert res_liczba.cells[(jednostka.pk, None)] == 1
    assert res_liczba.has_autorzy_dim is True

    res_pk = pivot.zbuduj_pivot(
        base_qs, pivot.DIMENSIONS["jednostka"], None, pivot.METRICS["punkty_kbn"]
    )
    assert res_pk.cells[(jednostka.pk, None)] == 40


@pytest.mark.django_db
def test_zbuduj_pivot_null_bucket_i_koszyk_pk(
    db,
    denorms,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    """Rekord z zrodlo=None -> etykieta „— brak —"; punkty_kbn=0 -> "0"
    (bez zbędnych zer po przecinku i bez notacji naukowej)."""
    from bpp.models.cache import Rekord

    _wyd(rok=2020, punkty_kbn=0, zrodlo=None)
    _wyd(rok=2020, punkty_kbn=40, zrodlo=None)
    denorms.flush()

    base_qs = Rekord.objects.all()

    res_zrodlo = pivot.zbuduj_pivot(
        base_qs, pivot.DIMENSIONS["zrodlo"], None, pivot.METRICS["liczba"]
    )
    zrodlo_labels = dict(res_zrodlo.rows)
    assert pivot.BRAK in zrodlo_labels.values()

    res_koszyk = pivot.zbuduj_pivot(
        base_qs, pivot.DIMENSIONS["koszyk_pk"], None, pivot.METRICS["liczba"]
    )
    koszyk_labels = dict(res_koszyk.rows)
    assert "0" in koszyk_labels.values()
    assert "40" in koszyk_labels.values()


@pytest.mark.django_db
def test_zbuduj_pivot_b_k2_dwie_rozne_jednostki(
    db,
    denorms,
    jednostka,
    autor_jan_kowalski,
    autor_jan_nowak,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    """K2 (spec §11.3, druga połowa): rekord z autorami z DWÓCH różnych
    jednostek -> liczony RAZ w komórce KAŻDEJ z jednostek (duplikacja
    MIĘDZY różnymi wartościami wymiaru jest zamierzona, w przeciwieństwie
    do duplikacji WEWNĄTRZ tej samej wartości — patrz test k2 wyżej)."""
    from bpp.models.cache import Rekord

    j2 = baker.make(Jednostka, uczelnia=jednostka.uczelnia, parent=None)
    w = _wyd(rok=2020, punkty_kbn=40)
    w.dodaj_autora(autor_jan_kowalski, jednostka)
    w.dodaj_autora(autor_jan_nowak, j2)
    denorms.flush()

    base_qs = Rekord.objects.all()

    res_liczba = pivot.zbuduj_pivot(
        base_qs, pivot.DIMENSIONS["jednostka"], None, pivot.METRICS["liczba"]
    )
    assert res_liczba.cells[(jednostka.pk, None)] == 1
    assert res_liczba.cells[(j2.pk, None)] == 1
    assert res_liczba.grand_total == 2
    assert res_liczba.has_autorzy_dim is True

    res_pk = pivot.zbuduj_pivot(
        base_qs, pivot.DIMENSIONS["jednostka"], None, pivot.METRICS["punkty_kbn"]
    )
    assert res_pk.cells[(jednostka.pk, None)] == 40
    assert res_pk.cells[(j2.pk, None)] == 40


@pytest.mark.django_db
def test_zbuduj_pivot_join_reuse_prace_autora(
    db,
    denorms,
    jednostka,
    autor_jan_kowalski,
    autor_jan_nowak,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    """base_qs przefiltrowany po autorze (autorzy__autor=X) i wymiar
    'jednostka' (autorzy__jednostka_id) współdzielą ten sam JOIN do
    'autorzy' — Django REUŻYWA filtrowany JOIN zamiast dodawać nowy, więc
    w wyniku widoczna jest TYLKO jednostka X, nigdy jednostka współautora
    Y (mimo że oboje są przypisani do tego samego rekordu)."""
    from bpp.models.cache import Rekord

    j2 = baker.make(Jednostka, uczelnia=jednostka.uczelnia, parent=None)
    w = _wyd(rok=2020, punkty_kbn=10)
    w.dodaj_autora(autor_jan_kowalski, jednostka)
    w.dodaj_autora(autor_jan_nowak, j2)
    denorms.flush()

    base_qs = Rekord.objects.filter(autorzy__autor=autor_jan_kowalski)

    res = pivot.zbuduj_pivot(
        base_qs, pivot.DIMENSIONS["jednostka"], None, pivot.METRICS["liczba"]
    )
    rows = dict(res.rows)
    assert res.cells[(jednostka.pk, None)] == 1
    assert j2.pk not in rows
    assert (j2.pk, None) not in res.cells


@pytest.mark.django_db
def test_zbuduj_pivot_etykieta_fk_resolve_model(
    db,
    denorms,
    jednostka,
    autor_jan_kowalski,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    """Etykieta wymiaru FK (jednostka) idzie przez
    resolve_model().objects.in_bulk() + str(obj) — sanity check na
    PRAWDZIWYM id (nie na braku/None/BRAK), żeby złapać regresję w
    fk_model / resolve_model()."""
    from bpp.models.cache import Rekord

    jednostka.nazwa = "Klinika Bardzo Charakterystyczna Testowa"
    jednostka.save()

    w = _wyd(rok=2020, punkty_kbn=1)
    w.dodaj_autora(autor_jan_kowalski, jednostka)
    denorms.flush()

    base_qs = Rekord.objects.all()
    res = pivot.zbuduj_pivot(
        base_qs, pivot.DIMENSIONS["jednostka"], None, pivot.METRICS["liczba"]
    )
    rows = dict(res.rows)
    assert rows[jednostka.pk] == str(jednostka)
    assert "Klinika Bardzo Charakterystyczna Testowa" in rows[jednostka.pk]


@pytest.mark.django_db
def test_zbuduj_pivot_sumy_brzegowe_i_col_totals_bez_kolumny(rekordy_pivot):
    """Sumy brzegowe (row_totals/col_totals/grand_total) wyliczone ręcznie
    z danych `rekordy_pivot` (2024/art: 40+20=60, 2024/roz: 10, 2023/art:
    5 -> wiersz 2024=70, wiersz 2023=5, kolumna art=65, kolumna roz=10,
    total=75). Dodatkowo (naprawa A): bez wymiaru kolumnowego col_totals
    MUSI pozostać puste — wcześniej zbierało {None: grand_total}."""
    res = pivot.zbuduj_pivot(
        rekordy_pivot,
        pivot.DIMENSIONS["rok"],
        pivot.DIMENSIONS["charakter_ogolny"],
        pivot.METRICS["punkty_kbn"],
    )
    assert res.row_totals == {2024: 70, 2023: 5}
    assert res.col_totals == {
        CHARAKTER_OGOLNY_ARTYKUL: 65,
        CHARAKTER_OGOLNY_ROZDZIAL: 10,
    }
    assert res.grand_total == 75

    res_no_col = pivot.zbuduj_pivot(
        rekordy_pivot, pivot.DIMENSIONS["rok"], None, pivot.METRICS["punkty_kbn"]
    )
    assert res_no_col.col_totals == {}
    assert res_no_col.row_totals == {2024: 70, 2023: 5}
    assert res_no_col.grand_total == 75


def test_as_table_bez_kolumn():
    """as_table() dla degeneracji (kolumny=(brak)) — płaska lista."""
    pr = pivot.PivotResult(
        rows=[(2024, "2024"), (2023, "2023")],
        cols=[],
        cells={(2024, None): 5, (2023, None): 3},
        row_totals={2024: 5, 2023: 3},
        col_totals={},
        grand_total=8,
        row_dim=pivot.DIMENSIONS["rok"],
        col_dim=None,
        metric=pivot.METRICS["liczba"],
        has_autorzy_dim=False,
    )
    t = pr.as_table()
    assert t["has_cols"] is False
    assert t["col_headers"] == []
    assert t["rows"][0] == {"label": "2024", "cells": [5], "total": 5}
    assert t["col_totals"] == []
    assert t["grand_total"] == 8


def test_as_table_z_kolumnami():
    """as_table() dla cross-tabu — komórki i sumy brzegowe w kolejności
    kolumn; brakująca komórka → None (szablon renderuje pustkę)."""
    pr = pivot.PivotResult(
        rows=[(2024, "2024")],
        cols=[("art", "Artykuł"), ("roz", "Rozdział")],
        cells={(2024, "art"): 9},  # brak (2024, "roz") → None
        row_totals={2024: 9},
        col_totals={"art": 9, "roz": 0},
        grand_total=9,
        row_dim=pivot.DIMENSIONS["rok"],
        col_dim=pivot.DIMENSIONS["charakter_ogolny"],
        metric=pivot.METRICS["liczba"],
        has_autorzy_dim=False,
    )
    t = pr.as_table()
    assert t["has_cols"] is True
    assert t["col_headers"] == ["Artykuł", "Rozdział"]
    assert t["rows"][0]["cells"] == [9, None]
    assert t["col_totals"] == [9, 0]


@pytest.mark.django_db
def test_zbuduj_pivot_gate_cells(rekordy_pivot, monkeypatch):
    """Przekroczony limit komórek → PivotTooLargeError(kind="cells")."""
    monkeypatch.setattr(pivot_core, "PIVOT_MAX_CELLS", 0)
    with pytest.raises(pivot.PivotTooLargeError) as exc:
        pivot.zbuduj_pivot(
            rekordy_pivot,
            pivot.DIMENSIONS["rok"],
            None,
            pivot.METRICS["liczba"],
        )
    assert exc.value.kind == "cells"
    assert exc.value.limit == 0
