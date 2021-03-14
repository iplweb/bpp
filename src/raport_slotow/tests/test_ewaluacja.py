from django.urls import reverse

from bpp.models import Autor_Dyscyplina
from raport_slotow.views import ewaluacja


def test_raport_ewaluacja_no_queries(
    rekord_slotu,
    django_assert_num_queries,
    admin_client,
    rok,
    autor_jan_kowalski,
    dyscyplina1,
):
    Autor_Dyscyplina.objects.create(
        rok=rok, autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1
    )

    url = reverse(
        "raport_slotow:raport-ewaluacja",
    )

    r = ewaluacja.RaportSlotowEwaluacja()
    r.data = dict(od_roku=rok, do_roku=rok, _export="html")
    assert r.get_queryset().count() == 1

    with django_assert_num_queries(13):
        admin_client.get(
            url,
            data={
                "od_roku": 2017,
                "do_roku": 2021,
                "_export": "xlsx",
            },
        )
