"""Formularz rankingu autorów — wartości domyślne renderowane po stronie
serwera (dawniej test Playwright, ale nie zależy od JavaScriptu)."""

import pytest
from django.urls import reverse
from django.utils import timezone

from bpp.tests.util import CURRENT_YEAR, any_autor, any_ciagle, any_jednostka


@pytest.fixture
def jednostka_raportow(
    typy_odpowiedzialnosci, jezyki, statusy_korekt, typy_kbn, charaktery_formalne
):
    """Jednostka z autorem i publikacjami z trzech ostatnich lat."""
    j = any_jednostka(nazwa="Jednostka")
    a = any_autor()

    for rok in (CURRENT_YEAR, CURRENT_YEAR - 1, CURRENT_YEAR - 2):
        any_ciagle(rok=rok).dodaj_autora(a, j)

    return j


@pytest.mark.django_db
def test_ranking_autorow_formularz_domyslny_rok(admin_client, jednostka_raportow):
    """W styczniu domyślnym rokiem jest poprzedni rok, potem bieżący."""
    res = admin_client.get(reverse("bpp:ranking_autorow_formularz"))
    assert res.status_code == 200

    val = CURRENT_YEAR - 1 if timezone.now().month < 2 else CURRENT_YEAR

    assert f'value="{val}"' in res.content.decode()
