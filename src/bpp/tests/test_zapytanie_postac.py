import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle


@pytest.fixture
def zalogowany_redaktor(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.mark.django_db
def test_postac_domyslna_to_tabela_redakcyjna(
    zalogowany_redaktor, wydawnictwo_ciagle, denorms
):
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "rekord", "query": f"rok = {wydawnictwo_ciagle.rok}"},
    )
    assert res.status_code == 200
    assert b"rekord-id-cell" in res.content


@pytest.mark.django_db
def test_postac_lista_renderuje_partial_multiseeka(
    zalogowany_redaktor, wydawnictwo_ciagle, denorms
):
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "list",
        },
    )
    assert b"multiseek-list-report" in res.content


@pytest.mark.django_db
def test_postac_lista_nie_pokazuje_widgetu_usuwania(
    zalogowany_redaktor, wydawnictwo_ciagle, denorms
):
    """Widget ❌ jest sesyjny i multiseekowy — na /zapytanie/ nie działałby."""
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "list",
        },
    )
    assert b"data-remove-result" not in res.content


@pytest.mark.django_db
def test_postac_tabela_ma_sumy(zalogowany_redaktor, wydawnictwo_ciagle, denorms):
    """Suma w stopce to SUMA CAŁEGO zbioru — nie wartość jednego wiersza.

    Dwa rekordy (40 + 10), zeby "50.00" mogło pochodzic TYLKO z agregatu w
    stopce, a nie z przypadkowego powtorzenia wartosci jednego z wierszy.
    """
    wydawnictwo_ciagle.punkty_kbn = 40
    wydawnictwo_ciagle.save()
    baker.make(Wydawnictwo_Ciagle, rok=wydawnictwo_ciagle.rok, punkty_kbn=10)
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "table",
        },
    )
    assert b"multiseek-table-report" in res.content
    assert b"Suma:" in res.content
    # Lokalizacja pl: separator dziesiętny to przecinek (Decimal -> "50,00"),
    # nie punkt — inaczej niż literał "0.00" z default_if_none (tekst, nie
    # liczba, więc l10n go nie dotyka).
    assert b"50,00" in res.content


@pytest.mark.django_db
def test_postac_niedozwolona_dla_autora_degraduje(
    zalogowany_redaktor, autor_jan_nowak, denorms
):
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "autor", "query": 'nazwisko = "Nowak"', "postac": "bibtex"},
    )
    assert res.status_code == 200
    assert b"multiseek-list-report" not in res.content


@pytest.mark.django_db
def test_postac_pivot_niewybieralna_w_selektorze(
    zalogowany_redaktor, wydawnictwo_ciagle, denorms
):
    """Pivot bez dedykowanego partiala nie ma prawa być opcją w <select>.

    Zasada: opcja w UI albo działa, albo jej nie ma. Realny render tabeli
    krzyżowej dokładają kolejne zadania planu.
    """
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "rekord", "query": f"rok = {wydawnictwo_ciagle.rok}"},
    )
    assert b'value="pivot"' not in res.content


@pytest.mark.django_db
def test_postac_pivot_dla_rekordu_degraduje(
    zalogowany_redaktor, wydawnictwo_ciagle, denorms
):
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "pivot",
        },
    )
    assert res.status_code == 200
    assert b"rekord-id-cell" in res.content


@pytest.mark.django_db
def test_postac_pivot_dla_autora_degraduje(
    zalogowany_redaktor, autor_jan_nowak, denorms
):
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "autor", "query": 'nazwisko = "Nowak"', "postac": "pivot"},
    )
    assert res.status_code == 200
    assert b"multiseek-list-report" not in res.content


@pytest.mark.django_db
def test_postac_bibtex_renderuje_wlasny_partial(
    zalogowany_redaktor, wydawnictwo_ciagle, denorms
):
    """multiseek ma dedykowany partial na BibTeX (<pre> + przycisk kopiowania)
    — /zapytanie/ ma go używać, nie podstawiać listy opisów jako placeholder.
    """
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "bibtex",
        },
    )
    assert b"multiseek-bibtex-container" in res.content
    assert b"multiseek-list-report" not in res.content


@pytest.mark.django_db
def test_multiseek_nadal_pokazuje_widget_usuwania(client, wydawnictwo_ciagle, denorms):
    """Dowód neutralności flagi hide_chrome: multiseek jej nie przekazuje."""
    denorms.flush()
    from django.template.loader import render_to_string

    from bpp.models import Rekord

    html = render_to_string(
        "multiseek/report-body-list.html",
        {"object_list": Rekord.objects.all(), "export_mode": False},
    )
    assert "data-remove-result" in html


@pytest.mark.django_db
def test_pager_zachowuje_postac_na_kolejnej_stronie(zalogowany_redaktor, denorms):
    """Regresja na `_zapytanie_pager.html`: bez `&postac=` link „następna
    strona" resetowałby wybraną postać z powrotem na „rekordy"."""
    rok = 2031
    for _ in range(30):
        baker.make(Wydawnictwo_Ciagle, rok=rok)
    denorms.flush()

    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "rekord", "query": f"rok = {rok}", "postac": "list"},
    )
    assert b"postac=list" in res.content


@pytest.mark.django_db
def test_tabela_suma_tylko_na_ostatniej_stronie(zalogowany_redaktor, denorms):
    """Regresja na `page_obj=results` w include'u tabeli: bez tego stopka
    "Suma:" renderowałaby się na KAŻDEJ stronie, nie tylko ostatniej."""
    rok = 2032
    for _ in range(30):
        baker.make(Wydawnictwo_Ciagle, rok=rok)
    denorms.flush()

    pierwsza = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "rekord", "query": f"rok = {rok}", "postac": "table"},
    )
    assert b"Suma:" not in pierwsza.content

    druga = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {rok}",
            "postac": "table",
            "page": 2,
        },
    )
    assert b"Suma:" in druga.content
