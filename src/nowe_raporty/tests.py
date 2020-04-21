import pytest
import xlrd
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from flexible_reports.models import (
    ReportElement,
    DATA_FROM_DATASOURCE,
    Datasource,
    Table,
    Column,
)
from flexible_reports.models.report import Report
from mock import patch
from model_mommy import mommy

from bpp.models import OpcjaWyswietlaniaField
from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.struktura import Jednostka, Wydzial
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from nowe_raporty.views import (
    GenerujRaportDlaAutora,
    GenerujRaportDlaJednostki,
    GenerujRaportDlaWydzialu,
)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "view,klass",
    [
        ("autor_generuj", Autor),
        ("jednostka_generuj", Jednostka),
        ("wydzial_generuj", Wydzial),
    ],
)
def test_view_raport_nie_zdefiniowany(app, view, klass):
    obj = mommy.make(klass)
    v = reverse("nowe_raporty:" + view, args=(obj.pk, 2017, 2017))
    res = app.get(v)

    assert "Nie znaleziono definicji" in res.text


@pytest.mark.django_db
@pytest.mark.parametrize(
    "view,klass,report_slug",
    [
        (GenerujRaportDlaAutora, Autor, "raport-autorow"),
        (GenerujRaportDlaJednostki, Jednostka, "raport-jednostek"),
        (GenerujRaportDlaWydzialu, Wydzial, "raport-wydzialow"),
    ],
)
def test_view_raport_zdefiniowany(view, klass, report_slug, rf):
    obj = mommy.make(klass)
    v = view(kwargs=dict(od_roku=2017, do_roku=2017))
    v.object = obj
    mommy.make(Report, slug=report_slug)

    v.request = rf.get("/")
    ret = v.get_context_data()

    assert ret["report"] is not None

    assert ret["report"].base_queryset.all().count() == 0


@pytest.fixture
def autor(typy_odpowiedzialnosci):
    swoja_jednostka = mommy.make(Jednostka, skupia_pracownikow=True)
    obca_jednostka = mommy.make(Jednostka, skupia_pracownikow=False)

    autor = mommy.make(Autor)

    wc1 = mommy.make(Wydawnictwo_Ciagle)
    wc2 = mommy.make(Wydawnictwo_Ciagle)

    wc1.dodaj_autora(autor, swoja_jednostka, zapisany_jako="lel")
    wc2.dodaj_autora(autor, obca_jednostka, zapisany_jako="lol", afiliuje=False)

    return autor


@pytest.mark.django_db
def test_rekord_prace_autora(autor):
    assert Rekord.objects.prace_autora(autor).count() == 2


@pytest.mark.django_db
def test_rekord_prace_autora_z_afiliowanych_jednostek(autor):
    assert Rekord.objects.prace_autora_z_afiliowanych_jednostek(autor).count() == 1


def test_GenerujRaportDlaAutora_get_base_queryset(rf):
    with patch.object(
        Rekord.objects, "prace_autora_z_afiliowanych_jednostek"
    ) as prace_z_afiliowanych:
        with patch.object(Rekord.objects, "prace_autora") as prace_autora:
            x = GenerujRaportDlaAutora()
            x.request = rf.get("/", data={"_tzju": "True"})
            x.object = None
            x.get_base_queryset()

            prace_z_afiliowanych.assert_called_once()
            prace_autora.assert_not_called()

    with patch.object(
        Rekord.objects, "prace_autora_z_afiliowanych_jednostek"
    ) as prace_z_afiliowanych:
        with patch.object(Rekord.objects, "prace_autora") as prace_autora:
            x = GenerujRaportDlaAutora()
            x.request = rf.get("/", data={"_tzju": "False"})
            x.object = None
            x.get_base_queryset()

            prace_z_afiliowanych.assert_not_called()
            prace_autora.assert_called_once()


@pytest.mark.django_db
def test_czy_jednostka_form_niewidoczny_dla_anonimow(webtest_app, uczelnia):
    mommy.make(Report, slug="raport-jednostek")
    res = webtest_app.get(reverse("nowe_raporty:jednostka_form"))
    assert res.status_code == 302
    assert "login" in res.location


@pytest.mark.django_db
def test_czy_jednostka_form_widoczny_dla_zalogowanych(app):
    mommy.make(Report, slug="raport-jednostek")
    res = app.get(reverse("nowe_raporty:jednostka_form"))
    assert res.status_code == 200


