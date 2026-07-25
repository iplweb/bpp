"""Testy payload-handlerów Rollbara (src/bpp/rollbar_config.py)."""

import pytest
from rollbar.lib.transforms.scruburl import ScrubUrlTransform

from bpp.rollbar_config import collapse_noisy_fingerprints


def _docx_payload(host="publikacje.up.lublin.pl"):
    """Payload zbliżony do realnego DocxConversionError (chained exc)."""
    return {
        "data": {
            "custom": {"DJANGO_BPP_HOSTNAME": host},
            "body": {
                "trace_chain": [
                    {
                        "exception": {
                            "class": "DocxConversionError",
                            "message": "DOCX conversion failed using both "
                            "pandoc and html2docx",
                        }
                    },
                    {
                        "exception": {
                            "class": "RuntimeError",
                            "message": "HTML2DOCX_URL not configured",
                        }
                    },
                ]
            },
        }
    }


def test_docx_error_dostaje_staly_fingerprint_per_host():
    """DocxConversionError scala się do jednego itemu per host."""
    result = collapse_noisy_fingerprints(_docx_payload())

    assert (
        result["data"]["fingerprint"] == "DocxConversionError:publikacje.up.lublin.pl"
    )


def test_rozne_hosty_daja_rozne_fingerprinty():
    """Dwa serwery z zepsutą konwersją = dwa osobne itemy, nie jeden."""
    a = collapse_noisy_fingerprints(_docx_payload("a.example.pl"))
    b = collapse_noisy_fingerprints(_docx_payload("b.example.pl"))

    assert a["data"]["fingerprint"] != b["data"]["fingerprint"]


def test_niewymieniony_wyjatek_bez_fingerprintu():
    """Wyjątki spoza allowlisty zachowują domyślne grupowanie Rollbara."""
    payload = {
        "data": {
            "custom": {"DJANGO_BPP_HOSTNAME": "x.pl"},
            "body": {
                "trace_chain": [{"exception": {"class": "Http404", "message": "..."}}]
            },
        }
    }

    result = collapse_noisy_fingerprints(payload)

    assert "fingerprint" not in result["data"]


def test_brak_hosta_daje_unknown():
    """Bez DJANGO_BPP_HOSTNAME fingerprint degraduje do :unknown."""
    payload = {
        "data": {
            "body": {
                "trace_chain": [
                    {
                        "exception": {
                            "class": "DocxConversionError",
                            "message": "...",
                        }
                    }
                ]
            }
        }
    }

    result = collapse_noisy_fingerprints(payload)

    assert result["data"]["fingerprint"] == "DocxConversionError:unknown"


def test_payload_bez_body_nie_wybucha():
    """Payload bez trace/trace_chain przechodzi bez zmian."""
    payload = {"data": {"custom": {"DJANGO_BPP_HOSTNAME": "x.pl"}}}

    result = collapse_noisy_fingerprints(payload)

    assert "fingerprint" not in result["data"]


# --- Scrub pola `code`: sekret OAuth TAK, linia kodu w tracebacku NIE -------
#
# UWAGA METODOLOGICZNA: te testy jadą PRAWDZIWYM łańcuchem transformów
# pyrollbara (`rollbar.init` + `rollbar._build_payload`), a nie jego
# rekonstrukcją. Wcześniejsza wersja składała listę transformów ręcznie
# i przez to POMIJAŁA `ScrubUrlTransform` — a właśnie tam siedział najgroźniejszy
# wyciek (`?code=` w URL-u). Testy świeciły na zielono przy dziurawym kodzie.


@pytest.fixture
def zbuduj_payload(monkeypatch):
    """Zwraca funkcję ``data -> payload`` przepuszczony przez pełny pyrollbar."""
    import rollbar

    from bpp.rollbar_config import ustawienia_rollbara

    monkeypatch.setattr(rollbar, "_initialized", False)
    monkeypatch.setattr(rollbar, "send_payload", lambda p, t: None)

    ustawienia = ustawienia_rollbara()
    ustawienia["access_token"] = "atrapa"
    ustawienia["environment"] = "test"
    ustawienia["handler"] = "blocking"
    ustawienia["suppress_reinit_warning"] = True
    rollbar.init(**ustawienia)

    return lambda data: rollbar._build_payload(data)["data"]


SEKRET = "wartosc-ktora-ma-zniknac-z-payloadu"
LINIA_KODU = "autor_str = str(self.autor) if self.autor_id else '???'"


def test_linia_kodu_w_tracebacku_nie_jest_zamazywana(zbuduj_payload):
    """Regresja: całe tracebacki w Rollbarze miały `code: "****"`.

    ``ROLLBAR_SCRUB_FIELDS`` zawierało ``"code"`` (dla parametru OAuth), a
    ``ScrubRedactTransform`` dopasowuje ścieżkę klucza po SUFIKSIE — więc
    trafiało też w ``body.trace.frames[*].code``, czyli linie kodu źródłowego.
    """
    out = zbuduj_payload(
        {"body": {"trace": {"frames": [{"filename": "a.py", "code": LINIA_KODU}]}}}
    )

    assert out["body"]["trace"]["frames"][0]["code"] == LINIA_KODU


