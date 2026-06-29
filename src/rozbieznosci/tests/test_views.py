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
def test_index_oznacza_brak_wpisu_zrodla(client_with_group):
    """Rekord bez wiersza Punktacja_Zrodla za rok pracy: w trybie standardowym
    niewidoczny; w 'również zerowe' widoczny, oznaczony, bez przycisku
    ustawiania (kasuj wyłączone)."""
    zrodlo = baker.make("bpp.Zrodlo")
    # celowo BEZ Punktacja_Zrodla dla (zrodlo, 2023)
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, impact_factor="1.500")
    url = reverse("rozbieznosci:index", kwargs={"metryka": "if"})

    # tryb standardowy — niewidoczny (brak markera)
    bez = client_with_group.get(url)
    assert bez.status_code == 200
    assert "brak wpisu za 2023" not in bez.content.decode()

    # tryb "również zerowe" — widoczny, oznaczony, bez przycisku ustawiania
    resp = client_with_group.get(f"{url}?tryb_zrodla=rowniez")
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "brak wpisu za 2023" in content
    assert "Źródło bez wartości za 2023" in content
    assert "ustaw wg źródła" not in content


@pytest.mark.django_db
def test_index_kasuj_on_udostepnia_przycisk_dla_braku_zrodla(client_with_group):
    """Przy kasuj=on rekord bez wartości w źródle dostaje aktywny przycisk
    (akcja wyczyści wartość w pracy)."""
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, impact_factor="1.500")
    url = reverse("rozbieznosci:index", kwargs={"metryka": "if"})
    resp = client_with_group.get(
        f"{url}?tryb_zrodla=rowniez&kasuj_przy_pustym_zrodle=1"
    )
    content = resp.content.decode()
    assert "brak wpisu za 2023" in content
    assert "ustaw wg źródła" in content


@pytest.mark.django_db
def test_set_brak_zrodla_kasuj_off_pomija_i_komunikuje(client_with_group):
    """POST _set na rekordzie bez wartości w źródle z kasuj=off: praca bez
    zmian, komunikat o pominięciu."""
    zrodlo = baker.make("bpp.Zrodlo")
    wc = baker.make(
        "bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, impact_factor="1.500"
    )
    url = reverse("rozbieznosci:index", kwargs={"metryka": "if"})
    resp = client_with_group.post(
        url, {"_set": wc.pk, "tryb_zrodla": "rowniez"}, follow=True
    )
    wc.refresh_from_db()
    assert str(wc.impact_factor) == "1.500"
    assert any("pominięty" in str(m) for m in resp.context["messages"])


@pytest.mark.django_db
def test_ustaw_wszystkie_brak_zrodla_kasuj_off_komunikuje_pominiete(client_with_group):
    """Bug 'rozdźwięk': rekord bez wartości w źródle widoczny w 'wyłącznie
    zerowe', ale 'ustaw wszystkie' z kasuj=off pomija go i jasno komunikuje
    (zamiast cichego 'zaktualizowano 0')."""
    zrodlo = baker.make("bpp.Zrodlo")
    wc = baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, kwartyl_w_wos=2)
    url = reverse("rozbieznosci:ustaw_wszystkie", kwargs={"metryka": "kw_wos"})
    resp = client_with_group.post(
        url,
        {"tryb_zrodla": "wylacznie", "rok_od": 2022, "rok_do": 2026},
        follow=True,
    )
    wc.refresh_from_db()
    assert wc.kwartyl_w_wos == 2  # nie ruszone
    assert any("Pominięto 1" in str(m) for m in resp.context["messages"])


@pytest.mark.django_db
def test_ustaw_wszystkie_kasuj_on_czysci(client_with_group):
    """POST 'ustaw wszystkie' z kasuj=on dla rekordu bez wartości w źródle:
    wartość w pracy wyczyszczona, komunikat o aktualizacji."""
    zrodlo = baker.make("bpp.Zrodlo")
    wc = baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, kwartyl_w_wos=2)
    url = reverse("rozbieznosci:ustaw_wszystkie", kwargs={"metryka": "kw_wos"})
    resp = client_with_group.post(
        url,
        {
            "tryb_zrodla": "wylacznie",
            "kasuj_przy_pustym_zrodle": "1",
            "rok_od": 2022,
            "rok_do": 2026,
        },
        follow=True,
    )
    wc.refresh_from_db()
    assert wc.kwartyl_w_wos is None
    assert any("Zaktualizowano 1" in str(m) for m in resp.context["messages"])


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
