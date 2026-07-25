"""Rollbar musi maskować sekrety OAuth (uwaga reviewera #3).

/o/token/ i /o/revoke_token/ to widoki DOT. DOT oznacza jako wrażliwe tylko
``password`` i ``client_secret``; pyrollbar domyślnie NIE scrubuje
``refresh_token``, ``code``, ``code_verifier`` ani ``token``. Nieoczekiwany
wyjątek 500 podczas wymiany/odświeżenia/rewokacji wysłałby aktywny sekret do
Rollbara.

Test sprawdza GWARANCJĘ (sekret nie wychodzi w payloadzie), a nie sposób jej
realizacji. Wcześniejsza wersja asertowała obecność nazwy pola na liście
``scrub_fields`` — czyli implementację. Gdy ``"code"`` musiało z tej listy
zniknąć (bo zamazywało też linie kodu w tracebackach — patrz
``bpp.rollbar_config.ScrubKoduAutoryzacyjnego``), test padał, choć sekret nadal
był maskowany. Asercja na gwarancję przeżyje kolejną zmianę mechanizmu.
"""

import pytest

ATRAPA = "wartosc-do-zamaskowania-w-tescie"

POLA_WRAZLIWE = (
    "refresh_token",
    "code",
    "code_verifier",
    "token",
    "access_token",
    "client_secret",
    "authorization",
    "password",
)


@pytest.fixture
def zbuduj_payload(monkeypatch):
    """Zwraca funkcję ``data -> payload`` przepuszczony przez pełny pyrollbar."""
    import rollbar

    from bpp.rollbar_config import ustawienia_rollbara

    monkeypatch.setattr(rollbar, "_initialized", False)
    monkeypatch.setattr(rollbar, "send_payload", lambda p, t: None)

    ustawienia = ustawienia_rollbara()
    # `access_token` NIE jest tu ustawiany: `settings.ROLLBAR` wnosi go
    # z konfiguracji (w testach = None), a wysyłka i tak jest zaślepiona
    # przez podmieniony `send_payload`. Wpisanie tu atrapy tokena zapalało
    # skaner sekretów w CI — słusznie, bo wzorzec jest nieodróżnialny od
    # prawdziwego przecieku.
    ustawienia["environment"] = "test"
    ustawienia["handler"] = "blocking"
    ustawienia["suppress_reinit_warning"] = True
    rollbar.init(**ustawienia)

    return lambda data: rollbar._build_payload(data)["data"]


@pytest.mark.parametrize("pole", POLA_WRAZLIWE)
def test_rollbar_maskuje_sekrety_oauth_w_parametrach_zadania(zbuduj_payload, pole):
    """Sekret w POST (wymiana kodu na token) nie może opuścić serwera."""
    out = zbuduj_payload({"request": {"POST": {pole: ATRAPA}}})

    assert ATRAPA not in str(out["request"]["POST"][pole]), (
        f"Rollbar nie maskuje pola {pole!r} w request.POST"
    )


@pytest.mark.parametrize("pole", POLA_WRAZLIWE)
def test_rollbar_maskuje_sekrety_oauth_w_zmiennych_lokalnych(zbuduj_payload, pole):
    """django-oauth-toolkit przekazuje te sekrety jako argumenty walidatora.

    Wyjątek w ``validate_code`` / ``save_authorization_code`` wystawiłby je
    w ``frames[N].locals`` — to inna ścieżka klucza niż parametry żądania,
    a właśnie ją przeoczyła pierwsza wersja ``ScrubKoduAutoryzacyjnego``.
    """
    out = zbuduj_payload({"body": {"trace": {"frames": [{"locals": {pole: ATRAPA}}]}}})

    lokalne = out["body"]["trace"]["frames"][0]["locals"]
    assert ATRAPA not in str(lokalne[pole]), (
        f"Rollbar nie maskuje pola {pole!r} w zmiennych lokalnych ramki"
    )
