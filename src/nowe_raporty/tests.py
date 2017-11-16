import pytest
from django.test.client import RequestFactory
from django.urls import reverse
from mock import patch
from model_mommy import mommy

from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.struktura import Jednostka, Wydzial
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from flexible_reports.models.report import Report
from nowe_raporty.views import GenerujRaportDlaAutora, \
    GenerujRaportDlaJednostki, GenerujRaportDlaWydzialu

rf = RequestFactory()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "view,klass",
    [("autor_generuj", Autor),
     ("jednostka_generuj", Jednostka),
     ("wydzial_generuj", Wydzial)]
)
def test_view_raport_nie_zdefiniowany(client, view, klass):
    obj = mommy.make(klass)
    v = reverse("nowe_raporty:" + view,
        args=(obj.pk, 2017, 2017))
    res = client.get(v)

    assert "Nie znaleziono definicji" in res.rendered_content


@pytest.mark.django_db
@pytest.mark.parametrize(
    "view,klass,report_slug",
    [(GenerujRaportDlaAutora, Autor, "raport-autorow"),
     (GenerujRaportDlaJednostki, Jednostka, "raport-jednostek"),
     (GenerujRaportDlaWydzialu, Wydzial, "raport-wydzialow")]
)
def test_view_raport_zdefiniowany(view, klass, report_slug):
    obj = mommy.make(klass)
    v = view(kwargs=dict(od_roku=2017, do_roku=2017))
    v.object = obj
    r = mommy.make(Report, slug=report_slug)

    v.request = rf.get("/")
    ret = v.get_context_data()

    assert ret['report'] is not None

    assert ret['report'].base_queryset.all().count() == 0


@pytest.fixture
def autor(typy_odpowiedzialnosci):
    swoja_jednostka = mommy.make(Jednostka, skupia_pracownikow=True)
    obca_jednostka = mommy.make(Jednostka, skupia_pracownikow=False)

    autor = mommy.make(Autor)

    wc1 = mommy.make(Wydawnictwo_Ciagle)
    wc2 = mommy.make(Wydawnictwo_Ciagle)

    wc1.dodaj_autora(autor, swoja_jednostka, zapisany_jako="lel")
    wc2.dodaj_autora(autor, obca_jednostka, zapisany_jako="lol")

    return autor


@pytest.mark.django_db
def test_rekord_prace_autora(autor):
    assert Rekord.objects.prace_autora(autor).count() == 2


@pytest.mark.django_db
def test_rekord_prace_autora_z_afiliowanych_jednostek(autor):
    assert Rekord.objects.prace_autora_z_afiliowanych_jednostek(
        autor).count() == 1


def test_GenerujRaportDlaAutora_get_base_queryset():
    with patch.object(Rekord.objects,
                      "prace_autora_z_afiliowanych_jednostek") as prace_z_afiliowanych:
        with patch.object(Rekord.objects, "prace_autora") as prace_autora:
            x = GenerujRaportDlaAutora()
            x.request = rf.get("/", data={"_tzju": "True"})
            x.object = None
            x.get_base_queryset()

            prace_z_afiliowanych.assert_called_once()
            prace_autora.assert_not_called()

    with patch.object(Rekord.objects,
                      "prace_autora_z_afiliowanych_jednostek") as prace_z_afiliowanych:
        with patch.object(Rekord.objects, "prace_autora") as prace_autora:
            x = GenerujRaportDlaAutora()
            x.request = rf.get("/", data={"_tzju": "False"})
            x.object = None
            x.get_base_queryset()

            prace_z_afiliowanych.assert_not_called()
            prace_autora.assert_called_once()
