"""Testy edycji ustawień na stronie profilu zalogowanego użytkownika
(``profil/``) — self-service przełącznik zwijania długich list autorów."""

import pytest
from django.urls import reverse

from bpp.models.profile import ZwijanieAutorow


@pytest.mark.django_db
def test_profil_wyswietla_formularz_ustawien(client, django_user_model):
    user = django_user_model.objects.create_user(username="u1", password="p")
    client.force_login(user)

    res = client.get(reverse("bpp:profil-uzytkownika"))

    assert res.status_code == 200
    assert "zwijaj_dlugie_listy_autorow" in res.content.decode("utf-8")


@pytest.mark.django_db
def test_profil_zapisuje_preferencje_zwijania(client, django_user_model):
    user = django_user_model.objects.create_user(username="u1", password="p")
    assert user.zwijaj_dlugie_listy_autorow == ZwijanieAutorow.DOMYSLNE
    client.force_login(user)

    res = client.post(
        reverse("bpp:profil-uzytkownika"),
        {"zwijaj_dlugie_listy_autorow": ZwijanieAutorow.NIGDY.value},
        follow=True,
    )

    assert res.status_code == 200
    user.refresh_from_db()
    assert user.zwijaj_dlugie_listy_autorow == ZwijanieAutorow.NIGDY


@pytest.mark.django_db
def test_profil_wymaga_zalogowania(client):
    res = client.get(reverse("bpp:profil-uzytkownika"))
    # LoginRequiredMixin → przekierowanie na logowanie
    assert res.status_code == 302
