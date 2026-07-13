import pytest
from model_bakery import baker

from fixtures.conftest_multisite import make_request_for_site
from ranking_autorow.views import RankingAutorow


@pytest.mark.django_db
def test_ranking_listuje_tylko_aktualnych_pracownikow_uczelni(settings,
    uczelnia1,
    uczelnia2,
    site1,
    jednostka_uczelnia1,
    jednostka_uczelnia2,
    autor_uczelnia1,
    autor_uczelnia2, typy_odpowiedzialnosci):
    settings.ALLOWED_HOSTS = ["*"]
    w1 = baker.make("bpp.Wydawnictwo_Ciagle", impact_factor=10, rok=2020)
    w1.dodaj_autora(autor_uczelnia1, jednostka_uczelnia1)
    w2 = baker.make("bpp.Wydawnictwo_Ciagle", impact_factor=10, rok=2020)
    w2.dodaj_autora(autor_uczelnia2, jednostka_uczelnia2)

    r = RankingAutorow(
        request=make_request_for_site(site1), kwargs=dict(od_roku=0, do_roku=3030)
    )
    autorzy = {row.autor.pk for row in r.get_queryset()}
    assert autor_uczelnia1.pk in autorzy
    assert autor_uczelnia2.pk not in autorzy
