"""Repro test dla FD#323 — HTTP 500 przy dodawaniu publikacji po DOI z CrossRef.

DOI 10.1002/cncr.23558 (Wiley / Cancer) zawiera wpis ``license`` z URL-em
spoza creativecommons oraz wydawcę ("Wiley"), którego nie ma w bazie BPP.
Na ścieżce prefill (``convert_crossref_to_changeform_initial_data``)
komparatory zwracały w niektórych gałęziach ``None`` zamiast obiektu
``WynikPorownania``, co kończyło się ``AttributeError`` na
``None.rekord_po_stronie_bpp`` → HTTP 500.
"""

import pytest

from crossref_bpp.admin.helpers import convert_crossref_to_changeform_initial_data
from crossref_bpp.core import Komparator


def _message_fd323() -> dict:
    """Słownik ``message`` ukształtowany jak rekord 10.1002/cncr.23558."""
    return {
        "publisher": "Wiley",
        "issue": "2",
        "license": [
            {
                "start": {"date-parts": [[2008, 5, 9]]},
                "content-version": "vor",
                "delay-in-days": 0,
                # URL spoza creativecommons.org — BPP nie umie zmapować
                "URL": "http://onlinelibrary.wiley.com/termsAndConditions#vor",
            }
        ],
        "short-container-title": ["Cancer"],
        "container-title": ["Cancer"],
        "DOI": "10.1002/cncr.23558",
        "type": "journal-article",
        "page": "367-375",
        "title": ["Randomized comparison of cladribine"],
        "volume": "113",
        "language": "en",
        "published": {"date-parts": [[2008, 7, 8]]},
    }


@pytest.mark.django_db
def test_porownaj_license_nie_zwraca_none_dla_url_spoza_cc():
    """Wpis licencji z URL-em spoza creativecommons NIE może dać ``None``."""
    wpis = _message_fd323()["license"][0]
    wynik = Komparator.porownaj_license(wpis)
    assert wynik is not None
    # samo odczytanie nie może rzucić AttributeError
    assert wynik.rekord_po_stronie_bpp is None


@pytest.mark.django_db
def test_porownaj_license_nie_zwraca_none_bez_url():
    """Wpis licencji bez URL-a NIE może dać ``None``."""
    wynik = Komparator.porownaj_license({"delay-in-days": 0})
    assert wynik is not None
    assert wynik.rekord_po_stronie_bpp is None


@pytest.mark.django_db
def test_porownaj_publisher_nie_zwraca_none_dla_nieznanego_wydawcy():
    """Nieznany wydawca NIE może dać ``None`` (→ ``.rekord_po_stronie_bpp``)."""
    wynik = Komparator.porownaj_publisher("Wiley")
    assert wynik is not None
    assert wynik.rekord_po_stronie_bpp is None


@pytest.mark.django_db
def test_convert_fd323_nie_rzuca():
    """Prefill changeform dla rekordu FD#323 nie może kończyć się błędem."""
    ret = convert_crossref_to_changeform_initial_data(_message_fd323())
    assert ret["doi"] == "10.1002/cncr.23558"
    assert ret["rok"] == 2008
