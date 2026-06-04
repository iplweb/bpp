import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_mapowanie_unikalne_per_uczelnia_charakter():
    from django.db import IntegrityError

    from dspace_api.models import Mapowanie_DSpace

    uczelnia = baker.make("bpp.Uczelnia")
    charakter = baker.make("bpp.Charakter_Formalny")
    baker.make(
        Mapowanie_DSpace,
        uczelnia=uczelnia,
        charakter_formalny=charakter,
        collection_uuid="11111111-1111-1111-1111-111111111111",
    )
    with pytest.raises(IntegrityError):
        Mapowanie_DSpace.objects.create(
            uczelnia=uczelnia,
            charakter_formalny=charakter,
            collection_uuid="22222222-2222-2222-2222-222222222222",
        )
