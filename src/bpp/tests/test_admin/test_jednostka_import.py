"""Faza C (#438): importer XLSX tworzy „wydział" jako jednostkę top-level."""

import pytest
import tablib
from model_bakery import baker

from bpp.admin.jednostka_import import JednostkaImportResource
from bpp.models import Jednostka

HEADERS = ["Uczelnia", "Wydział", "Katedra/Zakład/Klinika"]


@pytest.mark.django_db
def test_import_tworzy_wydzial_jako_jednostke_toplevel(uczelnia):
    ds = tablib.Dataset(headers=HEADERS)
    ds.append([uczelnia.nazwa, "Wydział Testowy", "Katedra Alfa"])

    result = JednostkaImportResource().import_data(ds, raise_errors=True)
    assert not result.has_errors()

    root = Jednostka.objects.get(nazwa="Wydział Testowy")
    assert root.parent is None
    katedra = Jednostka.objects.get(nazwa="Katedra Alfa")
    assert katedra.parent_id == root.pk


@pytest.mark.django_db
def test_import_wydzial_ponownie_uzywa_istniejacego_roota(uczelnia):
    root = baker.make(
        Jednostka, nazwa="Wydział Istniejący", parent=None, uczelnia=uczelnia
    )
    ds = tablib.Dataset(headers=HEADERS)
    ds.append([uczelnia.nazwa, "Wydział Istniejący", "Nowa Katedra"])

    JednostkaImportResource().import_data(ds, raise_errors=True)

    assert Jednostka.objects.filter(nazwa="Wydział Istniejący").count() == 1
    assert Jednostka.objects.get(nazwa="Nowa Katedra").parent_id == root.pk


@pytest.mark.django_db
def test_import_wydzial_kolizja_z_jednostka_podrzedna_blad(uczelnia):
    """F8: ``Jednostka.nazwa`` jest UNIQUE globalnie; wydział o nazwie
    istniejącej jednostki PODRZĘDNEJ = błąd jawny (nie ciche przypięcie
    dziecka pod nie-root albo IntegrityError)."""
    root = baker.make(Jednostka, nazwa="Wydział X", parent=None, uczelnia=uczelnia)
    baker.make(Jednostka, nazwa="Kolizja", parent=root, uczelnia=uczelnia)

    ds = tablib.Dataset(headers=HEADERS)
    ds.append([uczelnia.nazwa, "Kolizja", "Inna Katedra"])

    result = JednostkaImportResource().import_data(ds, raise_errors=False)
    # Widget zgłasza ValueError w fazie walidacji import-export → validation error.
    assert result.has_validation_errors()
    # Kolizja BLOKUJE import wiersza — żadna zła jednostka nie powstaje.
    assert Jednostka.objects.filter(nazwa="Inna Katedra").count() == 0
