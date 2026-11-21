"""FD#525: w raporcie autorów opis bibliograficzny pracy jest linkiem do
strony rekordu (HTML); eksport DOCX/XLSX zostaje bez linków."""

import importlib
from io import BytesIO

import openpyxl
import pytest
from django.apps import apps as django_apps
from django.urls import reverse
from flexible_reports.models import Column
from model_bakery import baker

from bpp.models import Autor, Jednostka, Wydawnictwo_Ciagle
from bpp.models.cache import Rekord
from nowe_raporty.seeding import seed_default_reports

STARY = "{{ record.opis_bibliograficzny_cache|safe }}"


@pytest.fixture
def praca_autora(typy_odpowiedzialnosci, uczelnia):
    seed_default_reports()
    jednostka = baker.make(Jednostka, skupia_pracownikow=True, uczelnia=uczelnia)
    autor = baker.make(Autor)
    wc = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Praca do klikniecia",
        rok=2020,
        adnotacje="lista_a",
    )
    wc.dodaj_autora(autor, jednostka, zapisany_jako="Kowalski J.")
    return autor, wc


def _url(autor, export=None):
    url = reverse(
        "nowe_raporty:raport_generuj", args=["raport-autorow", autor.pk, 2020, 2020]
    )
    return url + (f"?_export={export}" if export else "")


@pytest.mark.django_db
def test_fd525_opis_w_raporcie_autorow_to_link(client, praca_autora):
    autor, wc = praca_autora
    rekord = Rekord.objects.get_for_model(wc)

    res = client.get(_url(autor))

    assert res.status_code == 200
    html = res.content.decode()
    assert "Praca do klikniecia" in html
    assert f'<a href="{rekord.get_absolute_url()}">' in html


@pytest.mark.django_db
def test_fd525_eksport_xlsx_bez_html(client, praca_autora):
    autor, _wc = praca_autora

    res = client.get(_url(autor, "xlsx"))

    wb = openpyxl.load_workbook(BytesIO(res.content))
    komorki = [
        str(c.value)
        for ws in wb.worksheets
        for row in ws.iter_rows()
        for c in row
        if c.value is not None
    ]
    opisy = [k for k in komorki if "Praca do klikniecia" in k]
    assert opisy
    assert not any("<a" in k or "href" in k for k in opisy)


def _migracja():
    return importlib.import_module(
        "nowe_raporty.migrations.0003_opis_bibliograficzny_link"
    )


@pytest.mark.django_db
def test_fd525_migracja_podmienia_domyslny_szablon_i_nie_rusza_wlasnych():
    m = _migracja()
    domyslna = baker.make(Column, template=STARY, strip_html_on_export=True)
    z_odstepami = baker.make(
        Column,
        template="{{record.opis_bibliograficzny_cache|safe}}\n",
        strip_html_on_export=True,
    )
    wlasna = baker.make(
        Column, template="<b>{{ record.opis_bibliograficzny_cache|safe }}</b>"
    )

    m.naprzod(django_apps, None)

    for k in domyslna, z_odstepami, wlasna:
        k.refresh_from_db()
    assert domyslna.template == m.NOWY
    assert z_odstepami.template == m.NOWY
    assert wlasna.template == "<b>{{ record.opis_bibliograficzny_cache|safe }}</b>"

    m.wstecz(django_apps, None)
    domyslna.refresh_from_db()
    assert domyslna.template == STARY


def test_fd525_seed_i_migracja_maja_ten_sam_szablon():
    from nowe_raporty.seeding import definicje

    opis = next(k for k in definicje.KOLUMNY if k["label"] == "Opis bibliograficzny")
    assert opis["template"] == _migracja().NOWY


def test_fd525_docx_nie_przepuszcza_linkow():
    # DOCX: nh3 wycina <a>, zostawiając tekst opisu (eksport bez zmian).
    import nh3

    from nowe_raporty.docx_export import DEFAULT_ALLOWED_TAGS

    assert "a" not in DEFAULT_ALLOWED_TAGS
    html = nh3.clean(
        '<td><a href="/bpp/rekord/1,2/">Opis</a></td>',
        tags=set(DEFAULT_ALLOWED_TAGS),
        clean_content_tags=set(),
        link_rel=None,
    )
    assert "href" not in html
    assert "Opis" in html


@pytest.mark.django_db
def test_fd525_migracja_nie_rusza_kolumn_bez_stripowania_html():
    m = _migracja()
    bez_strip = baker.make(Column, template=STARY, strip_html_on_export=False)

    m.naprzod(django_apps, None)

    bez_strip.refresh_from_db()
    assert bez_strip.template == STARY
