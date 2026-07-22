import pytest
from model_bakery import baker

from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow


@pytest.mark.django_db
def test_row_dopuszcza_null_fk_i_ma_pola_odroczenia():
    parent = baker.make(ImportPracownikow)
    row = ImportPracownikowRow.objects.create(
        parent=parent,
        autor=None,
        jednostka=None,
        autor_jednostka=None,
        funkcja_autora=None,
        grupa_pracownicza=None,
        wymiar_etatu=None,
        zmiany_potrzebne=False,
    )
    assert row.pk is not None
    assert row.diff_do_utworzenia == {}
    assert row.pominiety_bo_nieaktualny is False
