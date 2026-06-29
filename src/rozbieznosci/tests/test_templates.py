import pytest
from django.urls import reverse
from model_bakery import baker


@pytest.mark.django_db
def test_zakladki_renderowane(client_with_group):
    url = reverse("rozbieznosci:index", kwargs={"metryka": "if"})
    html = client_with_group.get(url).content.decode()
    # wszystkie 4 etykiety zakładek
    for label in ["Impact Factor", "Punkty MNiSW", "Kwartyl Scopus", "Kwartyl WoS"]:
        assert label in html
    # link do innej metryki
    assert reverse("rozbieznosci:index", kwargs={"metryka": "mnisw"}) in html


@pytest.mark.django_db
def test_checkbox_pokaz_puste_zrodla_obecny(client_with_group):
    url = reverse("rozbieznosci:index", kwargs={"metryka": "if"})
    html = client_with_group.get(url).content.decode()
    assert "pokaz_puste_zrodla" in html


@pytest.mark.django_db
def test_confirm_threaduje_pokaz(client_with_group):
    """Ekran confirm ma hidden z pokaz_puste_zrodla gdy filtr był aktywny."""
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Punktacja_Zrodla", zrodlo=zrodlo, rok=2023, impact_factor="0.000")
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, impact_factor="1.000")
    url = reverse("rozbieznosci:ustaw_wszystkie", kwargs={"metryka": "if"})
    html = client_with_group.get(
        f"{url}?rok_od=2022&rok_do=2026&pokaz_puste_zrodla=1"
    ).content.decode()
    assert 'name="pokaz_puste_zrodla"' in html
