"""Testy zapisu osób z API instytucji PBN (`_zapisz_osobe_z_instytucji`).

Kontekst: ``OsobaZInstytucji`` ma DWA klucze unikalne — ``personId``
(OneToOne na ``Scientist``) oraz ``polonUuid``. PBN potrafi wystawić tę samą
fizyczną osobę pod NOWYM ``personId``, zachowując jej ``polonUuid`` z POL-onu
(np. po scaleniu zdublowanych profili). Import dopasowywał wiersz wyłącznie po
``personId``, więc taka osoba leciała na INSERT i rozbijała się o unikalność
``polonUuid``.
"""

import uuid

import pytest
from model_bakery import baker

from pbn_api.models import Scientist
from pbn_api.models.institution import Institution
from pbn_api.models.osoba_z_instytucji import OsobaZInstytucji
from pbn_integrator.utils.scientists import _zapisz_osobe_z_instytucji


@pytest.fixture
def instytucja(db):
    return baker.make(Institution)


def _person(scientist, instytucja, polon_uuid, **kw):
    dane = {
        "personId": scientist.pk,
        "institutionId": instytucja.pk,
        "firstName": "Jan",
        "lastName": "Kowalski",
        "institutionName": "Instytut Testowy",
        "polonUuid": str(polon_uuid),
        "phdStudent": False,
    }
    dane.update(kw)
    return dane


@pytest.mark.django_db
def test_zapisz_osobe_z_instytucji_tworzy_wpis(instytucja):
    scientist = baker.make(Scientist)
    polon_uuid = uuid.uuid4()

    assert _zapisz_osobe_z_instytucji(_person(scientist, instytucja, polon_uuid))

    osoba = OsobaZInstytucji.objects.get()
    assert osoba.personId_id == scientist.pk
    assert str(osoba.polonUuid) == str(polon_uuid)


@pytest.mark.django_db
def test_zapisz_osobe_przepina_wpis_gdy_pbn_zmienil_personId(instytucja):
    """Ten sam ``polonUuid`` pod nowym ``personId`` PRZEPINA istniejący wiersz.

    Regresja (Rollbar #1523): leciał ``IntegrityError`` na
    ``pbn_api_osobazinstytucji_polonUuid_key``, a osoba była pomijana —
    czyli nowa tożsamość PBN nigdy nie trafiała do bazy i błąd wracał
    przy każdym kolejnym imporcie.
    """
    polon_uuid = uuid.uuid4()
    stary = baker.make(Scientist)
    nowy = baker.make(Scientist)

    assert _zapisz_osobe_z_instytucji(_person(stary, instytucja, polon_uuid))
    assert _zapisz_osobe_z_instytucji(
        _person(nowy, instytucja, polon_uuid, firstName="Janina")
    )

    # Nadal JEDEN wiersz — ``polonUuid`` jest tożsamością osoby...
    osoba = OsobaZInstytucji.objects.get()
    # ...przepiętą na nowy identyfikator PBN, z odświeżonymi danymi.
    assert osoba.personId_id == nowy.pk
    assert osoba.firstName == "Janina"


@pytest.mark.django_db
def test_zapisz_osobe_pomija_gdy_tozsamosci_nie_da_sie_pogodzic(instytucja, mocker):
    """Dwie osobne tożsamości PBN nie dają się scalić — pomijamy, nie wywalamy.

    Gdy nowy ``personId`` ma JUŻ swój wiersz (z innym ``polonUuid``),
    przepięcie zderza się z unikalnością ``personId``. Scalenie to decyzja
    o danych, nie poprawka techniczna: raportujemy do Rollbara i idziemy
    dalej, zamiast przerywać cały import.
    """
    report = mocker.patch("pbn_integrator.utils.scientists.rollbar.report_exc_info")
    pierwsza = baker.make(Scientist)
    druga = baker.make(Scientist)
    uuid_a, uuid_b = uuid.uuid4(), uuid.uuid4()

    assert _zapisz_osobe_z_instytucji(_person(pierwsza, instytucja, uuid_a))
    assert _zapisz_osobe_z_instytucji(_person(druga, instytucja, uuid_b))

    # Osoba spod uuid_a przychodzi teraz pod personId, który ma już swój wiersz:
    assert not _zapisz_osobe_z_instytucji(_person(druga, instytucja, uuid_a))

    assert report.called
    assert OsobaZInstytucji.objects.count() == 2
