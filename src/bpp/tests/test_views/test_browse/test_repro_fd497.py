"""FD#497 — opcja "tylko dla zespołu" na stronie rekordu działała jak "nigdy".

Szablony strony rekordu porównywały ``pokazuj_*`` tylko z ``always`` i
``logged-in``, więc przy ``staff`` pole znikało także dla zespołu.
"""

import pytest

from bpp.models.fields import OpcjaWyswietlaniaField
from bpp.tests import browse_praca_url
from bpp.tests.test_models.test_struktura.test_uczelnia import (
    clear_uczelnia_cache,
)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "attr,s",
    [
        ("pokazuj_status_korekty", "Status:"),
        ("pokazuj_praca_recenzowana", "Praca recenzowana:"),
        ("pokazuj_tabele_slotow_na_stronie_rekordu", "Punkty i sloty autorów"),
    ],
)
def test_strona_rekordu_tylko_dla_zespolu(
    uczelnia, praca_z_dyscyplina, admin_client, attr, s, django_user_model
):
    from django.test import Client

    url = browse_praca_url(praca_z_dyscyplina)

    setattr(uczelnia, attr, OpcjaWyswietlaniaField.POKAZUJ_GDY_W_ZESPOLE)
    uczelnia.save()
    clear_uczelnia_cache(uczelnia)

    anonim = Client()
    assert s not in anonim.get(url).rendered_content

    zwykly = Client()
    zwykly.force_login(
        django_user_model.objects.create_user(username="zwykly", password="x")
    )
    assert s not in zwykly.get(url).rendered_content

    assert s in admin_client.get(url).rendered_content
