"""Testy integracji ALTCHA (proof-of-work CAPTCHA) + e-mail read-only.

Pokrywa sekcje B/C/D/F specyfikacji
``2026-07-12-zglos-captcha-altcha-design.md``:

- bramka anon-only na kroku 0 kreatora (pole ``captcha`` powstaje tylko dla
  anonima przy ``ZGLOS_CAPTCHA_ENABLED=True``),
- marker ``captcha_ok`` w ``storage.extra_data`` (1 PoW = 1 przebieg wizardu:
  awans + brak re-solve przy rewalidacji w ``render_done``, reset na GET),
- replay-protection na poziomie pola/cache (``LocMemCache`` — bo ``test.py`` ma
  ``DummyCache`` = no-op),
- system-check ``zglos_publikacje.W001`` (placeholder klucza + captcha ON),
- hint „zaloguj się" (F1) oraz serwerowe wymuszenie e-maila konta (F2).

Gotcha mockowania (spec D): po zamockowanym ``verify_solution`` django-altcha
i tak odpala ``replay_attack_protection`` → ``base64decode+json`` na payloadzie,
wymaga klucza ``"challenge"``. Dlatego fałszywy payload to
``base64(json({"challenge": ...}))`` — patrz ``_fake_payload``.
"""

import base64
import json
from unittest import mock

import pytest
from django.conf import settings as dj_settings
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.urls import reverse
from django_altcha import AltchaField
from model_bakery import baker

from bpp.models import BppUser
from zglos_publikacje.checks import W001_ID, captcha_key_placeholder_check
from zglos_publikacje.forms import Zgloszenie_Publikacji_DaneForm
from zglos_publikacje.models import Zgloszenie_Publikacji

# Cel patcha weryfikatora: `import altcha` w django_altcha/__init__.py sprawia,
# że `django_altcha.altcha` JEST modułem `altcha`; patchujemy jego atrybut
# `verify_solution`, a django-altcha woła go przez lookup call-time.
VERIFY_TARGET = "django_altcha.altcha.verify_solution"

LOCMEM_CACHE = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


def _url():
    return reverse("zglos_publikacje:nowe_zgloszenie")


def _fake_payload(challenge="chal-domyslny"):
    """Payload ALTCHA akceptowalny przez `replay_attack_protection`.

    Sama weryfikacja PoW jest mockowana, ale django-altcha bezwarunkowo
    dekoduje payload (base64→json) i czyta klucz ``challenge`` — musi więc
    być poprawnym base64(JSON) z tym kluczem.
    """
    raw = json.dumps({"challenge": challenge}).encode()
    return base64.b64encode(raw).decode()


def _verify_ok():
    """Kontekst-manager mockujący weryfikator na (True, None) + licznik."""
    return mock.patch(VERIFY_TARGET, return_value=(True, None))


# ---------------------------------------------------------------------------
# Test 1: anonim, krok 0 → forma MA pole `captcha` (renderuje <altcha-widget>).
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@override_settings(ZGLOS_CAPTCHA_ENABLED=True)
def test_anonim_krok0_ma_pole_captcha(webtest_app, uczelnia):
    page = webtest_app.get(_url())
    assert b"<altcha-widget" in page.content
    assert "0-captcha" in page.forms[0].fields


# ---------------------------------------------------------------------------
# Test 2: zalogowany, krok 0 → forma NIE ma pola `captcha` (bramka anon-only).
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@override_settings(ZGLOS_CAPTCHA_ENABLED=True)
def test_zalogowany_krok0_bez_pola_captcha(webtest_app, uczelnia):
    user = baker.make(BppUser)
    webtest_app.set_user(user)
    page = webtest_app.get(_url())
    assert b"<altcha-widget" not in page.content
    # Zalogowany → forms[0] to nav-form wylogowania; wizard-form po id.
    assert "0-captcha" not in page.forms["form-container"].fields


