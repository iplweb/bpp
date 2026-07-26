"""Tabela krzyżowa (pivot) na stronie "Szukaj zapytaniem" (postac=pivot).

Silnik pivota (parse_pivot_params/zbuduj_pivot/DIMENSIONS/METRICS) jest
gotowy i przetestowany w test_multiseek_pivot.py — tu sprawdzamy TYLKO
podpięcie: kontekst widoku, render partiala i eksport macierzy CSV/XLSX
z poziomu /zapytanie/.
"""

import pytest
from django.urls import reverse


@pytest.fixture
def redaktor(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.mark.django_db
def test_pivot_rekordow_renderuje_macierz(redaktor, wydawnictwo_ciagle, denorms):
    denorms.flush()
    res = redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "pivot",
            "pivot_row": "rok",
            "pivot_val": "liczba",
        },
    )
    assert res.status_code == 200
    assert res.context["pivot"].grand_total == 1
    assert str(wydawnictwo_ciagle.rok).encode() in res.content


@pytest.mark.django_db
def test_pivot_rekordow_z_kolumna(redaktor, wydawnictwo_ciagle, denorms):
    denorms.flush()
    res = redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "pivot",
            "pivot_row": "rok",
            "pivot_col": "typ_kbn",
            "pivot_val": "liczba",
        },
    )
    assert res.context["pivot"].col_dim.key == "typ_kbn"


@pytest.mark.django_db
def test_pivot_formularz_przenosi_stan_strony(redaktor, wydawnictwo_ciagle, denorms):
    """P1/P3: bez ukrytych pól model/query/postac submit zgubiłby filtr —
    strona zapytania trzyma go w URL-u, nie w sesji (jak multiseek)."""
    denorms.flush()
    res = redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "pivot",
            "pivot_row": "rok",
            "pivot_val": "liczba",
        },
    )
    content = res.content.decode()
    assert f'action="{reverse("bpp:zapytanie")}"' in content
    assert 'name="model" value="rekord"' in content
    assert f'name="query" value="rok = {wydawnictwo_ciagle.rok}"' in content
    assert 'name="postac" value="pivot"' in content


@pytest.mark.django_db
def test_pivot_linki_eksportu_pod_wlasciwym_urlem(
    redaktor, wydawnictwo_ciagle, denorms
):
    """P2/P3: linki eksportu muszą wskazywać /zapytanie/eksport/, nie
    ../export/ (ta ścieżka istnieje tylko pod /multiseek/results/)."""
    denorms.flush()
    res = redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "pivot",
            "pivot_row": "rok",
            "pivot_val": "liczba",
        },
    )
    content = res.content.decode()
    base = reverse("bpp:zapytanie_eksport", kwargs={"export_format": "csv"})
    base = base.rsplit("csv/", 1)[0]
    assert f"{base}xlsx/?" in content
    assert f"{base}csv/?" in content
    assert "../export/" not in content


@pytest.mark.django_db
def test_pivot_zbyt_duza_macierz_pokazuje_komunikat(
    redaktor, wydawnictwo_ciagle, denorms, monkeypatch
):
    """Bramka rozmiaru (PIVOT_MAX_CELLS) jest podłączona pod /zapytanie/ —
    zamiast wywalonego 500 user dostaje czytelny komunikat na ekranie."""
    from bpp.pivot import core as pivot_core

    # Prog czyta zbuduj_pivot jako globalna SWOJEGO modulu, wiec patchujemy go
    # w bpp.pivot.core, a nie przez zgodnosciowy shim multiseek_registry.pivot.
    monkeypatch.setattr(pivot_core, "PIVOT_MAX_CELLS", 0)
    denorms.flush()
    res = redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "pivot",
            "pivot_row": "rok",
            "pivot_val": "liczba",
        },
    )
    assert res.status_code == 200
    assert res.context["pivot"] is None
    assert b"zbyt du" in res.content


@pytest.mark.django_db
def test_pivot_eksport_csv_zwraca_macierz(redaktor, wydawnictwo_ciagle, denorms):
    denorms.flush()
    res = redaktor.get(
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": "csv"}),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "pivot",
            "pivot_row": "rok",
            "pivot_val": "liczba",
        },
    )
    assert res.status_code == 200
    assert b"RAZEM" in res.content


