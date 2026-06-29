import pytest
from django.urls import reverse
from model_bakery import baker

from rozbieznosci.models import IgnorowanaRozbieznosc


@pytest.mark.django_db
def test_index_200_dla_kazdej_metryki(client_with_group):
    for slug in ["if", "mnisw", "kw_scopus", "kw_wos"]:
        url = reverse("rozbieznosci:index", kwargs={"metryka": slug})
        assert client_with_group.get(url).status_code == 200


@pytest.mark.django_db
def test_index_404_dla_zlej_metryki(client_with_group):
    # 'foo' nie jest slugiem metryki
    resp = client_with_group.get("/rozbieznosci/foo/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_set_aktualizuje_z_zrodla(client_with_group):
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Punktacja_Zrodla", zrodlo=zrodlo, rok=2023, impact_factor="2.500")
    wc = baker.make(
        "bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, impact_factor="1.500"
    )
    url = reverse("rozbieznosci:index", kwargs={"metryka": "if"})
    client_with_group.get(f"{url}?_set={wc.pk}")
    wc.refresh_from_db()
    assert str(wc.impact_factor) == "2.500"


@pytest.mark.django_db
def test_ignore_dodaje_per_metryka(client_with_group):
    wc = baker.make("bpp.Wydawnictwo_Ciagle")
    url = reverse("rozbieznosci:index", kwargs={"metryka": "kw_wos"})
    client_with_group.get(f"{url}?_ignore={wc.pk}")
    assert IgnorowanaRozbieznosc.objects.filter(metryka="kw_wos", rekord=wc).exists()