# ---------------------------------------------------------------------------
# Test 3a: anonim, brak payloadu → krok 0 nieważny, brak awansu.
#   Re-render kroku 0 wciąż zawiera <altcha-widget> = marker extra_data
#   NIE został ustawiony (inaczej pole by zniknęło).
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@override_settings(ZGLOS_CAPTCHA_ENABLED=True)
def test_anonim_brak_payloadu_krok0_niewazny(webtest_app, uczelnia):
    page = webtest_app.get(_url())
    form = page.forms[0]
    form["0-rodzaj"] = "ARTYKUL"
    # `0-captcha` pozostaje puste → AltchaField.required wywala walidację.
    resp = form.submit()
    assert resp.status_code == 200
    assert b"1-forma_dostepu" not in resp.content  # brak awansu na krok 1
    # Marker nieustawiony → pole captcha nadal obecne przy re-renderze.
    assert b"<altcha-widget" in resp.content


# ---------------------------------------------------------------------------
# Test 3b: anonim, ZŁE rozwiązanie (mock verify → (False, ...)) → krok 0
#   nieważny mimo obecnego payloadu.
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@override_settings(ZGLOS_CAPTCHA_ENABLED=True)
def test_anonim_zle_rozwiazanie_krok0_niewazny(webtest_app, uczelnia):
    page = webtest_app.get(_url())
    form = page.forms[0]
    form["0-rodzaj"] = "ARTYKUL"
    form["0-captcha"] = _fake_payload("zle")
    with mock.patch(VERIFY_TARGET, return_value=(False, "bad")) as m:
        resp = form.submit()
    assert m.call_count == 1  # weryfikator został wywołany
    assert resp.status_code == 200
    assert b"1-forma_dostepu" not in resp.content
    assert b"<altcha-widget" in resp.content


# ---------------------------------------------------------------------------
# Test 4: anonim, POPRAWNE rozwiązanie → awans na krok 1; marker `captcha_ok`
#   dowiedziony behawioralnie — cofnięcie na krok 0 (wizard_goto_step) w tej
#   samej sesji NIE pokazuje już widgetu (captcha_wymagany=False, bo marker set).
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@override_settings(ZGLOS_CAPTCHA_ENABLED=True)
def test_anonim_poprawne_rozwiazanie_awans_i_marker(webtest_app, uczelnia):
    page = webtest_app.get(_url())
    form = page.forms[0]
    form["0-rodzaj"] = "ARTYKUL"
    form["0-captcha"] = _fake_payload("ok-4")
    with _verify_ok():
        page1 = form.submit()
    # Awans na krok 1.
    assert b"1-forma_dostepu" in page1.content
    assert b"<altcha-widget" not in page1.content

    # Cofnij na krok 0 — marker set → pole captcha znika (dowód extra_data OK).
    fields = list(page1.forms[0].submit_fields())
    fields.append(("wizard_goto_step", "0"))
    back = webtest_app.post(_url(), params=fields)
    assert back.status_code == 200
    assert b"<altcha-widget" not in back.content


# ---------------------------------------------------------------------------
# Test 4b: GET-restart (regresja HIGH 1). Rozwiąż krok 0, potem GET na URL
#   wizardu (storage.reset zeruje marker) → krok 0 znów MA pole captcha.
#   Dowodzi: jeden PoW NIE odblokowuje kolejnego przebiegu w tej samej sesji.
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@override_settings(ZGLOS_CAPTCHA_ENABLED=True)
def test_get_restart_przywraca_pole_captcha(webtest_app, uczelnia):
    page = webtest_app.get(_url())
    form = page.forms[0]
    form["0-rodzaj"] = "ARTYKUL"
    form["0-captcha"] = _fake_payload("ok-4b")
    with _verify_ok():
        page1 = form.submit()
    assert b"1-forma_dostepu" in page1.content  # marker set, jesteśmy na kroku 1

    # GET restartuje kreator (storage.reset) → marker wyzerowany.
    restart = webtest_app.get(_url())
    assert b"<altcha-widget" in restart.content
    assert "0-captcha" in restart.forms[0].fields


