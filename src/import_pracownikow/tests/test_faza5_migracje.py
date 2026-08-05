import pytest
from model_bakery import baker

from bpp.models import Autor, Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from przemapuj_prace_autora.models import PrzemapoaniePracAutora


@pytest.mark.django_db
def test_przepnij_prace_pole_domyslnie_false_i_zapisywalne():
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_UTWORZONY)
    row = ImportPracownikowRow.objects.create(parent=imp, zmiany_potrzebne=False)
    assert row.przepnij_prace is False
    row.przepnij_prace = True
    row.save(update_fields=["przepnij_prace"])
    row.refresh_from_db()
    assert row.przepnij_prace is True


@pytest.mark.django_db
def test_zrodlowy_import_fk_i_related_name():
    imp = baker.make(ImportPracownikow)
    prz = PrzemapoaniePracAutora.objects.create(
        autor=baker.make(Autor),
        jednostka_z=baker.make(Jednostka),
        jednostka_do=baker.make(Jednostka),
        zrodlowy_import=imp,
    )
    prz.refresh_from_db()
    assert prz.zrodlowy_import_id == imp.pk
    assert list(imp.przemapowania.all()) == [prz]


@pytest.mark.django_db
def test_zrodlowy_import_nullable():
    prz = PrzemapoaniePracAutora.objects.create(
        autor=baker.make(Autor),
        jednostka_z=baker.make(Jednostka),
        jednostka_do=baker.make(Jednostka),
    )
    assert prz.zrodlowy_import_id is None
