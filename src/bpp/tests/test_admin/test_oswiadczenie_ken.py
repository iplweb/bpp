"""Pole „Oświadczenie KEN" w inline autorów wydawnictw — widoczność zależna
od ``settings.BPP_POKAZUJ_OSWIADCZENIE_KEN``, renderowana po stronie serwera
(dawniej test Playwright; formularz admina nie potrzebuje do tego JS)."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

MODELE = pytest.mark.parametrize(
    ("model", "url"),
    [
        (Wydawnictwo_Ciagle, "admin:bpp_wydawnictwo_ciagle_change"),
        (Wydawnictwo_Zwarte, "admin:bpp_wydawnictwo_zwarte_change"),
    ],
)


def _strona_edycji(admin_client, model, url, autor, jednostka):
    rekord = baker.make(model)
    rekord.dodaj_autora(autor, jednostka)
    res = admin_client.get(reverse(url, args=(rekord.pk,)))
    assert res.status_code == 200
    return res.content.decode()


@pytest.mark.django_db
@MODELE
def test_oswiadczenie_ken_widoczne(
    admin_client,
    settings,
    model,
    url,
    autor_jan_nowak,
    jednostka,
    charaktery_formalne,
    typy_odpowiedzialnosci,
):
    settings.BPP_POKAZUJ_OSWIADCZENIE_KEN = True

    html = _strona_edycji(admin_client, model, url, autor_jan_nowak, jednostka)

    assert 'id="id_autorzy_set-0-oswiadczenie_ken"' in html
    assert 'type="hidden" name="autorzy_set-0-oswiadczenie_ken"' not in html


@pytest.mark.django_db
@MODELE
def test_oswiadczenie_ken_niewidoczne(
    admin_client,
    settings,
    model,
    url,
    autor_jan_nowak,
    jednostka,
    charaktery_formalne,
    typy_odpowiedzialnosci,
):
    settings.BPP_POKAZUJ_OSWIADCZENIE_KEN = False

    html = _strona_edycji(admin_client, model, url, autor_jan_nowak, jednostka)

    assert 'type="hidden" name="autorzy_set-0-oswiadczenie_ken"' in html
