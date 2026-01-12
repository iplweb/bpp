"""
Tests for admin actions and default behaviors.

This module contains Playwright tests that verify:
- User creation in admin (bug regression test)
- Default affiliation settings for new and existing records
"""

from django.urls import reverse

import pytest
from model_bakery import baker
from playwright.sync_api import Page

from bpp.models import Uczelnia


def test_bug_on_user_add(admin_page: Page, channels_live_server):
    """Test that user creation in admin works without errors (regression test)."""
    admin_page.goto(channels_live_server.url + reverse("admin:bpp_bppuser_add"))
    admin_page.fill('input[name="username"]', "as")
    admin_page.fill('input[name="password1"]', "as")
    admin_page.fill('input[name="password2"]', "as")
    admin_page.click('input[name="_continue"]')

    # Wait for navigation and check the new page contains the expected text
    admin_page.wait_for_load_state("domcontentloaded")
    assert "Zmień użytkownik" in admin_page.content()


@pytest.mark.parametrize("expected", [True, False])
@pytest.mark.parametrize(
    "url",
    ["wydawnictwo_ciagle", "wydawnictwo_zwarte", "patent"],
)
def test_admin_domyslnie_afiliuje_nowy_rekord(
    admin_page: Page,
    channels_live_server,
    url,
    expected,
):
    """Test that default affiliation setting is applied to new records."""
    # Create a new Uczelnia with the expected domyslnie_afiliuje setting
    baker.make(Uczelnia, domyslnie_afiliuje=expected)

    admin_page.goto(channels_live_server.url + reverse(f"admin:bpp_{url}_add"))

    # Add an extra autor inline by clicking "Dodaj powiązanie autora" link
    admin_page.get_by_text("Dodaj powiązanie autora").click()

    # Check if the afiliuje checkbox is checked according to the expected value
    checkbox = admin_page.locator("#id_autorzy_set-0-afiliuje")
    assert checkbox.is_checked() == expected


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("afiliowany", [True, False])
@pytest.mark.parametrize("expected", [True, False])
@pytest.mark.parametrize(
    "url,klasa",
    [
        ("wydawnictwo_ciagle", "Wydawnictwo_Ciagle"),
        ("wydawnictwo_zwarte", "Wydawnictwo_Zwarte"),
        ("patent", "Patent"),
    ],
)
def test_admin_domyslnie_afiliuje_istniejacy_rekord(
    admin_page: Page, channels_live_server, url, klasa, expected, afiliowany, denorms
):
    """Test that default affiliation setting is applied to new authors on existing records."""
    from bpp.const import TO_AUTOR
    from bpp.models import Autor, Jednostka, Patent, Typ_Odpowiedzialnosci
    from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
    from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte

    # twórz nowy obiekt, nie używaj z fixtury, bo db i transactional_db
    baker.make(Uczelnia, domyslnie_afiliuje=expected)
    autor = baker.make(Autor, nazwisko="Kowal", imiona="Ski")
    jednostka = baker.make(Jednostka, nazwa="Lol", skrot="WT")

    klasa_model = {"Wydawnictwo_Ciagle": Wydawnictwo_Ciagle, "Wydawnictwo_Zwarte": Wydawnictwo_Zwarte, "Patent": Patent}[
        klasa
    ]
    wydawnictwo = baker.make(klasa_model, tytul_oryginalny="test")
    Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot="aut.", nazwa="autor", typ_ogolny=TO_AUTOR
    )
    wa = wydawnictwo.dodaj_autora(autor, jednostka, zapisany_jako="Wutlolski")
    wa.afiliowany = afiliowany
    wa.save()

    admin_page.goto(
        channels_live_server.url
        + reverse(f"admin:bpp_{url}_change", args=(wydawnictwo.pk,))
    )

    # Add extra autor inline - find the visible "Dodaj powiązanie autora" link and click it
    admin_page.get_by_text("Dodaj powiązanie autora").click()

    # Wait for the new inline form to appear
    admin_page.wait_for_selector("#id_autorzy_set-1-autor", state="attached")

    # Check if the afiliuje checkbox on the NEW inline is checked according to expected value
    checkbox = admin_page.locator("#id_autorzy_set-1-afiliuje")
    assert checkbox.is_checked() == expected
