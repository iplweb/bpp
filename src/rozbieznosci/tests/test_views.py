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
    resp = client_with_group.post(url, {"_set": wc.pk})
    assert resp.status_code in (301, 302)
    wc.refresh_from_db()
    assert str(wc.impact_factor) == "2.500"


@pytest.mark.django_db
def test_ignore_dodaje_per_metryka(client_with_group):
    wc = baker.make("bpp.Wydawnictwo_Ciagle")
    url = reverse("rozbieznosci:index", kwargs={"metryka": "kw_wos"})
    resp = client_with_group.post(url, {"_ignore": wc.pk})
    assert resp.status_code in (301, 302)
    assert IgnorowanaRozbieznosc.objects.filter(metryka="kw_wos", rekord=wc).exists()


@pytest.mark.django_db
def test_post_set_zachowuje_sort_w_redirect(client_with_group):
    """Po POST _set z sort!=DEFAULT_SORT redirect URL zawiera sort=."""
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Punktacja_Zrodla", zrodlo=zrodlo, rok=2022, impact_factor="3.000")
    wc = baker.make(
        "bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2022, impact_factor="1.000"
    )
    url = reverse("rozbieznosci:index", kwargs={"metryka": "if"})
    resp = client_with_group.post(
        url,
        {"_set": wc.pk, "sort": "rok", "rok_od": 2022, "rok_do": 2026},
    )
    assert resp.status_code in (301, 302)
    assert "sort=rok" in resp.url
    wc.refresh_from_db()
    assert str(wc.impact_factor) == "3.000"


@pytest.mark.django_db
def test_get_z_set_nie_zmienia_stanu(client_with_group):
    """GET z parametrem _set nie może zmieniać stanu — get() jest side-effect-free."""
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Punktacja_Zrodla", zrodlo=zrodlo, rok=2023, impact_factor="2.500")
    wc = baker.make(
        "bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, impact_factor="1.500"
    )
    url = reverse("rozbieznosci:index", kwargs={"metryka": "if"})
    resp = client_with_group.get(f"{url}?_set={wc.pk}")
    assert resp.status_code == 200
    wc.refresh_from_db()
    assert str(wc.impact_factor) == "1.500"  # bez zmian
