import pytest

from bpp.models import Cache_Punktacja_Autora_Query, Rekord


@pytest.mark.django_db
@pytest.fixture
def rekord_slotu(autor_jan_kowalski, jednostka, dyscyplina1, wydawnictwo_ciagle_z_autorem):
    rekord = Rekord.objects.get_for_model(wydawnictwo_ciagle_z_autorem)
    return Cache_Punktacja_Autora_Query.objects.create(
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        dyscyplina=dyscyplina1,
        pkdaut=50,
        slot=20,
        rekord=rekord
    )
