"""Test Playwright: gating kafelków kroku 0 kreatora zgłoszeń.

Pokrywa scenariusz z ``2026-07-12-zglos-captcha-altcha-design.md``: kafelki
rodzaju publikacji (``.zglos-gated``) w ``step_rodzaj.html`` są ukryte
(``display:none``) dopóki widget ALTCHA nie wyemituje ``statechange`` z
``detail.state === 'verified'`` — wtedy JS dokleja klasę ``.revealed``
(SCSS: ``.zglos-gated.revealed { display:block }``). Przy
``ZGLOS_CAPTCHA_ENABLED=False`` gating w ogóle nie istnieje w DOM (kafelki
renderują się wprost, bez ``.zglos-captcha``/``.zglos-gated``/``altcha-widget``).

Dlaczego NIE ``@override_settings`` + zwykły ``channels_live_server``
----------------------------------------------------------------------
``channels_live_server`` (i jego wariant ``_per_test``) serwuje stronę z
osobnego procesu OS (``daphne.testing.DaphneProcess`` — podklasa
``multiprocessing.Process``). Na macOS domyślną metodą jest "spawn": dziecko
to świeży interpreter, który re-importuje ustawienia Django od zera — nie
dziedziczy stanu Pythona rodzica. ``@override_settings`` w procesie testowym
mutuje tylko obiekt ``django.conf.settings`` W TYM procesie; subprocess
Daphne (zwłaszcza wariant session-scoped, odpalony raz na cały worker) go
nie widzi. Zweryfikowane empirycznie: strona serwowana przez
``channels_live_server`` pod ``@override_settings(ZGLOS_CAPTCHA_ENABLED=True)``
nadal renderowała się tak, jakby captcha była OFF (``settings/test.py``
twardo ustawia ``ZGLOS_CAPTCHA_ENABLED = False`` — nie przez ``env()``, więc
nawet zmienne środowiskowe by nie pomogły).

Rozwiązanie: własna, lokalna fixture ``captcha_live_server`` — kopia
``channels_live_server_per_test`` z ``src/channels_live_server.py``, ale
z callbackiem ``setup`` który PO ``set_database_connection()`` (identyczne
DB wiring co reszta suity) dodatkowo mutuje ``settings.ZGLOS_CAPTCHA_ENABLED``
i ``settings.ALTCHA_HMAC_KEY`` BEZPOŚREDNIO W SUBPROCESIE — dokładnie tak,
jak ``set_database_connection`` robi to już dla ``settings.DATABASES``.
Widok czyta ``settings.ZGLOS_CAPTCHA_ENABLED`` "call-time" (per request, nie
przy starcie procesu — patrz komentarz w ``zglos_publikacje/views.py``
``get_form_kwargs``), więc mutacja przed ``self.server.run()`` wystarcza.

Callback ``setup_captcha_daphne`` MUSI być funkcją top-level w module BEZ
ciężkich importów Django na poziomie modułu (nie w tym pliku testowym, który
ma ``from model_bakery import baker`` / ``from bpp.models import Uczelnia``
na topie) — "spawn" pickluje callable po nazwie kwalifikowanej i odtwarza go
importując CAŁY jego moduł w dziecku, zanim ``django.setup()`` tam się
wykona. Stąd osobny, lekki moduł: ``_captcha_daphne_setup.py``
(zweryfikowane empirycznie: trzymanie tej funkcji tutaj powodowało
``AppRegistryNotReady`` w subprocesie).

Wzorce fixtur/nazw zaczerpnięte z ``test_global_search.py`` (``page``,
``channels_live_server``) oraz z ``zglos_publikacje/tests/test_zglos_captcha.py``
(nazwa URL-a ``zglos_publikacje:nowe_zgloszenie``, klucz testowy).
"""

from functools import partial

import pytest
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page

from bpp.models import Uczelnia
from integration_tests._captcha_daphne_setup import setup_captcha_daphne


def _url():
    return reverse("zglos_publikacje:nowe_zgloszenie")


