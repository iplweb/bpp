"""Testy self-service edycji profilu autora (Faza 2, §3.8): biogram + zdjęcie.

Edytować może wyłącznie zalogowany użytkownik z powiązanym ``user.autor`` —
i tylko własny biogram oraz zdjęcie (układ jest globalny per-Uczelnia, poza
zasięgiem autora).
"""

import json

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor

pytestmark = pytest.mark.django_db


def _user_z_autorem(django_user_model):
    autor = baker.make(Autor)
    user = django_user_model.objects.create_user(
        username="autor-user", password="x", email="a@example.com"
    )
    user.autor = autor
    user.save(update_fields=["autor"])
    return user, autor


def test_anonim_przekierowany_na_login(client):
    resp = client.get(reverse("bpp:profil-edycja"))
    assert resp.status_code == 302
    assert "login" in resp.url


def test_user_bez_autora_przekierowany_na_profil(client, django_user_model):
    user = django_user_model.objects.create_user(username="bez-autora", password="x")
    client.force_login(user)
    resp = client.get(reverse("bpp:profil-edycja"))
    assert resp.status_code == 302
    assert resp.url == reverse("bpp:profil-uzytkownika")


def test_user_z_autorem_widzi_formularz(client, django_user_model):
    user, _autor = _user_z_autorem(django_user_model)
    client.force_login(user)
    resp = client.get(reverse("bpp:profil-edycja"))
    assert resp.status_code == 200
    tresc = resp.content.decode()
    assert 'name="biogram"' in tresc
    assert 'name="biogram_format"' in tresc


def test_zapis_biogramu(client, django_user_model):
    user, autor = _user_z_autorem(django_user_model)
    client.force_login(user)
    resp = client.post(
        reverse("bpp:profil-edycja"),
        {"biogram": "Nowy biogram autora", "biogram_format": "md"},
    )
    assert resp.status_code == 302
    autor.refresh_from_db()
    assert autor.biogram == "Nowy biogram autora"


def test_podglad_renderuje_markdown_i_sanityzuje(client, django_user_model):
    user, _autor = _user_z_autorem(django_user_model)
    client.force_login(user)
    resp = client.post(
        reverse("bpp:profil-biogram-podglad"),
        {"biogram": "**Pogrubione**<script>alert(1)</script>", "biogram_format": "md"},
    )
    assert resp.status_code == 200
    dane = json.loads(resp.content)
    assert "<strong>Pogrubione</strong>" in dane["html"]
    assert "<script>" not in dane["html"]


def test_link_edycji_na_stronie_profilu(client, django_user_model):
    user, _autor = _user_z_autorem(django_user_model)
    client.force_login(user)
    resp = client.get(reverse("bpp:profil-uzytkownika"))
    assert reverse("bpp:profil-edycja") in resp.content.decode()
