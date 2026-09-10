"""PivotWidok — sortowanie i stronicowanie już policzonej macierzy.

Testy są czysto pamięciowe (bez bazy): `PivotResult` budujemy ręcznie, bo
sprawdzamy warstwę PREZENTACJI, nie agregację. Za agregację odpowiadają
test_multiseek_pivot.py i test_pivot_autor.py.
"""

import pytest

from bpp.pivot import core


def _dim(key="jednostka", label="Jednostka"):
    return core.PivotDimension(key=key, label=label, expr=key)


def _metric():
    return core.PivotMetric(key="liczba", label="Liczba prac", field=None)


def _wynik(pary, row_dim=None):
    """PivotResult bez kolumn: `pary` to lista (etykieta, suma_wiersza)."""
    row_dim = row_dim or _dim()
    rows = [(label, label) for label, _ in pary]
    row_totals = {label: total for label, total in pary}
    return core.PivotResult(
        rows=rows,
        cols=[],
        cells={(label, None): total for label, total in pary},
        row_totals=row_totals,
        col_totals={},
        grand_total=sum(t for _, t in pary),
        row_dim=row_dim,
        col_dim=None,
        metric=_metric(),
        has_autorzy_dim=False,
    )


# --- parse_widok -----------------------------------------------------------


def test_parse_widok_domyslne_gdy_pusto():
    w = core.parse_widok({})
    assert w.sort == core.SORT_ETYKIETA
    assert w.kierunek is None
    assert w.strona == 1
    assert w.na_stronie == core.DOMYSLNIE_NA_STRONIE


@pytest.mark.parametrize("wartosc", ["999999", "0", "-5", "", "abc", "51"])
def test_parse_widok_odrzuca_rozmiar_strony_spoza_whitelisty(wartosc):
    """Bez tej walidacji ?pivot_per_page=999999 unieważnia całą zmianę —
    wracamy do renderowania dwóch tysięcy wierszy naraz."""
    assert (
        core.parse_widok({"pivot_per_page": wartosc}).na_stronie
        == core.DOMYSLNIE_NA_STRONIE
    )


@pytest.mark.parametrize("ile", core.DOZWOLONE_NA_STRONIE)
def test_parse_widok_przyjmuje_dozwolone_rozmiary(ile):
    assert core.parse_widok({"pivot_per_page": str(ile)}).na_stronie == ile


@pytest.mark.parametrize("wartosc", ["abc", "", "0", "-3", None])
def test_parse_widok_smieciowa_strona_daje_pierwsza(wartosc):
    assert core.parse_widok({"pivot_page": wartosc}).strona == 1


def test_parse_widok_smieciowy_sort_i_kierunek_daja_domyslne():
    w = core.parse_widok({"pivot_sort": "xxx", "pivot_dir": "yyy"})
    assert w.sort == core.SORT_ETYKIETA
    assert w.kierunek is None


def test_kierunek_efektywny_zalezy_od_sortu():
    """Naturalny kierunek etykiety jest rosnący, sumy — malejący
    („kto ma najwięcej" to jedyne pytanie, które ludzie zadają)."""
    assert core.PivotWidok().kierunek_efektywny == "asc"
    assert core.PivotWidok(sort=core.SORT_SUMA).kierunek_efektywny == "desc"
    assert (
        core.PivotWidok(sort=core.SORT_SUMA, kierunek="asc").kierunek_efektywny == "asc"
    )


def test_bez_stronicowania_zeruje_strone_i_rozmiar():
    w = core.PivotWidok(sort=core.SORT_SUMA, strona=7, na_stronie=25)
    b = w.bez_stronicowania()
    assert b.na_stronie == 0
    assert b.strona == 1
    assert b.sort == core.SORT_SUMA  # sortowanie zostaje


# --- sortowanie ------------------------------------------------------------


def test_as_table_bez_widoku_zachowuje_sie_jak_dawniej():
    """Wywołanie bezargumentowe (używa go m.in. eksport) nie może dokładać
    kluczy stronicowania ani zmieniać kolejności."""
    w = _wynik([("Beta", 5), ("Alfa", 9)])
    t = w.as_table()
    assert [r["label"] for r in t["rows"]] == ["Beta", "Alfa"]
    assert "page_obj" not in t
    assert "is_paginated" not in t


