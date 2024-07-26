try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

import pytest

from bpp.tests.util import CURRENT_YEAR, any_autor, any_ciagle, any_jednostka


def wybrany(browser):
    return browser.execute_script(
        "$('section.active div[data-slug]').attr('data-slug')"
    )


def submit_page(browser):
    browser.execute_script("$('input[name=submit]:visible').click()")


def submit_admin_page(browser):
    browser.execute_script(
        "django.jQuery('input[type=submit]:visible').first().click()"
    )


pytestmark = [pytest.mark.slow, pytest.mark.selenium]


@pytest.mark.django_db
@pytest.fixture
def jednostka_raportow(
    typy_odpowiedzialnosci, jezyki, statusy_korekt, typy_kbn, charaktery_formalne
):
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
def test_ranking_autorow(preauth_browser, jednostka_raportow, channels_live_server):
    preauth_browser.visit(
        channels_live_server.url + reverse("bpp:ranking_autorow_formularz")
    )
    from django.utils import timezone

    now = timezone.now()

    if now.month < 2:
        val = CURRENT_YEAR - 1
    else:
        val = CURRENT_YEAR

    assert 'value="%s"' % val in preauth_browser.html
