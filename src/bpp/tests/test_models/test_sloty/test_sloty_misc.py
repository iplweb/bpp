"""
Miscellaneous tests for ISlot - patents, multi-center works, hidden statuses.

For Wydawnictwo_Ciagle tests, see test_sloty_wydawnictwo_ciagle.py
For Wydawnictwo_Zwarte tests, see test_sloty_wydawnictwo_zwarte.py
For cache tests, see test_sloty_cache.py
"""

import pytest

from bpp.models import Rekord, Typ_KBN, Uczelnia
from bpp.models.sloty.core import ISlot
from bpp.models.sloty.exceptions import CannotAdapt


def powiel_wpisy_dyscyplin_autorow(wydawnictwo, rok_z, rok_do):
    """Helper function to duplicate discipline entries for authors."""
    for wca in wydawnictwo.autorzy_set.all():
        ad = wca.autor.autor_dyscyplina_set.get(rok=rok_z)
        ad.pk = None
        ad.rok = rok_do
        ad.save()


@pytest.mark.django_db
def test_sloty_prace_wieloosrodkowe(zwarte_z_dyscyplinami, typy_kbn):
    zwarte_z_dyscyplinami.typ_kbn = Typ_KBN.objects.get(skrot="PW")
    zwarte_z_dyscyplinami.save()

    with pytest.raises(CannotAdapt, match="dla prac wielo"):
        ISlot(zwarte_z_dyscyplinami)


@pytest.mark.django_db
def test_ISlot_patent(patent):
    with pytest.raises(CannotAdapt):
        ISlot(patent)


@pytest.mark.parametrize("akcja", ["wszystko", None])
@pytest.mark.django_db
def test_autor_Autor_zbieraj_sloty(zwarte_z_dyscyplinami, akcja, denorms, rok):
    zwarte_z_dyscyplinami.punkty_kbn = 20
    zwarte_z_dyscyplinami.rok = 2017
    zwarte_z_dyscyplinami.save()
    powiel_wpisy_dyscyplin_autorow(zwarte_z_dyscyplinami, rok, 2017)

    denorms.flush()

    a = zwarte_z_dyscyplinami.autorzy_set.first().autor
    res = a.zbieraj_sloty(
        1, zwarte_z_dyscyplinami.rok, zwarte_z_dyscyplinami.rok, akcja=akcja
    )
    assert res == (
        10.0,
        [
            Rekord.objects.get_for_model(zwarte_z_dyscyplinami)
            .cache_punktacja_autora_query_set.first()
            .pk
        ],
        0.5,
    )


@pytest.mark.django_db
def test_ISlot_ukryty_status_nie_licz_punktow(
    zwarte_z_dyscyplinami, przed_korekta, po_korekcie, uczelnia
):
    zwarte_z_dyscyplinami.punkty_kbn = 20
    zwarte_z_dyscyplinami.rok = 2017

    zwarte_z_dyscyplinami.status_korekty = przed_korekta
    zwarte_z_dyscyplinami.save()

    Uczelnia.objects.get_default().ukryj_status_korekty_set.create(
        status_korekty=przed_korekta
    )

    with pytest.raises(CannotAdapt):
        ISlot(zwarte_z_dyscyplinami)

    zwarte_z_dyscyplinami.status_korekty = po_korekcie
    zwarte_z_dyscyplinami.save()

    ISlot(zwarte_z_dyscyplinami)