def test_sortowanie_po_sumie_malejaco_domyslnie():
    w = _wynik([("Alfa", 5), ("Beta", 9), ("Gamma", 1)])
    t = w.as_table(core.PivotWidok(sort=core.SORT_SUMA))
    assert [r["label"] for r in t["rows"]] == ["Beta", "Alfa", "Gamma"]
    assert [r["total"] for r in t["rows"]] == [9, 5, 1]


def test_sortowanie_po_sumie_rosnaco():
    w = _wynik([("Alfa", 5), ("Beta", 9), ("Gamma", 1)])
    t = w.as_table(core.PivotWidok(sort=core.SORT_SUMA, kierunek="asc"))
    assert [r["label"] for r in t["rows"]] == ["Gamma", "Alfa", "Beta"]


@pytest.mark.parametrize("sort", [core.SORT_ETYKIETA, core.SORT_SUMA])
def test_kolejnosc_jest_totalna_gdy_etykiety_sie_powtarzaja(sort, monkeypatch):
    """Etykiety NIE są unikatowe — dwóch autorów „Kowalski Jan" ma różne PK
    i ten sam `str()`. Gdyby remis rozstrzygała sama etykieta, o kolejności
    decydowałaby kolejność wejścia — a ta pochodzi z GROUP BY bez ORDER BY,
    więc nie jest powtarzalna między wykonaniami. Wiersz na granicy strony
    pokazałby się wtedy na dwóch stronach albo na żadnej.

    Wiersze budujemy przez `_labels`, tak jak robi to `_build_matrix`:
    dla sort=etykieta cała totalność siedzi właśnie tam.
    """
    dim = _dim()
    etykiety = {1: "Kowalski Jan", 2: "Kowalski Jan", 3: "Nowak Ewa"}
    sumy = {1: 5, 2: 5, 3: 5}  # remis także po sumie
    monkeypatch.setattr(
        core, "_label_mapping", lambda keys, d: {k: etykiety[k] for k in keys}
    )

    def wynik(kolejnosc_wejscia):
        rows = core._labels(kolejnosc_wejscia, dim)
        return core.PivotResult(
            rows=rows,
            cols=[],
            cells={(k, None): sumy[k] for k, _ in rows},
            row_totals=dict(sumy),
            col_totals={},
            grand_total=sum(sumy.values()),
            row_dim=dim,
            col_dim=None,
            metric=_metric(),
            has_autorzy_dim=False,
        )

    widok = core.PivotWidok(sort=sort)
    a = [p[0] for p in wynik([1, 2, 3]).posortowane_wiersze(widok)]
    b = [p[0] for p in wynik([3, 2, 1]).posortowane_wiersze(widok)]
    assert a == b == [1, 2, 3]


def test_labels_jest_totalne_przy_powtorzonych_etykietach(monkeypatch):
    """Warstwa `_labels` osobno: `keys` przychodzi tam jako `set`, a klucze
    o wspólnej etykiecie nie mogą się gubić ani przestawiać."""
    dim = _dim()
    monkeypatch.setattr(
        core, "_label_mapping", lambda keys, d: dict.fromkeys(keys, "Kowalski Jan")
    )
    assert core._labels([3, 1, 2], dim) == core._labels([2, 3, 1], dim)
    assert [k for k, _ in core._labels([3, 1, 2], dim)] == [1, 2, 3]


def test_sortowanie_po_sumie_rozstrzyga_remisy_etykieta():
    """Bez porządku totalnego wiersze o równych sumach mogłyby wypaść w innej
    kolejności przy kolejnym żądaniu — a wtedy przy stronicowaniu ten sam
    wiersz pokazuje się na dwóch stronach albo znika z obu."""
    w = _wynik([("Gamma", 5), ("Alfa", 5), ("Beta", 5)])
    kolejnosc = [
        r["label"] for r in w.as_table(core.PivotWidok(sort=core.SORT_SUMA))["rows"]
    ]
    assert kolejnosc == ["Alfa", "Beta", "Gamma"]
    # deterministycznie także przy odwróconym wejściu
    w2 = _wynik([("Beta", 5), ("Gamma", 5), ("Alfa", 5)])
    assert [
        r["label"] for r in w2.as_table(core.PivotWidok(sort=core.SORT_SUMA))["rows"]
    ] == kolejnosc


