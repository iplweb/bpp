"""
Tests for admin actions and default behaviors.

This module contains Selenium tests that verify:
- User creation in admin (bug regression test)
- Default affiliation settings for new and existing records
"""

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

import pytest
from model_bakery import baker

from bpp.const import TO_AUTOR
from bpp.models import (
    Autor,
    Jednostka,
    Typ_Odpowiedzialnosci,
    Uczelnia,
    Wydawnictwo_Ciagle,
)
from bpp.models.patent import Patent
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.tests import add_extra_autor_inline
from django_bpp.selenium_util import wait_for_page_load

pytestmark = [pytest.mark.slow, pytest.mark.selenium]


def test_bug_on_user_add(admin_browser, channels_live_server):
    """Test that user creation in admin works without errors (regression test)."""
    admin_browser.visit(channels_live_server.url + reverse("admin:bpp_bppuser_add"))
    admin_browser.fill("username", "as")
    admin_browser.fill("password1", "as")
    admin_browser.fill("password2", "as")
    with wait_for_page_load(admin_browser):
        admin_browser.find_by_name("_continue").click()

    admin_browser.wait_for_condition(lambda browser: "Zmień użytkownik" in browser.html)


@pytest.mark.parametrize("expected", [True, False])
@pytest.mark.parametrize(
    "url",
    ["wydawnictwo_ciagle", "wydawnictwo_zwarte", "patent"],
)
def test_admin_domyslnie_afiliuje_nowy_rekord(
    admin_browser,
    channels_live_server,
    url,
    expected,
):
    """Test that default affiliation setting is applied to new records."""
    # twórz nowy obiekt, nie używaj z fixtury, bo db i transactional_db
    baker.make(Uczelnia, domyslnie_afiliuje=expected)

    browser = admin_browser
    with wait_for_page_load(browser):
        browser.visit(channels_live_server.url + reverse(f"admin:bpp_{url}_add"))

    add_extra_autor_inline(browser)

    v = browser.find_by_id("id_autorzy_set-0-afiliuje")
    assert v.checked == expected


@pytest.mark.parametrize("afiliowany", [True, False])
@pytest.mark.parametrize("expected", [True, False])
@pytest.mark.parametrize(
    "url,klasa",
    [
        ("wydawnictwo_ciagle", Wydawnictwo_Ciagle),
        ("wydawnictwo_zwarte", Wydawnictwo_Zwarte),
        ("patent", Patent),
    ],
)
# @pytest.mark.django_db(transaction=True)
def test_admin_domyslnie_afiliuje_istniejacy_rekord(
    admin_browser, channels_live_server, url, klasa, expected, afiliowany, denorms
):
    """Test that default affiliation setting is applied to new authors on existing records."""
    # twórz nowy obiekt, nie używaj z fixtury, bo db i transactional_db
    baker.make(Uczelnia, domyslnie_afiliuje=expected)
    autor = baker.make(Autor, nazwisko="Kowal", imiona="Ski")
    jednostka = baker.make(Jednostka, nazwa="Lol", skrot="WT")
    wydawnictwo = baker.make(klasa, tytul_oryginalny="test")
    Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot="aut.", nazwa="autor", typ_ogolny=TO_AUTOR
    )
    wa = wydawnictwo.dodaj_autora(autor, jednostka, zapisany_jako="Wutlolski")
    wa.afiliowany = afiliowany
    wa.save()

    browser = admin_browser
    with wait_for_page_load(browser):
        browser.visit(
            channels_live_server.url
            + reverse(f"admin:bpp_{url}_change", args=(wydawnictwo.pk,))
        )

    add_extra_autor_inline(browser)

    v = browser.find_by_id("id_autorzy_set-1-afiliuje")
    assert v.checked == expected
