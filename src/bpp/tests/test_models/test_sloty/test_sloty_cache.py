"""
Tests for IPunktacjaCacher and cache slot invalidation.

For Wydawnictwo_Ciagle tests, see test_sloty_wydawnictwo_ciagle.py
For Wydawnictwo_Zwarte tests, see test_sloty_wydawnictwo_zwarte.py
For misc tests, see test_sloty_misc.py
"""

import pytest
from django.contrib.contenttypes.models import ContentType

from bpp.models import Cache_Punktacja_Autora, Cache_Punktacja_Dyscypliny
from bpp.models.sloty.core import IPunktacjaCacher, ISlot


def powiel_wpisy_dyscyplin_autorow(wydawnictwo, rok_z, rok_do):
    """Helper function to duplicate discipline entries for authors."""
    for wca in wydawnictwo.autorzy_set.all():
        ad = wca.autor.autor_dyscyplina_set.get(rok=rok_z)
        ad.pk = None
        ad.rok = rok_do
        ad.save()


@pytest.mark.django_db
def test_IPunktacjaCacher(
    ciagle_z_dyscyplinami,
    denorms,
    autor_jan_nowak,
    autor_jan_kowalski,
    dyscyplina1,
    dyscyplina2,
    dyscyplina3,
    rok,
):
    ciagle_z_dyscyplinami.punkty_kbn = 30
    ciagle_z_dyscyplinami.rok = 2017
    ciagle_z_dyscyplinami.save()
    powiel_wpisy_dyscyplin_autorow(ciagle_z_dyscyplinami, rok, 2017)

    denorms.flush()

    ipc = IPunktacjaCacher(ciagle_z_dyscyplinami)
    assert ipc.canAdapt()

    ipc.removeEntries()
    ipc.rebuildEntries()

    assert Cache_Punktacja_Dyscypliny.objects.count() == 2
    assert Cache_Punktacja_Autora.objects.count() == 2


@pytest.mark.django_db
def test_IPunktacjaCacher_brak_afiliacji(
    ciagle_z_dyscyplinami,
    autor_jan_nowak,
    autor_jan_kowalski,
    dyscyplina1,
    dyscyplina2,
    dyscyplina3,
):
    ciagle_z_dyscyplinami.punkty_kbn = 30
    ciagle_z_dyscyplinami.rok = 2017
    ciagle_z_dyscyplinami.save()

    ciagle_z_dyscyplinami.autorzy_set.update(afiliuje=False)

    ipc = IPunktacjaCacher(ciagle_z_dyscyplinami)
    assert ipc.canAdapt()
    ipc.removeEntries()
    ipc.rebuildEntries()

    assert Cache_Punktacja_Dyscypliny.objects.count() == 0
    assert Cache_Punktacja_Autora.objects.count() == 0


@pytest.mark.django_db
def test_cache_slotow_kasowanie_wpisow_przy_zmianie_pk_ciagle(
    ciagle_z_dyscyplinami, denorms, rok
):
    ciagle_z_dyscyplinami.punkty_kbn = 30
    ciagle_z_dyscyplinami.rok = 2017
    ciagle_z_dyscyplinami.save()

    powiel_wpisy_dyscyplin_autorow(ciagle_z_dyscyplinami, rok, 2017)

    assert ISlot(ciagle_z_dyscyplinami) is not None

    denorms.flush()

    ctype = ContentType.objects.get_for_model(ciagle_z_dyscyplinami).pk
    assert (
        Cache_Punktacja_Autora.objects.filter(
            rekord_id=[ctype, ciagle_z_dyscyplinami.pk]
        ).count()
        == 2
    )

    ciagle_z_dyscyplinami.punkty_kbn = 0
    ciagle_z_dyscyplinami.save()

    denorms.flush()
    assert (
        Cache_Punktacja_Autora.objects.filter(
            rekord_id=[ctype, ciagle_z_dyscyplinami.pk]
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_cache_slotow_kasowanie_wpisow_przy_zmianie_pk_zwarte(
    zwarte_z_dyscyplinami, denorms, rok
):
    zwarte_z_dyscyplinami.punkty_kbn = 20
    zwarte_z_dyscyplinami.rok = 2017
    zwarte_z_dyscyplinami.save()

    powiel_wpisy_dyscyplin_autorow(zwarte_z_dyscyplinami, rok, 2017)

    assert ISlot(zwarte_z_dyscyplinami) is not None

    denorms.flush()

    ctype = ContentType.objects.get_for_model(zwarte_z_dyscyplinami).pk
    assert (
        Cache_Punktacja_Autora.objects.filter(
            rekord_id=[ctype, zwarte_z_dyscyplinami.pk]
        ).count()
        == 2
    )

    zwarte_z_dyscyplinami.punkty_kbn = 0
    zwarte_z_dyscyplinami.save()

    denorms.flush()

    assert (
        Cache_Punktacja_Autora.objects.filter(
            rekord_id=[ctype, zwarte_z_dyscyplinami.pk]
        ).count()
        == 0
    )