def test_sortowanie_po_etykiecie_desc_odwraca_kolejnosc_naturalna():
    w = _wynik([("Alfa", 1), ("Beta", 2), ("Gamma", 3)])
    t = w.as_table(core.PivotWidok(sort=core.SORT_ETYKIETA, kierunek="desc"))
    assert [r["label"] for r in t["rows"]] == ["Gamma", "Beta", "Alfa"]


def test_sortowanie_po_sumie_traktuje_brak_sumy_jak_zero():
    w = _wynik([("Alfa", 3), ("Beta", 1)])
    w.row_totals.pop("Alfa")
    t = w.as_table(core.PivotWidok(sort=core.SORT_SUMA))
    assert [r["label"] for r in t["rows"]] == ["Beta", "Alfa"]


# --- strzałki i cele linków ------------------------------------------------


def test_strzalka_sumy_odzwierciedla_kierunek():
    w = _wynik([("Alfa", 1)])
    t = w.as_table(core.PivotWidok(sort=core.SORT_SUMA))
    assert t["sort_suma_strzalka"] == "▼"
    assert t["sort_suma_rosnaco"] is False
    assert t["sort_etykieta_strzalka"] == ""  # nieaktywna kolumna bez strzałki


def test_strzalka_etykiety_odwrocona_dla_roku():
    """Dla roku kolejność naturalna jest MALEJĄCA (najnowszy u góry), więc
    ▲ nad listą 2025, 2024, 2023 byłoby kłamstwem."""
    rok = _dim(key="rok", label="Rok")
    t = _wynik([("2025", 1)], row_dim=rok).as_table(core.PivotWidok())
    assert t["sort_etykieta_strzalka"] == "▼"
    assert t["sort_etykieta_rosnaco"] is False

    jednostka = _wynik([("Alfa", 1)]).as_table(core.PivotWidok())
    assert jednostka["sort_etykieta_strzalka"] == "▲"


def test_link_aktywnego_naglowka_odwraca_kierunek():
    w = _wynik([("Alfa", 1)])
    t = w.as_table(core.PivotWidok(sort=core.SORT_SUMA))  # aktywna suma, desc
    assert t["sort_suma_link"] == "asc"  # klik odwraca
    assert t["sort_etykieta_link"] == "asc"  # nieaktywna bierze swój domyślny

    t2 = w.as_table(core.PivotWidok(sort=core.SORT_ETYKIETA))
    assert t2["sort_etykieta_link"] == "desc"
    assert t2["sort_suma_link"] == "desc"


# --- stronicowanie ---------------------------------------------------------


def _duzy_wynik(n=120):
    return _wynik([(f"Wiersz {i:03d}", i) for i in range(n)])


def test_stronicowanie_tnie_wiersze():
    t = _duzy_wynik(120).as_table(core.PivotWidok(na_stronie=50))
    assert len(t["rows"]) == 50
    assert t["is_paginated"] is True
    assert t["paginator"].num_pages == 3
    assert t["wszystkich_wierszy"] == 120


def test_stronicowanie_druga_strona_ma_inne_wiersze():
    widok = core.PivotWidok(na_stronie=50)
    pierwsza = _duzy_wynik(120).as_table(widok)
    druga = _duzy_wynik(120).as_table(core.PivotWidok(na_stronie=50, strona=2))
    assert pierwsza["rows"][0]["label"] != druga["rows"][0]["label"]
    assert druga["page_obj"].number == 2
    assert druga["page_obj"].start_index() == 51


def test_strona_poza_zakresem_daje_ostatnia_nie_404():
    """get_page(), nie page(): user potrafi zostać na ?pivot_page=40 po
    zawężeniu filtra i nie ma powodu pokazywać mu błędu."""
    t = _duzy_wynik(120).as_table(core.PivotWidok(na_stronie=50, strona=999))
    assert t["page_obj"].number == 3
    assert len(t["rows"]) == 20


