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
def test_formularz_ma_3_tryby_i_kasuj_checkbox(client_with_group):
    url = reverse("rozbieznosci:index", kwargs={"metryka": "if"})
    html = client_with_group.get(url).content.decode()
    # 3-opcyjny wybór trybu źródła
    assert 'name="tryb_zrodla"' in html
    for label in [
        "Standardowy",
        "Pokazuj również zerowe rekordy",
        "Pokazuj wyłącznie zerowe rekordy",
    ]:
        assert label in html
    # checkbox kasowania oraz popup charakteru formalnego
    assert 'name="kasuj_przy_pustym_zrodle"' in html
    assert 'name="charaktery_formalne"' in html


@pytest.mark.django_db
def test_confirm_threaduje_tryb_zrodla(client_with_group):
    """Ekran confirm ma hidden z tryb_zrodla gdy filtr był aktywny."""
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Punktacja_Zrodla", zrodlo=zrodlo, rok=2023, impact_factor="0.000")
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, impact_factor="1.000")
    url = reverse("rozbieznosci:ustaw_wszystkie", kwargs={"metryka": "if"})
    html = client_with_group.get(
        f"{url}?rok_od=2022&rok_do=2026&tryb_zrodla=rowniez"
    ).content.decode()
    assert 'name="tryb_zrodla"' in html
