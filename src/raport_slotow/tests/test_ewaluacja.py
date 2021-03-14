from django.urls import reverse


def test_raport_ewaluacja_no_queries(
    rekord_slotu, django_assert_num_queries, admin_client
):

    url = reverse(
        "raport_slotow:raport-ewaluacja",
    )
    with django_assert_num_queries(13):
        admin_client.get(
            url,
            data={
                "od_roku": 2017,
                "do_roku": 2021,
                "_export": "xlsx",
            },
        )