@pytest.mark.django_db
def test_pivot_eksport_xlsx_zwraca_macierz(redaktor, wydawnictwo_ciagle, denorms):
    denorms.flush()
    res = redaktor.get(
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": "xlsx"}),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "pivot",
            "pivot_row": "rok",
            "pivot_val": "liczba",
        },
    )
    assert res.status_code == 200
    assert "spreadsheetml" in res["Content-Type"]


@pytest.mark.django_db
def test_pivot_eksport_html_400(redaktor, wydawnictwo_ciagle, denorms):
    denorms.flush()
    res = redaktor.get(
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": "html"}),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "pivot",
        },
    )
    assert res.status_code == 400
    # 400 pivota idzie przez _blad() jak każdy inny błąd tego widoku —
    # text/plain chroni przed reflected XSS (patrz komentarz w
    # zapytanie_export.py przy _blad).
    assert res["Content-Type"].startswith("text/plain")


@pytest.mark.django_db
def test_pivot_w_liscie_postaci_rekordowych(redaktor):
    """Opcja "tabela krzyżowa" wraca do <select> — Zadanie 3 ją usunęło,
    bo bez implementacji renderowała placeholder listy."""
    from bpp.views.zapytanie import POSTAC_PIVOT, POSTACIE_REKORD

    assert POSTAC_PIVOT in {key for key, _ in POSTACIE_REKORD}


# ---------------------------------------------------------------------------
# Zadanie 9 — pivot autorski w UI + presety.
#
# Silnik (zbuduj_pivot_autora/DIMENSIONS/METRICS) jest gotowy i przetestowany
# w test_pivot_autor.py — tu sprawdzamy TYLKO podpięcie pod /zapytanie/:
# rozgałęzienie _pivot_context po modelu (wybierz_rejestr_pivota), eksport
# macierzy autorskiej i presety w kontekście strony.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_pivot_autorow_jednostka_x_tytul(redaktor, jednostka):
    """Brak fixture'a `tytul` (liczba pojedyncza) w tym repo — jest tylko
    `tytuly` (mnoga). Tytuł budujemy więc inline przez baker.make, tak jak
    już robi to test_pivot_autor.py::test_krzyzowo_jednostka_x_tytul."""
    from model_bakery import baker

    from bpp.models import Autor
    from bpp.models.autor import Tytul

    tytul = baker.make(Tytul)
    baker.make(
        Autor,
        nazwisko="Nowak",
        aktualna_jednostka=jednostka,
        tytul=tytul,
        _quantity=2,
    )

    res = redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "autor",
            "query": 'nazwisko = "Nowak"',
            "postac": "pivot",
            "pivot_row": "jednostka",
            "pivot_col": "tytul",
            "pivot_val": "liczba_autorow",
        },
    )

    assert res.status_code == 200
    assert res.context["pivot"].grand_total == 2


@pytest.mark.django_db
def test_pivot_autorow_eksport_csv(redaktor, jednostka):
    from model_bakery import baker

    from bpp.models import Autor

    baker.make(Autor, nazwisko="Nowak", aktualna_jednostka=jednostka)

    res = redaktor.get(
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": "csv"}),
        {
            "model": "autor",
            "query": 'nazwisko = "Nowak"',
            "postac": "pivot",
            "pivot_row": "jednostka",
            "pivot_val": "liczba_autorow",
        },
    )

    assert res.status_code == 200
    assert b"RAZEM" in res.content


@pytest.mark.django_db
def test_pivot_autorow_eksport_xlsx(redaktor, jednostka):
    """Kontrapunkt CSV powyżej — XLSX to drugi format, który DEFEKT #4
    (eksport_formaty zwracające pustą krotkę dla autora) też chronił."""
    from model_bakery import baker

    from bpp.models import Autor

    baker.make(Autor, nazwisko="Nowak", aktualna_jednostka=jednostka)

    res = redaktor.get(
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": "xlsx"}),
        {
            "model": "autor",
            "query": 'nazwisko = "Nowak"',
            "postac": "pivot",
            "pivot_row": "jednostka",
            "pivot_val": "liczba_autorow",
        },
    )

    assert res.status_code == 200
    assert "spreadsheetml" in res["Content-Type"]


