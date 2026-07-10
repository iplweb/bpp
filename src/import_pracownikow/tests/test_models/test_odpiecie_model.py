import pytest
from model_bakery import baker

from bpp.models import Autor_Jednostka
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowOdpiecie,
    ImportPracownikowRow,
)


@pytest.mark.django_db
def test_row_ma_pole_utworz_nowego_default_false():
    imp = baker.make(ImportPracownikow)
    row = ImportPracownikowRow(parent=imp, zmiany_potrzebne=False)
    row.save()
    row.refresh_from_db()
    assert row.utworz_nowego is False


@pytest.mark.django_db
def test_odpiecie_defaults_i_relacja_parent():
    imp = baker.make(ImportPracownikow)
    aj = baker.make(Autor_Jednostka)
    odp = ImportPracownikowOdpiecie.objects.create(parent=imp, autor_jednostka=aj)
    assert odp.zaznaczone is False
    assert odp.wykonane is False
    assert list(imp.odpiecia.all()) == [odp]


@pytest.mark.django_db
def test_odpiecie_ordering_po_nazwisku_autora():
    imp = baker.make(ImportPracownikow)
    aj_b = baker.make(Autor_Jednostka, autor__nazwisko="Bielecki")
    aj_a = baker.make(Autor_Jednostka, autor__nazwisko="Adamski")
    ImportPracownikowOdpiecie.objects.create(parent=imp, autor_jednostka=aj_b)
    ImportPracownikowOdpiecie.objects.create(parent=imp, autor_jednostka=aj_a)
    nazwiska = [o.autor_jednostka.autor.nazwisko for o in imp.odpiecia.all()]
    assert nazwiska == ["Adamski", "Bielecki"]
