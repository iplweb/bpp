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


def test_IloscObiektowWDenormQueue_redaktor_ma_dostep(client, db):
    from django.contrib.auth.models import Group
    from model_bakery import baker

    from bpp.const import GR_WPROWADZANIE_DANYCH

    user = baker.make("bpp.BppUser", is_staff=True, is_superuser=False)
    grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(grupa)
    client.force_login(user)

    res = client.get(reverse("stan_systemu:ilosc_obiektow_w_denorm_queue"))
    assert res.status_code == 200


def test_IloscObiektowWDenormQueue_zwykly_user_bez_dostepu(client, db):
    from model_bakery import baker

    user = baker.make("bpp.BppUser", is_staff=False, is_superuser=False)
    client.force_login(user)

    res = client.get(reverse("stan_systemu:ilosc_obiektow_w_denorm_queue"))
    assert res.status_code != 200
