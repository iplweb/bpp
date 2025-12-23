import pytest
from django.core.management import call_command
from model_bakery import baker

from bpp.models.wydawca import Poziom_Wydawcy, Wydawca


@pytest.mark.django_db
def test_klonuj_poziom_wydawcy_utworzy_nowy():
    """Test tworzenia nowego poziomu gdy nie istnieje w roku docelowym."""
    wydawca = baker.make(Wydawca)
    baker.make(Poziom_Wydawcy, wydawca=wydawca, rok=2025, poziom=2)

    call_command("klonuj_poziom_wydawcy", 2025, 2026)

    assert Poziom_Wydawcy.objects.filter(wydawca=wydawca, rok=2026, poziom=2).exists()


@pytest.mark.django_db
def test_klonuj_poziom_wydawcy_pomija_identyczny():
    """Test pomijania gdy poziom w roku docelowym jest identyczny."""
    wydawca = baker.make(Wydawca)
    baker.make(Poziom_Wydawcy, wydawca=wydawca, rok=2025, poziom=2)
    baker.make(Poziom_Wydawcy, wydawca=wydawca, rok=2026, poziom=2)

    call_command("klonuj_poziom_wydawcy", 2025, 2026)

    assert Poziom_Wydawcy.objects.filter(wydawca=wydawca, rok=2026).count() == 1


@pytest.mark.django_db
def test_klonuj_poziom_wydawcy_nie_nadpisuje_innego_bez_force():
    """Test że bez --force nie nadpisuje różnego poziomu."""
    wydawca = baker.make(Wydawca)
    baker.make(Poziom_Wydawcy, wydawca=wydawca, rok=2025, poziom=2)
    baker.make(Poziom_Wydawcy, wydawca=wydawca, rok=2026, poziom=1)

    call_command("klonuj_poziom_wydawcy", 2025, 2026)

    # Poziom powinien pozostać niezmieniony (1)
    pw = Poziom_Wydawcy.objects.get(wydawca=wydawca, rok=2026)
    assert pw.poziom == 1


@pytest.mark.django_db
def test_klonuj_poziom_wydawcy_nadpisuje_z_force():
    """Test że z --force nadpisuje różny poziom."""
    wydawca = baker.make(Wydawca)
    baker.make(Poziom_Wydawcy, wydawca=wydawca, rok=2025, poziom=2)
    baker.make(Poziom_Wydawcy, wydawca=wydawca, rok=2026, poziom=1)

    call_command("klonuj_poziom_wydawcy", 2025, 2026, force=True)

    pw = Poziom_Wydawcy.objects.get(wydawca=wydawca, rok=2026)
    assert pw.poziom == 2


@pytest.mark.django_db
def test_klonuj_poziom_wydawcy_dry_run():
    """Test że --dry-run nie tworzy rekordów."""
    wydawca = baker.make(Wydawca)
    baker.make(Poziom_Wydawcy, wydawca=wydawca, rok=2025, poziom=2)

    call_command("klonuj_poziom_wydawcy", 2025, 2026, dry_run=True)

    assert not Poziom_Wydawcy.objects.filter(wydawca=wydawca, rok=2026).exists()


@pytest.mark.django_db
def test_klonuj_poziom_wydawcy_wiele_wydawcow():
    """Test klonowania wielu wydawców naraz."""
    wydawca1 = baker.make(Wydawca)
    wydawca2 = baker.make(Wydawca)
    wydawca3 = baker.make(Wydawca)

    baker.make(Poziom_Wydawcy, wydawca=wydawca1, rok=2025, poziom=1)
    baker.make(Poziom_Wydawcy, wydawca=wydawca2, rok=2025, poziom=2)
    baker.make(Poziom_Wydawcy, wydawca=wydawca3, rok=2025, poziom=1)

    call_command("klonuj_poziom_wydawcy", 2025, 2026)

    assert Poziom_Wydawcy.objects.filter(rok=2026).count() == 3
    assert Poziom_Wydawcy.objects.filter(wydawca=wydawca1, rok=2026, poziom=1).exists()
    assert Poziom_Wydawcy.objects.filter(wydawca=wydawca2, rok=2026, poziom=2).exists()
    assert Poziom_Wydawcy.objects.filter(wydawca=wydawca3, rok=2026, poziom=1).exists()


@pytest.mark.django_db
def test_klonuj_poziom_wydawcy_brak_danych_zrodlowych():
    """Test gdy nie ma żadnych poziomów w roku źródłowym."""
    call_command("klonuj_poziom_wydawcy", 2025, 2026)

    assert Poziom_Wydawcy.objects.filter(rok=2026).count() == 0
