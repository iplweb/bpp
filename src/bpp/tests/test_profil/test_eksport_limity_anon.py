"""Limity startu eksportu BibTeX/RIS dla niezalogowanych użytkowników.

- limit nowych zadań na IP klienta na godzinę
  (``EKSPORT_AUTORA_LIMIT_ANON_IP_NA_GODZINE``),
- globalny limit anonimowych zadań w toku
  (``EKSPORT_AUTORA_LIMIT_ANON_W_KOLEJCE``).

Weryfikację ALTCHA mockujemy jak w ``test_eksport_captcha``.
"""

import base64
import json
import uuid
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from bpp.models import Autor, AutorEksportTask

pytestmark = pytest.mark.django_db

VERIFY_TARGET = "django_altcha.altcha.verify_solution"

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@pytest.fixture(autouse=True)
def altcha_ok(mocker):
    mocker.patch(VERIFY_TARGET, return_value=(True, None))


@pytest.fixture(autouse=True)
def locmem_cache():
    with override_settings(CACHES=LOCMEM):
        cache.clear()
        yield
        cache.clear()


@pytest.fixture
def delay(mocker):
    return mocker.patch("bpp.tasks.generuj_eksport_autora.delay")


def _payload():
    # Unikalny challenge na każde żądanie — django-altcha odrzuca ponowne
    # użycie tego samego challenge'u (zapamiętuje je w cache).
    raw = json.dumps({"challenge": uuid.uuid4().hex}).encode()
    return base64.b64encode(raw).decode()


def _post(client, autor, ip="10.0.0.1", fmt="bib"):
    return client.post(
        reverse("bpp:autor_eksport_start", args=(autor.pk, fmt)),
        {"captcha": _payload()},
        REMOTE_ADDR=ip,
    )


# --- limit na IP -----------------------------------------------------------


@override_settings(
    EKSPORT_AUTORA_LIMIT_ANON_IP_NA_GODZINE=10,
    EKSPORT_AUTORA_LIMIT_ANON_W_KOLEJCE=0,
)
def test_limit_ip_jedenasty_start_odrzucony(client, delay):
    autorzy = baker.make(Autor, _quantity=11)
    for autor in autorzy[:10]:
        assert _post(client, autor).status_code == 302
    resp = _post(client, autorzy[10])
    assert resp.status_code == 429
    assert "Przekroczono limit eksportów" in resp.content.decode()
    assert AutorEksportTask.objects.count() == 10
    assert delay.call_count == 10


@override_settings(
    EKSPORT_AUTORA_LIMIT_ANON_IP_NA_GODZINE=10,
    EKSPORT_AUTORA_LIMIT_ANON_W_KOLEJCE=0,
)
def test_limit_ip_inne_ip_przechodzi(client, delay):
    autorzy = baker.make(Autor, _quantity=11)
    for autor in autorzy[:10]:
        assert _post(client, autor, ip="10.0.0.1").status_code == 302
    assert _post(client, autorzy[10], ip="10.0.0.1").status_code == 429
    assert _post(client, autorzy[10], ip="10.0.0.2").status_code == 302


@override_settings(
    EKSPORT_AUTORA_LIMIT_ANON_IP_NA_GODZINE=2,
    EKSPORT_AUTORA_LIMIT_ANON_W_KOLEJCE=0,
)
def test_limit_ip_deduplikacja_nie_zuzywa_limitu(client, delay):
    a1, a2, a3 = baker.make(Autor, _quantity=3)
    pierwszy = _post(client, a1)
    assert pierwszy.status_code == 302
    for _ in range(5):
        resp = _post(client, a1)
        assert resp.status_code == 302
        assert resp["Location"] == pierwszy["Location"]
    assert _post(client, a2).status_code == 302
    assert _post(client, a3).status_code == 429
    assert AutorEksportTask.objects.count() == 2


@override_settings(
    EKSPORT_AUTORA_LIMIT_ANON_IP_NA_GODZINE=0,
    EKSPORT_AUTORA_LIMIT_ANON_W_KOLEJCE=0,
)
def test_limit_ip_zero_wylacza(client, delay):
    for autor in baker.make(Autor, _quantity=12):
        assert _post(client, autor).status_code == 302
    assert AutorEksportTask.objects.count() == 12


@override_settings(
    EKSPORT_AUTORA_LIMIT_ANON_IP_NA_GODZINE=1,
    EKSPORT_AUTORA_LIMIT_ANON_W_KOLEJCE=0,
)
def test_limit_ip_nie_dotyczy_zalogowanych(client, delay, normal_django_user):
    client.force_login(normal_django_user)
    for autor in baker.make(Autor, _quantity=3):
        resp = client.post(
            reverse("bpp:autor_eksport_start", args=(autor.pk, "bib")),
            REMOTE_ADDR="10.0.0.1",
        )
        assert resp.status_code == 302


