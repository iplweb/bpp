import pytest
from django.urls import reverse

from bpp.models import Rekord
from bpp.tests.test_models.test_sloty.conftest import zwarte_z_dyscyplinami  # noqa


@pytest.mark.django_db
def test_praca_tabela_oswiadczenia_drukuj(
    zwarte_z_dyscyplinami, admin_client, uczelnia  # noqa
):  # noqa
    uczelnia.drukuj_oswiadczenia = True
    uczelnia.save()

    res = admin_client.get(
        reverse(
            "bpp:browse_rekord",
            args=Rekord.objects.get_for_model(zwarte_z_dyscyplinami).pk,
        ),
        follow=True,
    )
    assert b"<!-- wydruk oswiadczenia -->" in res.content


@pytest.mark.django_db
def test_praca_tabela_oswiadczenia_nie_drukuj(
    zwarte_z_dyscyplinami, admin_client, uczelnia  # noqa
):  # noqa
    uczelnia.drukuj_oswiadczenia = False
    uczelnia.save()

    res = admin_client.get(
        reverse(
            "bpp:browse_rekord",
            args=Rekord.objects.get_for_model(zwarte_z_dyscyplinami).pk,
        ),
        follow=True,
    )
    assert b"<!-- wydruk oswiadczenia -->" not in res.content


@pytest.mark.django_db
def test_oswiadczenie_jedno(zwarte_z_dyscyplinami, admin_client):  # noqa
    rekord = Rekord.objects.get_for_model(zwarte_z_dyscyplinami)

    autor = rekord.autorzy_set.first()
    dyscyplina_pracy = rekord.autorzy_set.first().dyscyplina_naukowa
    url = reverse(
        "oswiadczenia:jedno-oswiadczenie",
        args=(rekord.pk[0], rekord.pk[1], autor.autor.pk, dyscyplina_pracy.pk),
    )
    res = admin_client.get(url)
    assert res.status_code == 200
    assert b"window.print" in res.content


@pytest.mark.django_db
def test_oswiadczenie_druga_dyscyplina(zwarte_z_dyscyplinami, admin_client):  # noqa
    rekord = Rekord.objects.get_for_model(zwarte_z_dyscyplinami)

    autor = rekord.autorzy_set.first()
    dyscyplina_pracy = rekord.autorzy_set.first().dyscyplina_naukowa
    url = reverse(
        "oswiadczenia:jedno-oswiadczenie-druga-dyscyplina",
        args=(rekord.pk[0], rekord.pk[1], autor.autor.pk, dyscyplina_pracy.pk),
    )
    res = admin_client.get(url)
    assert res.status_code == 200
    assert b"window.print" in res.content


@pytest.mark.django_db
def test_oswiadczenie_wiele(zwarte_z_dyscyplinami, admin_client):  # noqa
    rekord = Rekord.objects.get_for_model(zwarte_z_dyscyplinami)

    url = reverse(
        "oswiadczenia:wiele-oswiadczen",
        args=(rekord.pk[0], rekord.pk[1]),
    )
    res = admin_client.get(url)
    assert res.status_code == 200
    assert b"window.print" in res.content
