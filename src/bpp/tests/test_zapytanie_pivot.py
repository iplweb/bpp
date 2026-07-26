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
    from bpp.multiseek_registry import pivot as pivot_mod

    monkeypatch.setattr(pivot_mod, "PIVOT_MAX_CELLS", 0)
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
