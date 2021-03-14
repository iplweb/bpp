import pytest
from model_mommy import mommy

from bpp.models import Cache_Punktacja_Autora_Query, Cache_Punktacja_Dyscypliny, Rekord
from raport_slotow.models.uczelnia import RaportSlotowUczelnia


@pytest.mark.django_db
@pytest.fixture
def rekord_slotu(
    autor_jan_kowalski, jednostka, dyscyplina1, wydawnictwo_ciagle_z_autorem, rok
):
    wydawnictwo_ciagle_z_autorem.autorzy_set.update(dyscyplina_naukowa=dyscyplina1)

    rekord = Rekord.objects.get_for_model(wydawnictwo_ciagle_z_autorem)
    Cache_Punktacja_Dyscypliny.objects.create(
        rekord_id=rekord.pk,
        dyscyplina=dyscyplina1,
        pkd=50,
        slot=20,
        autorzy_z_dyscypliny=[
            autor_jan_kowalski.pk,
        ],
        zapisani_autorzy_z_dyscypliny=[
            "Foo",
        ],
    )
    return Cache_Punktacja_Autora_Query.objects.create(
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        dyscyplina=dyscyplina1,
        pkdaut=50,
        slot=20,
        rekord=rekord,
    )


@pytest.mark.django_db
@pytest.fixture
def raport_slotow_uczelnia(db):
    return mommy.make(RaportSlotowUczelnia)
