import pytest
from django.test.client import RequestFactory
from flexible_reports.models.report import Report
from model_mommy import mommy

from bpp.models.autor import Autor
from bpp.models.profile import BppUser
from bpp.models.struktura import Jednostka, Wydzial
from nowe_raporty.views import GenerujRaportDlaAutora, \
    GenerujRaportDlaJednostki, GenerujRaportDlaWydzialu

rf = RequestFactory()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "view",
    [GenerujRaportDlaAutora,
     GenerujRaportDlaJednostki,
     GenerujRaportDlaWydzialu]
)
def test_view_raport_nie_zdefiniowany(view):
    autor = mommy.make(Autor)
    v = view(kwargs=dict(rok=2017))
    v.object = autor
    ret = v.get_context_data()

    assert ret['report'] is None

    v.request = rf.get("/foo")
    superuser = BppUser.objects.create_superuser(
        "asdf", "Asdf@.asdfpl", "asdf")
    v.request.user = superuser
    v.request.session = {}
    ret = v.render_to_response({})
    ret.render()

    assert "Nie znaleziono definicji" in ret.rendered_content


@pytest.mark.django_db
@pytest.mark.parametrize(
    "view,klass,report_slug",
    [(GenerujRaportDlaAutora, Autor, "raport-autorow"),
     (GenerujRaportDlaJednostki, Jednostka, "raport-jednostek"),
     (GenerujRaportDlaWydzialu, Wydzial, "raport-wydzialow")]
)
def test_view_raport_zdefiniowany(view, klass, report_slug):
    obj = mommy.make(klass)
    v = view(kwargs=dict(rok=2017))
    v.object = obj
    r = mommy.make(Report, slug=report_slug)
    ret = v.get_context_data()

    assert ret['report'] is not None

    assert ret['report'].base_queryset.all().count() == 0
