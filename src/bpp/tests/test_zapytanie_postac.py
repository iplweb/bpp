import pytest
from django.urls import reverse


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
