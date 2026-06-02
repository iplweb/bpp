import pytest

from bpp.models.cache import Cache_Punktacja_Dyscypliny


@pytest.mark.django_db
def test_cache_punktacja_dyscypliny_ma_uczelnia(uczelnia, dyscyplina1):
    obj = Cache_Punktacja_Dyscypliny(
        rekord_id=[1, 1],
        dyscyplina=dyscyplina1,
        pkd=10,
        slot=1,
        uczelnia=uczelnia,
    )
    assert obj.uczelnia_id == uczelnia.pk
    assert obj.serialize()[-1] == uczelnia.pk
