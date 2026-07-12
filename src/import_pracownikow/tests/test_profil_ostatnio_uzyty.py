import pytest
from model_bakery import baker

from import_pracownikow.mapping import wybierz_profil_fallback


@pytest.mark.django_db
def test_fallback_zwraca_ostatnio_uzyty_gdy_pokrycie_wystarcza():
    baker.make(
        "import_pracownikow.ProfilMapowania",
        nazwa="stary",
        mapowanie={"nazwisko": "nazwisko", "imię": "imię"},
        ostatnio_uzyty="2026-01-01T00:00:00Z",
    )
    nowy = baker.make(
        "import_pracownikow.ProfilMapowania",
        nazwa="nowy",
        mapowanie={"nazwisko": "nazwisko", "imię": "imię"},
        ostatnio_uzyty="2026-07-01T00:00:00Z",
    )
    # nagłówki pliku pokrywają klucze profilu w 100% → powyżej progu 0.5
    assert wybierz_profil_fallback(["nazwisko", "imię"]) == nowy


@pytest.mark.django_db
def test_fallback_none_gdy_pokrycie_za_male():
    baker.make(
        "import_pracownikow.ProfilMapowania",
        nazwa="p",
        mapowanie={"a": "nazwisko", "b": "imię", "c": "email", "d": "orcid"},
        ostatnio_uzyty="2026-07-01T00:00:00Z",
    )
    # tylko 1 z 4 kluczy profilu obecny w nagłówkach → 0.25 < 0.5
    assert wybierz_profil_fallback(["a", "zzz"]) is None


@pytest.mark.django_db
def test_fallback_none_gdy_brak_profili():
    assert wybierz_profil_fallback(["nazwisko"]) is None
