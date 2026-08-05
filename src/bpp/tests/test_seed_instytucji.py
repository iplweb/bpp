"""Testy seeda słownika instytucji finansujących (migracja danych 0486).

Migracja danych jest częścią stanu bazy testowej — pytest-django zakłada bazę
przez ``migrate``, więc wiersze zasiane przez 0486 widać w każdym teście
z ``django_db``. Te testy nie pilnują tego, że seed „się wykonał", tylko że
nie wjechał do niego identyfikator wpisany z pamięci: zły Crossref Funder ID
albo ROR z literówką sklei publikacje uczelni z cudzym profilem grantodawcy
w OpenAIRE, a rekord wyglądający na uzupełniony jest gorszy niż pusty.
"""

import importlib

import pytest
from django.apps import apps as rejestr_aplikacji

from bpp.models import Instytucja_Finansujaca
from bpp.util.ror import poprawny as ror_poprawny

MIGRACJA = "bpp.migrations.0486_seed_instytucje_finansujace"

#: Akronimy, których obecności pilnujemy — zakres uzgodniony w planie.
OCZEKIWANE_AKRONIMY = {
    "NCN",
    "NCBR",
    "MNiSW",
    "FNP",
    "NAWA",
    "ABM",
    "EC",
}


@pytest.mark.django_db
def test_seed_zawiera_ncn():
    ncn = Instytucja_Finansujaca.objects.filter(akronim="NCN").first()
    assert ncn is not None
    assert ncn.kraj == "PL"


@pytest.mark.django_db
def test_seed_zawiera_wszystkie_instytucje_z_zakresu():
    obecne = set(
        Instytucja_Finansujaca.objects.filter(
            akronim__in=OCZEKIWANE_AKRONIMY
        ).values_list("akronim", flat=True)
    )
    assert obecne == OCZEKIWANE_AKRONIMY


@pytest.mark.django_db
def test_seed_bez_zmyslonych_identyfikatorow():
    # FundRef ID Crossrefa to sam ciąg cyfr (bez URL-a i bez prefiksu).
    for instytucja in Instytucja_Finansujaca.objects.exclude(fundref_id=""):
        assert instytucja.fundref_id.isdigit(), instytucja.nazwa


@pytest.mark.django_db
def test_seed_ma_poprawne_identyfikatory_ror():
    # ROR ma wbudowaną sumę kontrolną — literówka w przepisanym identyfikatorze
    # jest tu wykrywalna bez odpytywania sieci.
    for instytucja in Instytucja_Finansujaca.objects.exclude(ror_id=""):
        assert ror_poprawny(instytucja.ror_id), instytucja.nazwa


@pytest.mark.django_db
def test_seed_ma_identyfikatory_dla_calego_zakresu():
    # Każda instytucja z zakresu została potwierdzona w OBU rejestrach —
    # gdyby któraś straciła identyfikator przy edycji seeda, chcemy to
    # zobaczyć tutaj, a nie w harveście OpenAIRE.
    for instytucja in Instytucja_Finansujaca.objects.filter(
        akronim__in=OCZEKIWANE_AKRONIMY
    ):
        assert instytucja.fundref_id, instytucja.nazwa
        assert instytucja.ror_id, instytucja.nazwa


@pytest.mark.django_db
def test_seed_jest_idempotentny():
    # ``get_or_create`` po ``fundref_id`` — powtórne przejście migracji
    # (np. przy odtwarzaniu bazy z dumpu sprzed baseline'u) nie może
    # zdublować słownika.
    przed = Instytucja_Finansujaca.objects.count()
    importlib.import_module(MIGRACJA).seed(rejestr_aplikacji, None)
    assert Instytucja_Finansujaca.objects.count() == przed
