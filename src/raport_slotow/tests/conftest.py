import pytest
from model_bakery import baker

from raport_slotow.models.uczelnia import RaportSlotowUczelnia

from bpp.models import Cache_Punktacja_Autora_Query, Cache_Punktacja_Dyscypliny, Rekord


def _rekord_slotu_maker(autor, jednostka, dyscyplina, wydawnictwo_ciagle, rok):
    wydawnictwo_ciagle.autorzy_set.update(dyscyplina_naukowa=dyscyplina)

    rekord = Rekord.objects.get_for_model(wydawnictwo_ciagle)
    Cache_Punktacja_Dyscypliny.objects.create(
        rekord_id=rekord.pk,
        dyscyplina=dyscyplina,
        pkd=50,
        slot=20,
        autorzy_z_dyscypliny=[
            autor.pk,
        ],
        zapisani_autorzy_z_dyscypliny=[
            "Foo",
        ],
    )
    return Cache_Punktacja_Autora_Query.objects.create(
        autor=autor,
        jednostka=jednostka,
        dyscyplina=dyscyplina,
        pkdaut=50,
        slot=20,
        rekord=rekord,
    )


@pytest.mark.django_db
@pytest.fixture
def rekord_slotu(
    autor_jan_kowalski, jednostka, dyscyplina1, wydawnictwo_ciagle_z_autorem, rok
):
    return _rekord_slotu_maker(
        autor_jan_kowalski, jednostka, dyscyplina1, wydawnictwo_ciagle_z_autorem, rok
    )


@pytest.mark.django_db
@pytest.fixture
def raport_slotow_uczelnia(db):
    return baker.make(RaportSlotowUczelnia)
