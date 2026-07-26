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
def test_pivot_autorow_lista_wciaz_400(redaktor, autor_jan_nowak, denorms):
    """Eksport LISTY autorów (postac domyślna "rekordy") pozostaje
    zablokowany — to wciąż Zadanie 11, nie 9. Rozgałęzienie po postaci w
    ZapytanieExportView.get() nie miało otworzyć wszystkiego, tylko pivot."""
    denorms.flush()
    res = redaktor.get(
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": "csv"}),
        {"model": "autor", "query": 'nazwisko = "Nowak"'},
    )
    assert res.status_code == 400


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
    """DEFEKT #3 z brief-u: `"rok" not in pivot_dimensions` byłby zielony
    NIEZALEŻNIE od tego, czy filtrowanie po bazie metryki (`expr_dla`)
    naprawdę działa, bo "rok" nie jest dziś w ogóle kluczem w
    bpp.pivot.autor.DIMENSIONS (dojdzie dopiero w Zadaniu 10 jako wymiar
    bazy P/U). Sprawdzamy więc to, co JEST dziś falsyfikowalne: strona
    autorska pokazuje wymiary z WŁAŚCIWEGO rejestru (autorskiego, nie
    rekordowego) — gdyby _pivot_context pomyłkowo użył rejestru rekordowego,
    te klucze by się nie zgadzały. Właściwy test „metryka bazy K chowa
    wymiary publikacyjne bazy P/U" wymaga wymiarów per-bazowych i trafia do
    Zadania 10 (patrz test_metryka_slotowa_pokazuje_rok niżej, xfail)."""
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
    assert res.context["pivot_dimensions"].keys() == autor_rejestr.DIMENSIONS.keys()
    assert "jednostka" in res.context["pivot_dimensions"]
    assert "rok" not in res.context["pivot_dimensions"]


@pytest.mark.xfail(reason="metryki bazy U dochodzą w Zadaniu 10", strict=True)
@pytest.mark.django_db
def test_metryka_slotowa_pokazuje_rok(redaktor, autor_jan_nowak):
    res = redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "autor",
            "query": 'nazwisko = "Nowak"',
            "postac": "pivot",
            "pivot_val": "suma_slotow",
        },
    )
    assert "rok" in res.context["pivot_dimensions"]
    assert "typ_odpowiedzialnosci" not in res.context["pivot_dimensions"]