@pytest.mark.django_db
def test_pivot_autorow_lista_teraz_dziala(redaktor, autor_jan_nowak, denorms):
    """Kontrapunkt historyczny: do Zadania 11 eksport LISTY autorów (postac
    domyślna "rekordy") był zablokowany 400-ką — to rozróżnienie chroniło
    Zadanie 9 (macierz autorska) przed przypadkowym „otwarciem wszystkiego"
    rozgałęzieniem po postaci w ZapytanieExportView.get(). Od Zadania 11
    lista też działa naprawdę (autor_csv_export_response), więc 400 by tu był
    regresją — patrz test_zapytanie_export.py::test_eksport_autorow_csv_ma_
    kolumny_dorobku dla właściwego pokrycia tej ścieżki."""
    denorms.flush()
    res = redaktor.get(
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": "csv"}),
        {"model": "autor", "query": 'nazwisko = "Nowak"'},
    )
    assert res.status_code == 200
    assert "text/csv" in res["Content-Type"]


@pytest.mark.django_db
def test_strona_pokazuje_presety_dla_autora(redaktor):
    res = redaktor.get(reverse("bpp:zapytanie"), {"model": "autor"})
    assert b"Audyt kompletno" in res.content


@pytest.mark.django_db
def test_presety_dla_autora_niosa_biezace_zapytanie(redaktor):
    """Presety mają DOŁOŻYĆ wymiary/metrykę do query-stringa, nie zgubić
    zapytania, które user już wpisał — inaczej klik w preset cofnąłby go do
    pustego wyniku."""
    from django.template.defaultfilters import urlencode as tpl_urlencode

    from bpp.views.zapytanie import PIVOT_PRESETY_AUTOR

    biezace_zapytanie = 'nazwisko = "Nowak"'
    res = redaktor.get(
        reverse("bpp:zapytanie"), {"model": "autor", "query": biezace_zapytanie}
    )
    fragment = f"query={tpl_urlencode(biezace_zapytanie)}".encode()
    assert res.content.count(fragment) >= len(PIVOT_PRESETY_AUTOR)


@pytest.mark.django_db
def test_pivot_autorow_baza_udzialow_renderuje_sume(
    redaktor, zwarte_z_dyscyplinami, autor_jan_nowak, denorms
):
    """End-to-end bazy U na stronie: Σ slotów × rok renderuje się i eksportuje.

    `zwarte_z_dyscyplinami` buduje realne wiersze `bpp_cache_punktacja_autora`
    (dwóch autorów po 0.5 slota), więc macierz ma się z czego wziąć — grand
    total 1.0 dla obu autorów razem, 0.5 w wierszu Jana Nowaka.
    """
    from decimal import Decimal

    denorms.flush()
    res = redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "autor",
            "query": 'nazwisko in ("Nowak", "Kowalski")',
            "postac": "pivot",
            "pivot_row": "autor",
            "pivot_col": "rok",
            "pivot_val": "suma_slotow",
        },
    )
    assert res.status_code == 200
    pivot = res.context["pivot"]
    assert pivot.grand_total == Decimal("1.0000")
    assert pivot.row_totals[autor_jan_nowak.pk] == Decimal("0.5000")
    assert str(zwarte_z_dyscyplinami.rok).encode() in res.content

    eksport = redaktor.get(
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": "csv"}),
        {
            "model": "autor",
            "query": 'nazwisko in ("Nowak", "Kowalski")',
            "postac": "pivot",
            "pivot_row": "autor",
            "pivot_col": "rok",
            "pivot_val": "suma_slotow",
        },
    )
    assert eksport.status_code == 200
    assert b"RAZEM" in eksport.content


@pytest.mark.django_db
def test_presety_nieobecne_dla_rekordu(redaktor, wydawnictwo_ciagle, denorms):
    """Presety z Zadania 9 dotyczą TYLKO modelu autor (baza K, patrz brief).
    Model rekord ich nie pokazuje — zapobiega martwym linkom z parametrami
    wymiarów, które w rejestrze rekordowym nie istnieją (np. "ma_orcid")."""
    denorms.flush()
    res = redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "rekord", "query": f"rok = {wydawnictwo_ciagle.rok}"},
    )
    assert b"Audyt kompletno" not in res.content


