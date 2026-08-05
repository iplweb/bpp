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
        "title": "dr hab.",
        "from": "2020-01-01",
        "to": "2030-12-31",
    }
    dane.update(kw)
    return dane


@pytest.mark.django_db
def test_zapisz_osobe_z_instytucji_zapisuje_wszystkie_pola(instytucja):
    scientist = baker.make(Scientist)
    polon_uuid = uuid.uuid4()

    assert _zapisz_osobe_z_instytucji(_person(scientist, instytucja, polon_uuid))

    osoba = OsobaZInstytucji.objects.get()
    assert osoba.personId_id == scientist.pk
    assert osoba.institutionId_id == instytucja.pk
    assert str(osoba.polonUuid) == str(polon_uuid)
    assert osoba.firstName == "Jan"
    assert osoba.lastName == "Kowalski"
    assert osoba.institutionName == "Instytut Testowy"
    assert osoba.title == "dr hab."
    assert osoba.phdStudent is False
    assert str(osoba._from) == "2020-01-01"
    assert str(osoba._to) == "2030-12-31"


@pytest.mark.django_db
def test_zapisz_osobe_bez_polonuuid_pomija_bez_raportu(instytucja, mocker):
    """Brak ``polonUuid`` (kolumna NOT NULL) to nie „konflikt tożsamości".

    Wcześniej dowiadywaliśmy się o tym okrężnie — przez IntegrityError na
    NOT NULL, raportowany do Rollbara pod mylącą etykietą konfliktu.
    """
    report = mocker.patch("pbn_integrator.utils.scientists.rollbar.report_exc_info")
    scientist = baker.make(Scientist)

    dane = _person(scientist, instytucja, uuid.uuid4())
    del dane["polonUuid"]

    assert not _zapisz_osobe_z_instytucji(dane)
    assert not report.called
    assert not OsobaZInstytucji.objects.exists()


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
    nowa_instytucja = baker.make(Institution)

    assert _zapisz_osobe_z_instytucji(_person(stary, instytucja, polon_uuid))
    pierwotny_pk = OsobaZInstytucji.objects.get().pk

    assert _zapisz_osobe_z_instytucji(
        _person(nowy, nowa_instytucja, polon_uuid, firstName="Janina")
    )

    # Nadal JEDEN wiersz — ``polonUuid`` jest tożsamością osoby...
    osoba = OsobaZInstytucji.objects.get()
    # ...i to TEN SAM wiersz: przepięty, nie skasowany i odtworzony. FK z
    # deduplikator_autorow (``main_osoba_z_instytucji``, on_delete=SET_NULL)
    # przeżyłby podmianę jako NULL, więc pilnujemy pk.
    assert osoba.pk == pierwotny_pk
    assert osoba.personId_id == nowy.pk
    assert osoba.firstName == "Janina"
    # ``institutionId`` MUSI się odświeżyć — na nim stoi scoping per-uczelnia
    # (patrz bpp/views/autocomplete/authors.py: institutionId_id == pbn_uid).
    assert osoba.institutionId_id == nowa_instytucja.pk


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
    # Raport musi nieść treść naruszonego ograniczenia — bez tego kolizja
    # personId, NOT NULL i każdy inny IntegrityError wyglądają identycznie.
    assert "constraint" in report.call_args.kwargs["extra_data"]
    assert OsobaZInstytucji.objects.count() == 2
