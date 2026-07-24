"""Testy payload-handlerów Rollbara (src/bpp/rollbar_config.py)."""

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
