import openpyxl
import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from flexible_reports.models import (
    DATA_FROM_DATASOURCE,
    Column,
    Datasource,
    ReportElement,
    Table,
)
from flexible_reports.models.report import Report
from formdefaults.models import FormRepresentation
from model_bakery import baker
from six import BytesIO

from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.struktura import Jednostka
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from nowe_raporty.forms import form_class_dla
from nowe_raporty.models import DefinicjaRaportu
from nowe_raporty.seeding import seed_default_reports
from nowe_raporty.views import RaportGenerujView


@pytest.fixture
def autor(typy_odpowiedzialnosci):
    swoja_jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    obca_jednostka = baker.make(Jednostka, skupia_pracownikow=False)

    autor = baker.make(Autor)

    wc1 = baker.make(Wydawnictwo_Ciagle)
    wc2 = baker.make(Wydawnictwo_Ciagle)

    wc1.dodaj_autora(autor, swoja_jednostka, zapisany_jako="lel")
    wc2.dodaj_autora(autor, obca_jednostka, zapisany_jako="lol", afiliuje=False)

    return autor


@pytest.mark.django_db
def test_rekord_prace_autora(autor):
    assert Rekord.objects.prace_autora(autor).count() == 2


@pytest.mark.django_db
def test_rekord_prace_autora_z_afiliowanych_jednostek(autor):
    assert Rekord.objects.prace_autora_z_afiliowanych_jednostek(autor).count() == 1


@pytest.mark.django_db
def test_generowanie_xls(
    uczelnia,
    autor_jan_kowalski,
    client,
    rok,
    jednostka,
    wydawnictwo_ciagle,
    wydawnictwo_zwarte,
    typ_odpowiedzialnosci_autor,
):
    # Eksport XLSX zaseedowanego raportu autorow (raport-autorow ma domyslnie
    # DOSTEP_WSZYSCY -> anonim/klient widzi).
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

    r = baker.make(Report, slug="raport-autorow")
    baker.make(
        DefinicjaRaportu,
        slug="raport-autorow",
        poziom=DefinicjaRaportu.POZIOM_AUTOR,
        report=r,
        poziom_dostepu=DefinicjaRaportu.DOSTEP_WSZYSCY,
        aktywny=True,
    )
    ds = baker.make(Datasource, dsl_query='tytul_oryginalny = "fa"', distinct=True)

    base_model = ContentType.objects.get_for_model(Rekord)

    t = baker.make(Table, base_model=base_model)
    baker.make(Column, parent=t, attr_name="tytul_oryginalny")

    baker.make(
        ReportElement,
        parent=r,
        data_from=DATA_FROM_DATASOURCE,
        base_model=base_model,
        datasource=ds,
        table=t,
    )

    url = (
        reverse(
            "nowe_raporty:raport_generuj",
            args=("raport-autorow", autor_jan_kowalski.pk, rok, rok),
        )
        + "?_export=xlsx&_tzju=True"
    )
    res = client.get(url)

    # Sprawdź, czy to XLS
    wb = openpyxl.load_workbook(BytesIO(res.content))
    assert len(wb.worksheets) == 1


@pytest.mark.django_db
def test_form_defaults_napis_przed_po(uczelnia, admin_client):
    # FormRepresentation html_before/html_after renderuja sie na stronie
    # generycznego formularza raportu (formdefaults per dynamiczna klasa).
    NAPIS_PRZED = b"napis przed"
    NAPIS_PO = b"napis po"

    seed_default_reports()  # raport-autorow -> DOSTEP_WSZYSCY
    definicja = DefinicjaRaportu.objects.get(slug="raport-autorow")
    url = reverse("nowe_raporty:raport_form", args=[definicja.slug])

    res = admin_client.get(url)
    for n in NAPIS_PO, NAPIS_PRZED:
        assert n not in res.content

    rep = FormRepresentation.objects.get_or_create_for_instance(
        form_class_dla(definicja)()
    )
    rep.html_before = NAPIS_PRZED
    rep.html_after = NAPIS_PO
    rep.save()

    res = admin_client.get(url)
    for n in NAPIS_PO, NAPIS_PRZED:
        assert n in res.content


@pytest.mark.django_db
def test_generuj_get_context_data_ukryj_statusy(rf, uczelnia, przed_korekta):
    # ukryte_statusy("raporty") wyklucza rekordy o danym statusie korekty z
    # bazowego querysetu raportu (generyczny RaportGenerujView).
    seed_default_reports()
    definicja = DefinicjaRaportu.objects.get(slug="raport-autorow")

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)

    v = RaportGenerujView()
    v.kwargs = dict(slug=definicja.slug, od_roku=0, do_roku=3000)
    v.object = None
    v.request = rf.get("/", data={"_tzju": "True"})
    res = v.get_context_data()
    query = str(res["report"].base_queryset.query)
    assert """AND NOT ("bpp_rekord_mat"."status_korekty_id" IN """ in query


@pytest.mark.django_db
def test_invalid_character_slash_sheet_title(
    autor_jan_kowalski, admin_client, raport_autorow
):
    # Tytuly arkuszy XLSX z "/" sa sanityzowane (Invalid character / in sheet
    # title). raport_autorow (conftest) tworzy Report; dorabiamy DefinicjaRaportu.
    baker.make(
        DefinicjaRaportu,
        slug="raport-autorow",
        poziom=DefinicjaRaportu.POZIOM_AUTOR,
        report=raport_autorow,
        poziom_dostepu=DefinicjaRaportu.DOSTEP_WSZYSCY,
        aktywny=True,
    )
    url = reverse(
        "nowe_raporty:raport_generuj",
        args=("raport-autorow", autor_jan_kowalski.pk, 2020, 2020),
    )
    res = admin_client.get(url, data={"_tzju": "True", "_export": "xlsx"})
    assert res.status_code == 200
