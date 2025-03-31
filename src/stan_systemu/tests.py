import denorm
from django.urls import reverse


def test_IloscObiektowWDenormQueue(
    admin_app, admin_user, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
):

    url = reverse("stan_systemu:ilosc_obiektow_w_denorm_queue")
    res = admin_app.get(url)
    assert res.status_code == 200
    assert b"Przeliczenia wymaga" in res.content

    denorm.flush()
    res = admin_app.get(url)
    assert res.status_code == 200
    assert b"jest pusta" in res.content