# ---------------------------------------------------------------------------
# Test 5: pełny przebieg do done() → weryfikator wołany DOKŁADNIE RAZ.
#   Non-tautologiczny dowód markera: bez niego rewalidacja wszystkich kroków w
#   render_done wywołałaby verify_solution po raz drugi. Ścieżka POZOSTALE +
#   OTWARTY omija krok 4 (opłaty; wymagaj_oplatach_inne=False) i pole plików.
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@override_settings(ZGLOS_CAPTCHA_ENABLED=True)
def test_pelny_przebieg_weryfikator_wolany_raz(
    webtest_app,
    uczelnia,
    typy_odpowiedzialnosci,
    autor_jan_kowalski,
    aktualna_jednostka,
):
    with _verify_ok() as m:
        page = webtest_app.get(_url())
        form = page.forms[0]
        form["0-rodzaj"] = "POZOSTALE"
        form["0-captcha"] = _fake_payload("ok-5")
        page1 = form.submit()  # → krok 1

        page1.forms[0]["1-forma_dostepu"] = "OTWARTY"
        page2 = page1.forms[0].submit()  # → krok 2

        f2 = page2.forms[0]
        f2["2-tytul_oryginalny"] = "Testowa publikacja"
        f2["2-rok"] = "2020"
        if "2-email" in f2.fields:
            f2["2-email"] = "zglaszajacy@test.pl"
        if "2-strona_www" in f2.fields:
            f2["2-strona_www"] = "https://example.com/"
        if "2-zgoda_na_publikacje_pelnego_tekstu" in f2.fields:
            f2["2-zgoda_na_publikacje_pelnego_tekstu"] = "True"
        page3 = f2.submit()  # → krok 3

        f3 = page3.forms[0]
        f3["3-0-autor"].force_value(autor_jan_kowalski.pk)
        f3["3-0-jednostka"].force_value(aktualna_jednostka.pk)
        resp = f3.submit()  # → done()

    assert resp.status_code == 200
    assert Zgloszenie_Publikacji.objects.count() == 1
    # Marker działa: rewalidacja kroku 0 w render_done rekonstruuje formę BEZ
    # pola captcha, więc weryfikator NIE jest wołany po raz drugi.
    assert m.call_count == 1


# ---------------------------------------------------------------------------
# Test 6: replay-protection na poziomie pola + LocMemCache. To samo rozwiązanie
#   w dwóch niezależnych AltchaField → drugie odrzucone jako „already used".
# ---------------------------------------------------------------------------
@override_settings(CACHES=LOCMEM_CACHE)
def test_replay_odrzucony_na_locmem_cache():
    from django.core.cache import caches

    caches["default"].clear()  # LocMem współdzieli store per-nazwa między testami
    payload = _fake_payload("replay-6")

    with _verify_ok():
        AltchaField().clean(payload)  # 1. użycie — mark_challenge_used
        with pytest.raises(ValidationError):
            AltchaField().clean(payload)  # 2. użycie — replay → ValidationError


# ---------------------------------------------------------------------------
# Test 7: ZGLOS_CAPTCHA_ENABLED=False (default test.py) → anonim krok 0 NIE ma
#   pola captcha (dowód: dotychczasowa suita nie jest ruszona).
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_captcha_off_anonim_bez_pola(webtest_app, uczelnia):
    assert dj_settings.ZGLOS_CAPTCHA_ENABLED is False
    page = webtest_app.get(_url())
    assert b"<altcha-widget" not in page.content
    assert "0-captcha" not in page.forms[0].fields


# ---------------------------------------------------------------------------
# Test 8: system-check zglos_publikacje.W001.
#   ON + placeholder → 1 Warning; ON + realny klucz → []; OFF + placeholder → [].
# ---------------------------------------------------------------------------
def test_system_check_placeholder():
    sentinel = dj_settings.ALTCHA_HMAC_KEY_UNSET

    # ON + placeholder → dokładnie jeden Warning W001.
    with override_settings(ZGLOS_CAPTCHA_ENABLED=True, ALTCHA_HMAC_KEY=sentinel):
        warnings = captcha_key_placeholder_check(None)
        assert len(warnings) == 1
        assert warnings[0].id == W001_ID

    # ON + realny klucz → brak ostrzeżenia.
    with override_settings(
        ZGLOS_CAPTCHA_ENABLED=True, ALTCHA_HMAC_KEY="prawdziwy-losowy-klucz-hex"
    ):
        assert captcha_key_placeholder_check(None) == []

    # OFF + placeholder → brak ostrzeżenia (check no-op gdy captcha wyłączona).
    with override_settings(ZGLOS_CAPTCHA_ENABLED=False, ALTCHA_HMAC_KEY=sentinel):
        assert captcha_key_placeholder_check(None) == []