def test_linia_kodu_w_trace_chain_tez_nie_jest_zamazywana(zbuduj_payload):
    """Wyjątki łańcuchowe mają inną ścieżkę klucza — też musi być pokryta."""
    out = zbuduj_payload(
        {
            "body": {
                "trace_chain": [{"frames": [{"filename": "a.py", "code": LINIA_KODU}]}]
            }
        }
    )

    assert out["body"]["trace_chain"][0]["frames"][0]["code"] == LINIA_KODU


@pytest.mark.parametrize(
    "opis,data,sciezka",
    [
        (
            "POST /o/token/",
            {"request": {"POST": {"code": SEKRET}}},
            ("request", "POST", "code"),
        ),
        (
            "GET /orcid/callback/",
            {"request": {"GET": {"code": SEKRET}}},
            ("request", "GET", "code"),
        ),
        (
            "inna wielkosc liter",
            {"request": {"POST": {"Code": SEKRET}}},
            ("request", "POST", "Code"),
        ),
        (
            "kolizja klucza `frames` poza tracebackiem",
            {"request": {"POST": {"frames": {"code": SEKRET}}}},
            ("request", "POST", "frames", "code"),
        ),
        (
            "zmienna lokalna ramki (django-oauth-toolkit: validate_code)",
            {"body": {"trace": {"frames": [{"locals": {"code": SEKRET}}]}}},
            ("body", "trace", "frames", 0, "locals", "code"),
        ),
        (
            "argument nazwany ramki",
            {"body": {"trace": {"frames": [{"kwargs": {"code": SEKRET}}]}}},
            ("body", "trace", "frames", 0, "kwargs", "code"),
        ),
    ],
)
def test_kod_autoryzacyjny_jest_zamazywany(zbuduj_payload, opis, data, sciezka):
    """Druga strona kontraktu — bez niej poprawka byłaby regresją bezpieczeństwa."""
    out = zbuduj_payload(data)

    biezacy = out
    for element in sciezka:
        biezacy = biezacy[element]

    assert SEKRET not in str(biezacy), f"WYCIEK sekretu: {opis}"


@pytest.mark.parametrize(
    "opis,data,sciezka",
    [
        (
            "request.url",
            {
                "request": {
                    "url": f"https://bpp.example.pl/orcid/callback/?code={SEKRET}"
                }
            },
            ("request", "url"),
        ),
        (
            "naglowek Referer",
            {
                "request": {
                    "headers": {"Referer": f"https://bpp.example.pl/cb?code={SEKRET}"}
                }
            },
            ("request", "headers", "Referer"),
        ),
        (
            "URL w zmiennej lokalnej ramki",
            {
                "body": {
                    "trace": {
                        "frames": [{"locals": {"url": f"https://x/cb?code={SEKRET}"}}]
                    }
                }
            },
            ("body", "trace", "frames", 0, "locals", "url"),
        ),
    ],
)
def test_kod_autoryzacyjny_w_URL_tez_jest_zamazywany(
    zbuduj_payload, opis, data, sciezka
):
    """Najgroźniejszy wyciek, jaki wyszedł w self-review.

    Wbudowany ``ScrubUrlTransform`` czyści parametry URL na podstawie
    ``scrub_fields`` — zdjęcie stamtąd ``"code"`` rozbroiłoby go dla tego
    parametru. ``/orcid/callback/`` dostaje kod autoryzacyjny w query stringu,
    a pyrollbar zapisuje pełny ``request.build_absolute_uri()``.
    """
    out = zbuduj_payload(data)

    biezacy = out
    for element in sciezka:
        biezacy = biezacy[element]

    assert SEKRET not in str(biezacy), f"WYCIEK sekretu w URL: {opis}"


def test_pozostale_pola_wrazliwe_nadal_zamazywane_takze_w_ramkach(zbuduj_payload):
    """`password` w zmiennych lokalnych ramki MUSI zniknąć — inaczej niż `code`."""
    out = zbuduj_payload(
        {"body": {"trace": {"frames": [{"locals": {"password": "tajne123"}}]}}}
    )

    assert "tajne123" not in str(out["body"]["trace"]["frames"][0]["locals"])


def test_configure_rollbar_przekazuje_nasze_transformy_do_inicjalizacji(mocker):
    """Sam transform nic nie da, jeśli nie trafi do ``rollbar.init``.

    Kolejność ma znaczenie: ``rollbar.init`` buduje łańcuch transformów tylko
    przy PIERWSZYM wywołaniu. ``configure_rollbar`` biegnie z
    ``AppConfig.ready()``, czyli przed middlewarem django-rollbar.
    """
    import bpp.rollbar_config as rc

    init = mocker.patch("bpp.rollbar_config.rollbar.init")
    mocker.patch("bpp.rollbar_config.rollbar.events.add_payload_handler")
    mocker.patch.object(rc, "_initialized", False)

    rc.configure_rollbar()

    transformy = init.call_args.kwargs["custom_transforms"]
    assert any(isinstance(t, rc.ScrubKoduAutoryzacyjnego) for t in transformy)
    assert any(isinstance(t, ScrubUrlTransform) for t in transformy)
