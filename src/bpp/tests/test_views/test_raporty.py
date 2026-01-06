try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

import pytest
from django.contrib.auth.models import Group

from bpp.models import Typ_Odpowiedzialnosci
from bpp.tests.util import any_autor, any_ciagle, any_jednostka
from bpp.util import rebuild_contenttypes


@pytest.fixture
def ranking_raporty_data(db, logged_in_client):
    """Fixture tworzący dane testowe dla testów rankingu."""
    rebuild_contenttypes()

    Typ_Odpowiedzialnosci.objects.get_or_create(skrot="aut.", nazwa="autor")
    Group.objects.get_or_create(name="wprowadzanie danych")

    j = any_jednostka()
    a = any_autor(nazwisko="Kowalski")
    c = any_ciagle(impact_factor=200, rok=2000)
    c.dodaj_autora(a, j)

    return {"client": logged_in_client}


def test_renderowanie(ranking_raporty_data):
    client = ranking_raporty_data["client"]
    url = reverse("bpp:ranking-autorow", args=(2000, 2000))
    res = client.get(url)
    assert res.status_code == 200
    assert "Ranking autorów" in res.content.decode()
    assert "Kowalski" in res.content.decode()


def test_renderowanie_csv(ranking_raporty_data):
    client = ranking_raporty_data["client"]
    url = reverse("bpp:ranking-autorow", args=(2000, 2000))
    res = client.get(url, data={"_export": "csv"})
    assert b'"Kowalski Jan Maria, dr",Jednostka' in res.content
