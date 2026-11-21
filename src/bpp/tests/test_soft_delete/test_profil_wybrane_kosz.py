"""Wyróżnione prace autora z kosza znikają z profilu (i wracają po restore)."""

import pytest
from django.contrib.contenttypes.models import ContentType
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from bpp.models.wybrana_publikacja import WybranaPublikacjaAutora
from bpp.profil_autora_dane import _wybrane_publikacje


@pytest.mark.django_db
def test_wyrozniona_praca_z_kosza_znika_z_profilu(autor_jan_kowalski, rf):
    wc = baker.make(Wydawnictwo_Ciagle)
    WybranaPublikacjaAutora.objects.create(
        autor=autor_jan_kowalski,
        content_type=ContentType.objects.get_for_model(wc),
        object_id=wc.pk,
        kolejnosc=0,
    )
    request = rf.get("/")

    assert _wybrane_publikacje(autor_jan_kowalski, 10, request)["prace"] == [wc]

    wc.delete()
    assert _wybrane_publikacje(autor_jan_kowalski, 10, request) is None

    wc.restore()
    assert _wybrane_publikacje(autor_jan_kowalski, 10, request)["prace"] == [wc]
