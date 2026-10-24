"""Ochrona startu eksportu BibTeX/RIS przed botami.

- GET na adres startu NIE kolejkuje zadania — pokazuje stronę z przyciskiem
  „Generuj” (crawler idący po linkach nic nie uruchomi).
- Zadanie startuje dopiero POST-em.
- Anonim musi przejść ALTCHA (proof-of-work); zalogowany — bez captchy.
- Synchroniczne ``eksport.bib`` / ``eksport.ris`` (generowane w wątku
  requestu) są tylko dla zalogowanych.

Weryfikację PoW mockujemy jak w ``zglos_publikacje/tests/test_zglos_captcha``:
django-altcha i tak dekoduje payload (base64→JSON z kluczem ``challenge``).
"""

import base64
import json
from unittest import mock

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, AutorEksportTask

pytestmark = pytest.mark.django_db

VERIFY_TARGET = "django_altcha.altcha.verify_solution"


def _fake_payload(challenge="chal-eksport"):
    raw = json.dumps({"challenge": challenge}).encode()
    return base64.b64encode(raw).decode()


@pytest.fixture
def autor():
    return baker.make(Autor)


@pytest.fixture
def delay(mocker):
    return mocker.patch("bpp.tasks.generuj_eksport_autora.delay")


def _url(autor, fmt="bib"):
    return reverse("bpp:autor_eksport_start", args=(autor.pk, fmt))


def test_get_nie_kolejkuje_zadania(client, autor, delay):
    resp = client.get(_url(autor))
    assert resp.status_code == 200
    assert AutorEksportTask.objects.count() == 0
    delay.assert_not_called()


def test_get_anonim_widzi_altcha(client, autor, delay):
    tresc = client.get(_url(autor)).content.decode()
    assert "<altcha-widget" in tresc


def test_get_zalogowany_bez_altcha(client, autor, delay, normal_django_user):
    client.force_login(normal_django_user)
    tresc = client.get(_url(autor)).content.decode()
    assert "<altcha-widget" not in tresc
    assert "Generuj" in tresc


def test_post_anonim_bez_captchy_odrzucony(client, autor, delay):
    resp = client.post(_url(autor))
    assert resp.status_code == 200
    assert AutorEksportTask.objects.count() == 0
    delay.assert_not_called()


def test_post_anonim_z_blednym_captcha_odrzucony(client, autor, delay):
    with mock.patch(VERIFY_TARGET, return_value=(False, "zły PoW")):
        resp = client.post(_url(autor), {"captcha": _fake_payload()})
    assert resp.status_code == 200
    assert AutorEksportTask.objects.count() == 0
    delay.assert_not_called()


def test_post_anonim_z_poprawnym_captcha_startuje(client, autor, delay):
    with mock.patch(VERIFY_TARGET, return_value=(True, None)):
        resp = client.post(_url(autor), {"captcha": _fake_payload()})
    assert resp.status_code == 302
    task = AutorEksportTask.objects.get()
    assert task.autor == autor
    assert task.format == "bib"
    assert reverse("bpp:autor_eksport_status", args=(task.pk,)) in resp["Location"]
    delay.assert_called_once_with(str(task.pk))


def test_post_zalogowany_startuje_bez_captchy(client, autor, delay, normal_django_user):
    client.force_login(normal_django_user)
    resp = client.post(_url(autor, "ris"))
    assert resp.status_code == 302
    task = AutorEksportTask.objects.get()
    assert task.format == "ris"
    delay.assert_called_once_with(str(task.pk))


def test_post_deduplikuje(client, autor, delay, normal_django_user):
    client.force_login(normal_django_user)
    resp1 = client.post(_url(autor))
    resp2 = client.post(_url(autor))
    assert resp1["Location"] == resp2["Location"]
    assert AutorEksportTask.objects.count() == 1
    delay.assert_called_once()


def test_linki_eksportu_na_stronie_autora_sa_nofollow(client, autor):
    tresc = client.get(autor.get_absolute_url()).content.decode()
    for fmt in ("bib", "ris"):
        url = _url(autor, fmt)
        assert url in tresc
        poz = tresc.index(url)
        znacznik = tresc[tresc.rindex("<a", 0, poz) : tresc.index(">", poz)]
        assert 'rel="nofollow"' in znacznik


@pytest.mark.parametrize("nazwa", ["autor_eksport_bibtex", "autor_eksport_ris"])
def test_eksport_synchroniczny_wymaga_logowania(client, autor, nazwa):
    resp = client.get(reverse(f"bpp:{nazwa}", args=(autor.pk,)))
    assert resp.status_code == 302
    assert "login" in resp["Location"]


def test_anonim_przycisk_generuj_ukryty_do_weryfikacji(client, autor, delay):
    # Przycisk pokazuje JS (eksport-autora-altcha.js) po weryfikacji ALTCHA;
    # do tego czasu na stronie jest tylko powrót do autora.
    tresc = client.get(_url(autor)).content.decode()
    assert "data-czeka-na-altcha" in tresc
    assert "Powrót do strony autora" in tresc


def test_zalogowany_przycisk_generuj_od_razu(client, autor, delay, normal_django_user):
    client.force_login(normal_django_user)
    tresc = client.get(_url(autor)).content.decode()
    assert "data-czeka-na-altcha" not in tresc
