"""Playwright tests for reports functionality."""

import pytest
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import Page

from bpp.tests.util import CURRENT_YEAR, any_autor, any_ciagle, any_jednostka

pytestmark = [pytest.mark.slow, pytest.mark.playwright]


@pytest.mark.django_db
@pytest.fixture
def jednostka_raportow(
    typy_odpowiedzialnosci, jezyki, statusy_korekt, typy_kbn, charaktery_formalne
):
    """Create a jednostka with an author and publications for report testing."""
    j = any_jednostka(nazwa="Jednostka")
    a = any_autor()

    c = any_ciagle(rok=CURRENT_YEAR)
    c.dodaj_autora(a, j)

    d = any_ciagle(rok=CURRENT_YEAR - 1)
    d.dodaj_autora(a, j)

    e = any_ciagle(rok=CURRENT_YEAR - 2)
    e.dodaj_autora(a, j)

    return j


@pytest.mark.django_db(transaction=True)
def test_ranking_autorow(admin_page: Page, jednostka_raportow, channels_live_server):
    """Test that ranking_autorow form has correct default year."""
    admin_page.goto(channels_live_server.url + reverse("bpp:ranking_autorow_formularz"))
    admin_page.wait_for_load_state("domcontentloaded")

    now = timezone.now()

    if now.month < 2:
        val = CURRENT_YEAR - 1
    else:
        val = CURRENT_YEAR

    assert f'value="{val}"' in admin_page.content()