@pytest.mark.django_db
def test_czy_generuj_jednostka_niewidoczny_dla_anonimow(webtest_app, jednostka):
    mommy.make(Report, slug="raport-jednostek")
    res = webtest_app.get(
        reverse("nowe_raporty:jednostka_generuj", args=(jednostka.pk, 2018, 2020))
    )
    assert res.status_code == 302
    assert "login" in res.location


@pytest.mark.django_db
def test_czy_generuj_jednostka_widoczny_dla_zalogowanych(app, jednostka):
    mommy.make(Report, slug="raport-jednostek")
    res = app.get(
        reverse("nowe_raporty:jednostka_generuj", args=(jednostka.pk, 2018, 2020))
    )
    assert res.status_code == 200


@pytest.mark.django_db
def test_czy_wydzial_form_niewidoczny_dla_anonimow(webtest_app, uczelnia):
    mommy.make(Report, slug="raport-wydzialow")
    res = webtest_app.get(reverse("nowe_raporty:wydzial_form"))
    assert res.status_code == 302
    assert "login" in res.location


@pytest.mark.django_db
def test_czy_wydzial_form_widoczny_dla_zalogowanych(app):
    mommy.make(Report, slug="raport-wydzialow")
    res = app.get(reverse("nowe_raporty:wydzial_form"))
    assert res.status_code == 200


@pytest.mark.django_db
def test_czy_generuj_wydzial_niewidoczny_dla_anonimow(webtest_app, wydzial):
    mommy.make(Report, slug="raport-wydzialow")
    res = webtest_app.get(
        reverse("nowe_raporty:wydzial_generuj", args=(wydzial.pk, 2018, 2020))
    )
    assert res.status_code == 302
    assert "login" in res.location


@pytest.mark.django_db
def test_czy_generuj_wydzial_widoczny_dla_zalogowanych(app, wydzial):
    mommy.make(Report, slug="raport-wydzialow")
    res = app.get(
        reverse("nowe_raporty:wydzial_generuj", args=(wydzial.pk, 2018, 2020))
    )
    assert res.status_code == 200


@pytest.mark.django_db
def test_czy_raport_autorow_generuj_i_form_przestrzegaja_ustawien_anonim(
    webtest_app, uczelnia, autor_jan_kowalski
):
    mommy.make(Report, slug="raport-autorow")

    urls = [
        reverse("nowe_raporty:autor_generuj", args=(autor_jan_kowalski.pk, 2018, 2020)),
        reverse("nowe_raporty:autor_form"),
    ]

    for url in urls:
        uczelnia.pokazuj_raport_autorow = OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM
        uczelnia.save()

        res = webtest_app.get(url)
        assert res.status_code == 302
        assert "login" in res.location

        uczelnia.pokazuj_raport_autorow = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
        uczelnia.save()

        res = webtest_app.get(url)
        assert res.status_code == 200

        uczelnia.pokazuj_raport_autorow = OpcjaWyswietlaniaField.POKAZUJ_NIGDY
        uczelnia.save()

        webtest_app.get(url, status=404)


@pytest.mark.django_db
def test_czy_raport_jednostek_generuj_i_form_przestrzegaja_ustawien_anonim(
    webtest_app, uczelnia, jednostka
):
    mommy.make(Report, slug="raport-jednostek")

    urls = [
        reverse("nowe_raporty:jednostka_generuj", args=(jednostka.pk, 2018, 2020)),
        reverse("nowe_raporty:jednostka_form"),
    ]

    for url in urls:
        uczelnia.pokazuj_raport_jednostek = OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM
        uczelnia.save()

        res = webtest_app.get(url)
        assert res.status_code == 302
        assert "login" in res.location

        uczelnia.pokazuj_raport_jednostek = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
        uczelnia.save()

        res = webtest_app.get(url)
        assert res.status_code == 200

        uczelnia.pokazuj_raport_jednostek = OpcjaWyswietlaniaField.POKAZUJ_NIGDY
        uczelnia.save()

        webtest_app.get(url, status=404)


