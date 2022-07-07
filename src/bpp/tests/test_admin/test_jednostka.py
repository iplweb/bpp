from django.urls import reverse

from bpp.models import Uczelnia


def test_admin_struktura_JednostkaAdmin_uczelnia_jednostki_alfabetycznie(
    uczelnia: Uczelnia, admin_client
):
    uczelnia.sortuj_jednostki_alfabetycznie = True
    uczelnia.save()

    assert (
        admin_client.get(reverse("admin:bpp_jednostka_changelist")).status_code == 200
    )


def test_admin_struktura_JednostkaAdmin_uczelnia_jednostki_wg_kolejnosci(
    uczelnia: Uczelnia, admin_client
):
    uczelnia.sortuj_jednostki_alfabetycznie = False
    uczelnia.save()

    assert (
        admin_client.get(reverse("admin:bpp_jednostka_changelist")).status_code == 200
    )