# --- limit kolejki ---------------------------------------------------------


def _zadania_anonimowe(n, status="pending", **kw):
    return baker.make(
        AutorEksportTask,
        format="bib",
        status=status,
        zlecone_anonimowo=True,
        _quantity=n,
        **kw,
    )


@override_settings(
    EKSPORT_AUTORA_LIMIT_ANON_IP_NA_GODZINE=0,
    EKSPORT_AUTORA_LIMIT_ANON_W_KOLEJCE=3,
)
def test_kolejka_pelna_anonim_odrzucony(client, delay):
    _zadania_anonimowe(2, status="pending")
    _zadania_anonimowe(1, status="running")
    autor = baker.make(Autor)
    resp = _post(client, autor)
    assert resp.status_code == 503
    assert "Za dużo eksportów w toku" in resp.content.decode()
    assert not AutorEksportTask.objects.filter(autor=autor).exists()
    delay.assert_not_called()


@override_settings(
    EKSPORT_AUTORA_LIMIT_ANON_IP_NA_GODZINE=0,
    EKSPORT_AUTORA_LIMIT_ANON_W_KOLEJCE=3,
)
def test_kolejka_pelna_zalogowany_przechodzi(client, delay, normal_django_user):
    _zadania_anonimowe(3)
    client.force_login(normal_django_user)
    autor = baker.make(Autor)
    resp = client.post(reverse("bpp:autor_eksport_start", args=(autor.pk, "bib")))
    assert resp.status_code == 302
    task = AutorEksportTask.objects.get(autor=autor)
    assert task.zlecone_anonimowo is False


@override_settings(
    EKSPORT_AUTORA_LIMIT_ANON_IP_NA_GODZINE=0,
    EKSPORT_AUTORA_LIMIT_ANON_W_KOLEJCE=3,
)
def test_kolejka_zadania_zakonczone_nie_licza_sie(client, delay):
    _zadania_anonimowe(2, status="completed")
    _zadania_anonimowe(2, status="failed")
    _zadania_anonimowe(2, status="pending")
    # Zadania zalogowanych nie liczą się do limitu anonimów.
    baker.make(AutorEksportTask, format="bib", status="pending", _quantity=3)
    autor = baker.make(Autor)
    assert _post(client, autor).status_code == 302
    assert AutorEksportTask.objects.get(autor=autor).zlecone_anonimowo is True


@override_settings(
    EKSPORT_AUTORA_LIMIT_ANON_IP_NA_GODZINE=0,
    EKSPORT_AUTORA_LIMIT_ANON_W_KOLEJCE=3,
)
def test_kolejka_stare_wiszace_nie_licza_sie(client, delay):
    stare = _zadania_anonimowe(3, status="running")
    # ``created_at`` ma auto_now_add — cofamy datę przez update().
    AutorEksportTask.objects.filter(pk__in=[t.pk for t in stare]).update(
        created_at=timezone.now() - timedelta(hours=2)
    )
    autor = baker.make(Autor)
    assert _post(client, autor).status_code == 302


@override_settings(
    EKSPORT_AUTORA_LIMIT_ANON_IP_NA_GODZINE=0,
    EKSPORT_AUTORA_LIMIT_ANON_W_KOLEJCE=1,
)
def test_kolejka_pelna_deduplikacja_przechodzi(client, delay):
    autor = baker.make(Autor)
    pierwszy = _post(client, autor)
    assert pierwszy.status_code == 302
    # Kolejka pełna (1/1), ale ten sam eksport trafia do istniejącego zadania.
    drugi = _post(client, autor)
    assert drugi.status_code == 302
    assert drugi["Location"] == pierwszy["Location"]
    assert _post(client, baker.make(Autor)).status_code == 503


@override_settings(
    EKSPORT_AUTORA_LIMIT_ANON_IP_NA_GODZINE=0,
    EKSPORT_AUTORA_LIMIT_ANON_W_KOLEJCE=0,
)
def test_kolejka_zero_wylacza(client, delay):
    _zadania_anonimowe(50)
    assert _post(client, baker.make(Autor)).status_code == 302


@override_settings(
    EKSPORT_AUTORA_LIMIT_ANON_IP_NA_GODZINE=1,
    EKSPORT_AUTORA_LIMIT_ANON_W_KOLEJCE=1,
)
def test_odmowa_kolejki_nie_zuzywa_limitu_ip(client, delay):
    zajete = _zadania_anonimowe(1)
    assert _post(client, baker.make(Autor)).status_code == 503
    AutorEksportTask.objects.filter(pk=zajete[0].pk).update(status="completed")
    assert _post(client, baker.make(Autor)).status_code == 302
