import pytest
from django.test.client import RequestFactory
from model_mommy import mommy

from bpp.models.autor import Autor
from bpp.models.profile import BppUser
from bpp.models.struktura import Jednostka, Wydzial
from flexible_reports.models.report import Report
from nowe_raporty.views import GenerujRaportDlaAutora, \
    GenerujRaportDlaJednostki, GenerujRaportDlaWydzialu
from django.urls import reverse
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
    ret = v.get_context_data()

    assert ret['report'] is not None

    assert ret['report'].base_queryset.all().count() == 0
