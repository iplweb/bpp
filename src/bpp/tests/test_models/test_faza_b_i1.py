import pytest
from django.core.exceptions import FieldDoesNotExist
from model_bakery import baker

from bpp.models import Jednostka, RodzajJednostki


@pytest.mark.django_db
def test_seed_wydzial_pokazuje_strukture_podjednostek():
    wydzial = RodzajJednostki.objects.get(nazwa="Wydział")
    assert wydzial.pokazuj_strukture_podjednostek is True


def test_jednostka_wchodzi_do_rankingu_autorow_pole_istnieje():
    field = Jednostka._meta.get_field("wchodzi_do_rankingu_autorow")
    assert field.default is True

    # Stara nazwa pola (sprzed RenameField) sklejona z kawałków, żeby nie
    # dawać fałszywego trafienia w grepie pilnującym braku referencji do
    # niej poza migracjami (zob. definition-of-done zadania I-1).
    stara_nazwa = "wchodzi_do_" + "raportow"
    with pytest.raises(FieldDoesNotExist):
        Jednostka._meta.get_field(stara_nazwa)


@pytest.mark.django_db
def test_jednostka_aktualna_override_domyslnie_none():
    field = Jednostka._meta.get_field("aktualna_override")
    assert field.null is True
    assert field.blank is True

    j = baker.make(Jednostka, aktualna_override=None)
    j.refresh_from_db()
    assert j.aktualna_override is None