def test_sumy_brzegowe_dotycza_calego_zbioru_nie_strony():
    """Semantyka Excela: RAZEM podsumowuje cały wynik. Szablon musi to
    napisać pod tabelą (t.is_paginated → adnotacja)."""
    pelny = _duzy_wynik(120)
    calosc = sum(range(120))
    t = pelny.as_table(core.PivotWidok(na_stronie=25, strona=3))
    assert t["grand_total"] == calosc
    assert sum(r["total"] for r in t["rows"]) < calosc


def test_jedna_strona_nie_jest_stronicowana():
    t = _wynik([("Alfa", 1), ("Beta", 2)]).as_table(core.PivotWidok(na_stronie=50))
    assert t["is_paginated"] is False
    assert len(t["rows"]) == 2


def test_na_stronie_zero_wylacza_stronicowanie():
    """Tego wariantu używa eksport — plik ma mieć pełną macierz."""
    t = _duzy_wynik(120).as_table(core.PivotWidok(na_stronie=0))
    assert len(t["rows"]) == 120
    assert t["paginator"] is None
    assert t["is_paginated"] is False


def test_zakres_stron_zawiera_wielokropek_jako_none():
    t = _duzy_wynik(2000).as_table(core.PivotWidok(na_stronie=25, strona=20))
    assert None in t["page_range"]
    assert 20 in t["page_range"]


# --- eksport ---------------------------------------------------------------


def test_eksport_respektuje_sortowanie_ale_ignoruje_strone():
    from bpp.views.multiseek_export import _pivot_export_rows

    widok = core.PivotWidok(
        sort=core.SORT_SUMA, strona=3, na_stronie=25
    ).bez_stronicowania()
    wiersze = list(_pivot_export_rows(_duzy_wynik(120), widok))
    # nagłówek + 120 wierszy + RAZEM
    assert len(wiersze) == 122
    assert wiersze[1][0] == "Wiersz 119"  # największa suma na górze


def test_eksport_bez_widoku_dziala_jak_dawniej():
    from bpp.views.multiseek_export import _pivot_export_rows

    wiersze = list(_pivot_export_rows(_wynik([("Beta", 5), ("Alfa", 9)])))
    assert [w[0] for w in wiersze] == ["Jednostka", "Beta", "Alfa", "RAZEM"]


# --- render pagera ---------------------------------------------------------


def _render_pager(t, url="/multiseek/results/?pivot_row=autor&print=1"):
    """Render partiala pagera. Wymaga bazy: render_to_string z `request`
    odpala context processory projektu (m.in. czytający Uczelnię)."""
    from django.contrib.auth.models import AnonymousUser
    from django.template.loader import render_to_string
    from django.test import RequestFactory

    request = RequestFactory().get(url)
    request.user = AnonymousUser()  # context processory projektu jej wymagają
    return render_to_string("multiseek/_pivot-pager.html", {"t": t}, request=request)


@pytest.mark.django_db
def test_pager_renderuje_wielokropek_i_numery():
    """Wielokropek jedzie do szablonu jako None — sprawdzamy, że `{% if
    numer is None %}` naprawdę go łapie, a nie renderuje słowa "None"."""
    t = _duzy_wynik(2000).as_table(core.PivotWidok(na_stronie=25, strona=20))
    html = _render_pager(t)
    assert 'class="ellipsis"' in html
    assert "None" not in html
    assert "pivot_page=21" in html.replace("&amp;", "&")


@pytest.mark.django_db
def test_pager_linki_gasza_tryb_wydruku():
    t = _duzy_wynik(120).as_table(core.PivotWidok(na_stronie=25))
    html = _render_pager(t).replace("&amp;", "&")
    assert "pivot_page=" in html
    assert "print=1" not in html
    # bieżący filtr macierzy jest przenoszony
    assert "pivot_row=autor" in html


@pytest.mark.django_db
def test_pager_milczy_gdy_jedna_strona():
    t = _wynik([("Alfa", 1)]).as_table(core.PivotWidok(na_stronie=50))
    assert _render_pager(t).strip() == ""