@pytest.fixture
def captcha_live_server(transactional_db):
    """Per-test Daphne subprocess z ``ZGLOS_CAPTCHA_ENABLED=True``.

    Kopia ``channels_live_server_per_test`` (``src/channels_live_server.py``)
    z jedną różnicą: ``setup=setup_captcha_daphne`` zamiast
    ``set_database_connection`` — patrz docstring modułu po uzasadnienie.
    """
    from daphne.testing import DaphneProcess
    from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
    from django.core.exceptions import ImproperlyConfigured
    from django.db import connections
    from django.test.utils import modify_settings

    from channels_live_server import _ChannelsLiveServer

    for connection in connections.all():
        if connection.vendor == "sqlite" and connection.is_in_memory_db():
            raise ImproperlyConfigured(
                "ChannelsLiveServer can not be used with in-memory databases"
            )

    host = "localhost"
    modified_settings = modify_settings(ALLOWED_HOSTS={"append": host})
    modified_settings.enable()

    # Import lokalny (jak w ``channels_live_server._spawn_daphne``) — moduł
    # ``channels.testing.live`` importuje Django na czas configu ASGI.
    from channels.testing.live import make_application

    get_application = partial(make_application, static_wrapper=ASGIStaticFilesHandler)
    server_process = DaphneProcess(host, get_application, setup=setup_captcha_daphne)
    server_process.start()

    while True:
        if not server_process.ready.wait(timeout=1):
            if server_process.is_alive():
                continue
            raise RuntimeError("Server stopped") from None
        break

    port = server_process.port.value
    server = _ChannelsLiveServer(host, port)
    try:
        yield server
    finally:
        server_process.terminate()
        server_process.join()
        modified_settings.disable()


def test_kafelki_ukryte_przed_weryfikacja(captcha_live_server, page: Page):
    """Anonim, captcha ON: ``.zglos-gated`` jest ukryte, widget widoczny."""
    baker.make(Uczelnia)

    url = captcha_live_server.url + _url()
    page.goto(url)
    page.wait_for_selector("altcha-widget")

    gated = page.locator(".zglos-gated")
    assert gated.count() == 1
    # Ukryte: display:none → Playwright is_visible() zwraca False.
    assert not gated.first.is_visible()


def test_kafelki_pojawiaja_sie_po_verified(captcha_live_server, page: Page):
    """Po ``statechange:verified`` ``.zglos-gated`` dostaje ``.revealed``.

    Zamiast czekać na realny PoW w headless (``auto="onload"``) — flaky/wolne
    w CI — sterujemy stanem bezpośrednio: emitujemy ``statechange`` z
    ``detail.state='verified'`` na ``<altcha-widget>``, tak jak zrobiłby to
    prawdziwy widget po ukończeniu weryfikacji. Test weryfikuje wyłącznie
    zachowanie JS-a strony (nasłuch zdarzenia → klasa ``.revealed``), nie
    samą bibliotekę ALTCHA (tę pokrywają testy 1/3 — obecność/brak widgetu —
    i unit testy w ``test_zglos_captcha.py``).
    """
    baker.make(Uczelnia)

    url = captcha_live_server.url + _url()
    page.goto(url)
    page.wait_for_selector("altcha-widget")

    gated = page.locator(".zglos-gated")
    assert not gated.first.is_visible()

    page.eval_on_selector(
        "altcha-widget",
        "el => el.dispatchEvent(new CustomEvent('statechange',"
        " {detail: {state: 'verified'}}))",
    )

    page.wait_for_selector(".zglos-gated.revealed", timeout=5000)
    assert page.locator(".zglos-gated").first.is_visible()
    assert page.locator(".tile-card").first.is_visible()


@pytest.mark.django_db(transaction=True)
def test_kafelki_widoczne_od_razu_bez_captchy(channels_live_server, page: Page):
    """Captcha OFF (default ``settings/test.py``): kafelki widoczne od razu.

    Zwykła, session-scoped ``channels_live_server`` wystarcza — domyślne
    ``ZGLOS_CAPTCHA_ENABLED=False`` w ``settings/test.py`` to dokładnie
    scenariusz, który chcemy sprawdzić, więc nie trzeba nic wymuszać w
    subprocesie.
    """
    baker.make(Uczelnia)

    url = channels_live_server.url + _url()
    page.goto(url)
    page.wait_for_selector(".tile-card")

    assert page.locator(".tile-card").first.is_visible()
    assert page.locator(".zglos-gated").count() == 0
    assert page.locator("altcha-widget").count() == 0
