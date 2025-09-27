import pytest
from django.urls.base import reverse


@pytest.fixture
def multiseek_browser(splinter_browser, live_server):
    splinter_browser.visit(live_server + reverse("multiseek:index"))
    return splinter_browser


@pytest.mark.django_db
def test_index_copernicus_schowany(multiseek_browser, uczelnia):
    uczelnia.pokazuj_index_copernicus = False
    uczelnia.save()

    multiseek_browser.reload()

    assert "Index Copernicus" not in multiseek_browser.html


@pytest.mark.django_db
def test_index_copernicus_widoczny(multiseek_browser, uczelnia):
    uczelnia.pokazuj_index_copernicus = True
    uczelnia.save()

    multiseek_browser.reload()
    assert "Index Copernicus" in multiseek_browser.html
