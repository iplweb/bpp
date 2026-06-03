import pytest
from model_bakery import baker

from bpp.views.browse import LataView, RokView
from fixtures.conftest_multisite import make_request_for_site


def _dwie_prace(
    jednostka_uczelnia1, jednostka_uczelnia2, autor_uczelnia1, autor_uczelnia2
):
    w1 = baker.make("bpp.Wydawnictwo_Ciagle", rok=2020)
    w1.dodaj_autora(autor_uczelnia1, jednostka_uczelnia1)
    w2 = baker.make("bpp.Wydawnictwo_Ciagle", rok=2021)
    w2.dodaj_autora(autor_uczelnia2, jednostka_uczelnia2)


@pytest.mark.django_db
def test_lata_view_liczy_tylko_swoja_uczelnie(
    uczelnia1,
    uczelnia2,
    site1,
    jednostka_uczelnia1,
    jednostka_uczelnia2,
    autor_uczelnia1,
    autor_uczelnia2,
    settings,
):
    settings.ALLOWED_HOSTS = ["*"]
    _dwie_prace(
        jednostka_uczelnia1, jednostka_uczelnia2, autor_uczelnia1, autor_uczelnia2
    )
    view = LataView()
    view.request = make_request_for_site(site1)
    view.kwargs = {}
    lata = {y["year"] for y in view.get_queryset()}
    assert 2020 in lata
    assert 2021 not in lata


@pytest.mark.django_db
def test_rok_view_listuje_tylko_swoja_uczelnie(
    uczelnia1,
    uczelnia2,
    site1,
    jednostka_uczelnia1,
    jednostka_uczelnia2,
    autor_uczelnia1,
    autor_uczelnia2,
    settings,
):
    settings.ALLOWED_HOSTS = ["*"]
    _dwie_prace(
        jednostka_uczelnia1, jednostka_uczelnia2, autor_uczelnia1, autor_uczelnia2
    )
    view = RokView()
    view.request = make_request_for_site(site1)
    view.kwargs = {"rok": 2021}
    view.object_list = view.get_queryset()
    ctx = view.get_context_data()
    assert ctx["total_count"] == 0  # praca 2021 należy do uczelni2
