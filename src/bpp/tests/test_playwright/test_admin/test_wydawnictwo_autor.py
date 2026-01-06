import pytest
from django.urls import reverse
from playwright.sync_api import Page

from bpp.tests import normalize_html


@pytest.mark.django_db
@pytest.mark.parametrize("klass", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_changelist_no_argument(klass, live_server, admin_page: Page):
    url = f"admin:bpp_{klass}_autor_changelist"
    admin_page.goto(live_server.url + reverse(url))
    assert "Musisz wejść w edycję" in normalize_html(admin_page.content())