@pytest.mark.django_db
def test_metryka_kadrowa_pokazuje_rejestr_autorski(redaktor, autor_jan_nowak):
    """Metryka bazy K (liczba autorów) chowa wymiary publikacyjne baz P/U.

    Selektor dostaje z widoku PRZEFILTROWANY słownik wymiarów: sam `bpp_autor`
    nie ma dojścia do rekordu, więc „rok"/„dyscyplina"/… nie mają w bazie K
    ścieżki ORM (`expr_dla("K") is None`) i muszą zniknąć z selektora. Zostają
    dokładnie wymiary autorskie — porównanie z jawną listą, a nie z
    `DIMENSIONS.keys()`, bo od Zadania 10 rejestr jest szerszy niż baza K.
    """
    from bpp.pivot import autor as autor_rejestr

    res = redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "autor",
            "query": 'nazwisko = "Nowak"',
            "postac": "pivot",
            "pivot_val": "liczba_autorow",
        },
    )
    widoczne = res.context["pivot_dimensions"]
    assert set(widoczne) == {
        klucz
        for klucz, dim in autor_rejestr.DIMENSIONS.items()
        if dim.expr_dla(autor_rejestr.BAZA_KADROWA) is not None
    }
    assert "jednostka" in widoczne
    assert "rok" not in widoczne
    assert "dyscyplina" not in widoczne


@pytest.mark.django_db
def test_metryka_slotowa_pokazuje_rok(redaktor, autor_jan_nowak):
    """Metryka Σ slotów (baza U) odsłania wymiary publikacyjne bazy U — ale
    tylko te, które `bpp_cache_punktacja_autora` naprawdę zna: typ
    odpowiedzialności i charakter formalny zostają wyłącznie w bazie P."""
    res = redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "autor",
            "query": 'nazwisko = "Nowak"',
            "postac": "pivot",
            "pivot_val": "suma_slotow",
        },
    )
    widoczne = res.context["pivot_dimensions"]
    assert "rok" in widoczne
    assert "dyscyplina" in widoczne
    assert "jednostka_pracy" in widoczne
    assert "typ_odpowiedzialnosci" not in widoczne
    assert "charakter_formalny" not in widoczne


@pytest.mark.django_db
def test_metryka_liczby_prac_pokazuje_wymiary_bazy_prac(redaktor, autor_jan_nowak):
    """Baza P (liczba prac) idzie przez `autorzy` do rekordu, więc widzi
    WSZYSTKIE wymiary publikacyjne — w odróżnieniu od bazy U."""
    res = redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "autor",
            "query": 'nazwisko = "Nowak"',
            "postac": "pivot",
            "pivot_val": "liczba_prac",
        },
    )
    widoczne = res.context["pivot_dimensions"]
    assert {"rok", "dyscyplina", "typ_odpowiedzialnosci", "charakter_formalny"} <= set(
        widoczne
    )


@pytest.mark.django_db
def test_presety_autora_sa_wykonalne_w_swojej_bazie():
    """Każdy preset musi PRZEŻYĆ parse_pivot_params_autor bez podmiany.

    Preset podaje wiersz, kolumnę i metrykę; metryka wybiera bazę, a baza
    decyduje, które wymiary istnieją. Gdyby preset łączył wymiar publikacyjny
    (np. „rok") z metryką bazy kadrowej, parser cicho podstawiłby DEFAULT_ROW /
    wyrzucił kolumnę i user zobaczyłby tabelę inną niż obiecuje etykieta.
    """
    from bpp.pivot.autor import parse_pivot_params_autor
    from bpp.views.zapytanie import PIVOT_PRESETY_AUTOR

    for opis, row_key, col_key, metric_key in PIVOT_PRESETY_AUTOR:
        row, col, metric = parse_pivot_params_autor(
            {"pivot_row": row_key, "pivot_col": col_key, "pivot_val": metric_key}
        )
        assert metric.key == metric_key, opis
        assert row.key == row_key, opis
        assert col is not None and col.key == col_key, opis