@pytest.mark.django_db
def test_czy_raport_wydzialow_generuj_i_form_przestrzegaja_ustawien_anonim(
    webtest_app, uczelnia, wydzial
):
    mommy.make(Report, slug="raport-wydzialow")

    urls = [
        reverse("nowe_raporty:wydzial_generuj", args=(wydzial.pk, 2018, 2020)),
        reverse("nowe_raporty:wydzial_form"),
    ]

    for url in urls:
        uczelnia.pokazuj_raport_wydzialow = OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM
        uczelnia.save()

        res = webtest_app.get(url)
        assert res.status_code == 302
        assert "login" in res.location

        uczelnia.pokazuj_raport_wydzialow = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
        uczelnia.save()

        res = webtest_app.get(url)
        assert res.status_code == 200

        uczelnia.pokazuj_raport_wydzialow = OpcjaWyswietlaniaField.POKAZUJ_NIGDY
        uczelnia.save()

        webtest_app.get(url, status=404)


@pytest.mark.django_db
def test_czy_raport_autorow_generuj_i_form_przestrzegaja_ustawien_zalogowany(
    app, uczelnia, autor_jan_kowalski
):
    mommy.make(Report, slug="raport-autorow")

    urls = [
        reverse("nowe_raporty:autor_generuj", args=(autor_jan_kowalski.pk, 2018, 2020)),
        reverse("nowe_raporty:autor_form"),
    ]

    for url in urls:
        uczelnia.pokazuj_raport_autorow = OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM
        uczelnia.save()

        res = app.get(url)
        assert res.status_code == 200

        uczelnia.pokazuj_raport_autorow = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
        uczelnia.save()

        res = app.get(url)
        assert res.status_code == 200

        uczelnia.pokazuj_raport_autorow = OpcjaWyswietlaniaField.POKAZUJ_NIGDY
        uczelnia.save()

        app.get(url, status=404)


@pytest.mark.django_db
def test_czy_raport_jednostek_generuj_i_form_przestrzegaja_ustawien_zalogowany(
    app, uczelnia, jednostka
):
    mommy.make(Report, slug="raport-jednostek")

    urls = [
        reverse("nowe_raporty:jednostka_generuj", args=(jednostka.pk, 2018, 2020)),
        reverse("nowe_raporty:jednostka_form"),
    ]

    for url in urls:
        uczelnia.pokazuj_raport_jednostek = OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM
        uczelnia.save()

        res = app.get(url)
        assert res.status_code == 200

        uczelnia.pokazuj_raport_jednostek = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
        uczelnia.save()

        res = app.get(url)
        assert res.status_code == 200

        uczelnia.pokazuj_raport_jednostek = OpcjaWyswietlaniaField.POKAZUJ_NIGDY
        uczelnia.save()

        app.get(url, status=404)


@pytest.mark.django_db
def test_czy_raport_wydzialow_generuj_i_form_przestrzegaja_ustawien_zalogowany(
    app, uczelnia, wydzial
):
    mommy.make(Report, slug="raport-wydzialow")

    urls = [
        reverse("nowe_raporty:wydzial_generuj", args=(wydzial.pk, 2018, 2020)),
        reverse("nowe_raporty:wydzial_form"),
    ]

    for url in urls:
        uczelnia.pokazuj_raport_wydzialow = OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM
        uczelnia.save()

        res = app.get(url)
        assert res.status_code == 200

        uczelnia.pokazuj_raport_wydzialow = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
        uczelnia.save()

        res = app.get(url)
        assert res.status_code == 200

        uczelnia.pokazuj_raport_wydzialow = OpcjaWyswietlaniaField.POKAZUJ_NIGDY
        uczelnia.save()

        app.get(url, status=404)


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
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

    r = mommy.make(Report, slug="raport-autorow")
    ds = mommy.make(Datasource, dsl_query='tytul_oryginalny = "fa"', distinct=True)

    base_model = ContentType.objects.get_for_model(Rekord)

    t = mommy.make(Table, base_model=base_model)
    mommy.make(Column, parent=t, attr_name="tytul_oryginalny")

    mommy.make(
        ReportElement,
        parent=r,
        data_from=DATA_FROM_DATASOURCE,
        base_model=base_model,
        datasource=ds,
        table=t,
    )

    url = (
        reverse("nowe_raporty:autor_generuj", args=(autor_jan_kowalski.pk, rok, rok))
        + "?_export=xlsx&_tzju=True"
    )
    res = client.get(url)

    # Sprawdź, czy to XLS
    wb = xlrd.open_workbook(file_contents=res.content)
    assert len(wb.sheets()) == 1