# ---------------------------------------------------------------------------
# Test 9: F1 hint „zaloguj się".
#   anonim + ON → HTML kroku 0 ma hint + widget; zalogowany → brak obu.
# ---------------------------------------------------------------------------
HINT_MARKER = "aby pominąć tę weryfikację".encode()


@pytest.mark.django_db
@override_settings(ZGLOS_CAPTCHA_ENABLED=True)
def test_hint_zaloguj_sie_anonim(webtest_app, uczelnia):
    page = webtest_app.get(_url())
    assert b"<altcha-widget" in page.content
    assert HINT_MARKER in page.content
    # Link prowadzi na stronę logowania.
    assert reverse("login_form").encode() in page.content


@pytest.mark.django_db
@override_settings(ZGLOS_CAPTCHA_ENABLED=True)
def test_hint_zaloguj_sie_brak_dla_zalogowanego(webtest_app, uczelnia):
    user = baker.make(BppUser)
    webtest_app.set_user(user)
    page = webtest_app.get(_url())
    assert b"<altcha-widget" not in page.content
    assert HINT_MARKER not in page.content


# ---------------------------------------------------------------------------
# Test 10: F2 e-mail read-only.
# ---------------------------------------------------------------------------
def _dane_form(email_zablokowany, uczelnia, initial=None):
    return Zgloszenie_Publikacji_DaneForm(
        rodzaj="POZOSTALE",
        forma_dostepu="OTWARTY",
        email_zablokowany=email_zablokowany,
        uczelnia=uczelnia,
        initial=initial or {},
    )


@pytest.mark.django_db
def test_email_disabled_gdy_zablokowany(uczelnia):
    form = _dane_form(True, uczelnia, initial={"email": "konto@real.pl"})
    assert form.fields["email"].disabled is True


@pytest.mark.django_db
def test_email_edytowalny_gdy_niezablokowany(uczelnia):
    # Anonim / zalogowany bez e-maila → pole edytowalne.
    form = _dane_form(False, uczelnia)
    assert not form.fields["email"].disabled


@pytest.mark.django_db
def test_email_wymuszony_serwerowo_dla_zalogowanego(
    webtest_app,
    uczelnia,
    typy_odpowiedzialnosci,
    autor_jan_kowalski,
    aktualna_jednostka,
):
    """POST z podmienionym e-mailem → zapisany e-mail KONTA (disabled → initial).

    `disabled=True` sprawia, że Django ignoruje wartość z POST i bierze
    `initial` (e-mail konta), więc atak „podmień 2-email" nie przechodzi.
    """
    user = baker.make(BppUser, email="konto@real.pl")
    webtest_app.set_user(user)

    # Zalogowany → w nawigacji jest form wylogowania; wizard-form po id.
    page = webtest_app.get(_url())  # zalogowany → brak captcha
    page.forms["form-container"]["0-rodzaj"] = "POZOSTALE"
    page1 = page.forms["form-container"].submit()  # → krok 1

    page1.forms["form-container"]["1-forma_dostepu"] = "OTWARTY"
    page2 = page1.forms["form-container"].submit()  # → krok 2

    f2 = page2.forms["form-container"]
    f2["2-tytul_oryginalny"] = "Testowa publikacja"
    f2["2-rok"] = "2020"
    if "2-strona_www" in f2.fields:
        f2["2-strona_www"] = "https://example.com/"
    if "2-zgoda_na_publikacje_pelnego_tekstu" in f2.fields:
        f2["2-zgoda_na_publikacje_pelnego_tekstu"] = "True"
    # Pole `2-email` jest disabled → webtest nie wyśle go z formularza.
    # Wstrzykujemy podmieniony e-mail ręcznie, symulując złośliwy POST.
    fields = list(f2.submit_fields())
    fields.append(("2-email", "atak@evil.pl"))
    page3 = webtest_app.post(_url(), params=fields)  # → krok 3

    f3 = page3.forms["form-container"]
    f3["3-0-autor"].force_value(autor_jan_kowalski.pk)
    f3["3-0-jednostka"].force_value(aktualna_jednostka.pk)
    f3.submit()  # → done()

    zp = Zgloszenie_Publikacji.objects.order_by("-pk").first()
    assert zp is not None
    assert zp.email == "konto@real.pl"  # NIE atak@evil.pl
