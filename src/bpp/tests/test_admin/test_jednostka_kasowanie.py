"""Testy admina: bezpieczne kasowanie pustych jednostek (spec 2026-07-07).

``JednostkaAdmin`` pozwala skasować jednostkę tylko gdy jest pusta. Niepusta
jest bramkowana przez ``get_deleted_objects`` (wpis na liście ``protected`` →
Django chowa przycisk potwierdzenia). Akcja masowa jest wszystko-albo-nic:
jedna niepusta w zaznaczeniu blokuje całą partię.
"""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, BppUser, Jednostka


@pytest.fixture
def administracja_client(client, db):
    """Zalogowany klient superusera należącego do grupy ``administracja``
    (obie przesłanki ``has_delete_permission`` spełnione)."""
    grupa, _ = Group.objects.get_or_create(name="administracja")
    user = BppUser.objects.create_superuser(
        username="kasownik", password="haslo", email="k@example.org"
    )
    user.groups.add(grupa)
    client.force_login(user)
    return client


def _delete_url(jednostka: Jednostka) -> str:
    return reverse("admin:bpp_jednostka_delete", args=(jednostka.pk,))


@pytest.mark.django_db
def test_kasowanie_pustej_jednostki_usuwa(administracja_client, jednostka: Jednostka):
    pk = jednostka.pk
    resp = administracja_client.post(_delete_url(jednostka), {"post": "yes"})

    assert resp.status_code == 302
    assert not Jednostka.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_kasowanie_niepustej_jednostki_zablokowane(
    administracja_client, jednostka: Jednostka
):
    jednostka.dodaj_autora(baker.make(Autor))
    pk = jednostka.pk

    # Próba potwierdzenia kasowania niepustej jednostki NIE usuwa jej.
    resp = administracja_client.post(_delete_url(jednostka), {"post": "yes"})

    assert Jednostka.objects.filter(pk=pk).exists()
    # Strona potwierdzenia sygnalizuje blokadę (lista ``protected``).
    assert b"nie mo\xc5\xbcna usun\xc4\x85\xc4\x87" in resp.content.lower()


@pytest.mark.django_db
def test_kasowanie_masowe_blokuje_cala_partie(
    administracja_client, jednostka: Jednostka, druga_jednostka: Jednostka
):
    # Jedna pusta (druga_jednostka), jedna niepusta (jednostka) w zaznaczeniu.
    jednostka.dodaj_autora(baker.make(Autor))
    pusta_pk, niepusta_pk = druga_jednostka.pk, jednostka.pk

    resp = administracja_client.post(
        reverse("admin:bpp_jednostka_changelist"),
        {
            "action": "delete_selected",
            "_selected_action": [pusta_pk, niepusta_pk],
            "post": "yes",
        },
    )

    # Wszystko-albo-nic: obie jednostki nadal istnieją (nawet pusta).
    assert Jednostka.objects.filter(pk=pusta_pk).exists()
    assert Jednostka.objects.filter(pk=niepusta_pk).exists()
    assert resp.status_code == 200


@pytest.mark.django_db
def test_superuser_bez_grupy_nie_skasuje(client, jednostka: Jednostka):
    # Regresja: bramka grupy `administracja` (RestrictDeletionToAdministracja-
    # GroupMixin) MUSI zostać nienaruszona — sam superuser (bez grupy) nie
    # kasuje pustej jednostki. Nowy warunek „pusta" jest DODATKOWY, nie
    # zastępuje grupowego.
    user = BppUser.objects.create_superuser(
        username="bezgrupy", password="haslo", email="b@example.org"
    )
    client.force_login(user)
    pk = jednostka.pk

    client.post(_delete_url(jednostka), {"post": "yes"})

    assert Jednostka.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_kasowanie_masowe_samych_pustych_usuwa(
    administracja_client, jednostka: Jednostka, druga_jednostka: Jednostka
):
    pk1, pk2 = jednostka.pk, druga_jednostka.pk

    administracja_client.post(
        reverse("admin:bpp_jednostka_changelist"),
        {
            "action": "delete_selected",
            "_selected_action": [pk1, pk2],
            "post": "yes",
        },
    )

    assert not Jednostka.objects.filter(pk__in=[pk1, pk2]).exists()
