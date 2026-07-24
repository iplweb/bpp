"""Testy payload-handlerów Rollbara (src/bpp/rollbar_config.py)."""

from bpp.rollbar_config import (
    ScrubKoduAutoryzacyjnego,
    collapse_noisy_fingerprints,
    ustawienia_rollbara,
)


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


def _przepusc_przez_scrub(fragment, klucz_startowy):
    """Uruchamia łańcuch scrubujący dokładnie tak, jak robi to pyrollbar.

    ``rollbar._build_payload`` woła ``_transform`` osobno dla każdego klucza
    najwyższego poziomu, zasiewając ścieżkę jako ``(klucz,)`` — dlatego ramki
    stosu widzi jako ``("body", "trace", "frames", 0, "code")``, a parametry
    żądania jako ``("request", "POST", "code")``.
    """
    from rollbar.lib import transforms
    from rollbar.lib.transforms.scrub_redact import ScrubRedactTransform

    from django_bpp.settings.base import ROLLBAR_SCRUB_FIELDS

    lancuch = [
        ScrubRedactTransform(
            suffixes=[(pole,) for pole in ROLLBAR_SCRUB_FIELDS], redact_char="*"
        )
    ] + list(ustawienia_rollbara()["custom_transforms"])

    return transforms.transform(fragment, lancuch, key=(klucz_startowy,))


def test_linia_kodu_w_tracebacku_nie_jest_zamazywana():
    """Regresja: od pyrollbara 1.4.0 KAŻDY traceback miał `code: "****"`.

    ``ROLLBAR_SCRUB_FIELDS`` zawierało ``"code"`` (dla parametru OAuth), a
    ``ScrubRedactTransform`` dopasowuje ścieżkę klucza po SUFIKSIE — więc
    trafiało też w ``body.trace.frames[*].code``, czyli linie kodu źródłowego.
    Efekt: każde śledztwo w Rollbarze zaczynało się bez kodu.
    """
    body = {
        "trace": {
            "frames": [
                {
                    "filename": "/app/src/bpp/models/autor.py",
                    "lineno": 690,
                    "code": "autor_str = str(self.autor) if self.autor_id else '???'",
                }
            ]
        }
    }

    out = _przepusc_przez_scrub(body, "body")

    assert out["trace"]["frames"][0]["code"] == (
        "autor_str = str(self.autor) if self.autor_id else '???'"
    )


def test_kod_autoryzacyjny_oauth_w_zadaniu_nadal_jest_zamazywany():
    """Druga strona kontraktu — bez niej poprawka byłaby regresją bezpieczeństwa.

    ``/o/token/`` przyjmuje ``code`` (kod autoryzacyjny OAuth) w POST. Gdyby
    ten endpoint zwrócił 500, Rollbar wysłałby aktywny kod w czystej postaci.
    """
    request = {
        "POST": {
            "code": "AKTYWNY_KOD_AUTORYZACYJNY",
            "code_verifier": "TAJNY_VERIFIER",
            "grant_type": "authorization_code",
        }
    }

    out = _przepusc_przez_scrub(request, "request")

    assert "AKTYWNY_KOD" not in out["POST"]["code"]
    assert "TAJNY_VERIFIER" not in out["POST"]["code_verifier"]
    # Wartość niewrażliwa zostaje nietknięta — scrub nie może być zbyt szeroki.
    assert out["POST"]["grant_type"] == "authorization_code"


def test_pozostale_pola_wrazliwe_nadal_zamazywane_takze_w_ramkach():
    """`password` w zmiennych lokalnych ramki MUSI zniknąć — inaczej niż `code`."""
    body = {
        "trace": {"frames": [{"filename": "a.py", "locals": {"password": "tajne123"}}]}
    }

    out = _przepusc_przez_scrub(body, "body")

    assert out["trace"]["frames"][0]["locals"]["password"] != "tajne123"


def test_configure_rollbar_przekazuje_nasz_transform_do_inicjalizacji(mocker):
    """Sam transform nic nie da, jeśli nie trafi do ``rollbar.init``.

    Kolejność ma znaczenie: ``rollbar.init`` buduje łańcuch transformów tylko
    przy PIERWSZYM wywołaniu. ``configure_rollbar`` biegnie z
    ``AppConfig.ready()``, czyli przed middlewarem django-rollbar — gdyby było
    odwrotnie, nasz transform nigdy by nie wszedł.
    """
    import bpp.rollbar_config as rc

    init = mocker.patch("bpp.rollbar_config.rollbar.init")
    mocker.patch("bpp.rollbar_config.rollbar.events.add_payload_handler")
    mocker.patch.object(rc, "_initialized", False)

    rc.configure_rollbar()

    assert init.called
    transformy = init.call_args.kwargs["custom_transforms"]
    assert any(isinstance(t, ScrubKoduAutoryzacyjnego) for t in transformy)
