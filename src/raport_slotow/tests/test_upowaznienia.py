from django.urls import reverse

from raport_slotow.views.upowaznienie_pbn import RaportEwaluacjaUpowaznienia

from bpp.models import Autor_Dyscyplina


def test_raport_ewaluacja_upowaznienia(
    rekord_slotu,
    admin_client,
    rok,
    autor_jan_kowalski,
    dyscyplina1,
    wydawnictwo_ciagle_z_autorem,
):

    Autor_Dyscyplina.objects.create(
        rok=rok, autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1
    )

    rekord_slotu.delete()
    wydawnictwo_ciagle_z_autorem.punkty_kbn = 500
    wydawnictwo_ciagle_z_autorem.save()

    af = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
    af.afiliuje = False
    af.save()

    url = reverse(
        "raport_slotow:raport-ewaluacja-upowaznienia",
    )

    r = RaportEwaluacjaUpowaznienia()
    r.data = dict(od_roku=rok, do_roku=rok, _export="html")
    assert r.get_queryset().count() == 1

    admin_client.get(
        url,
        data={
            "od_roku": 2017,
            "do_roku": 2021,
            "_export": "xlsx",
        },
    )
