import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_model_tworzy_sie_i_ma_wiersze(admin_user):
    from import_punktacji_zrodel.models import (
        ImportPunktacjiZrodel,
        WierszImportuPunktacjiZrodel,
    )

    imp = baker.make(ImportPunktacjiZrodel, owner=admin_user, rok=2025)
    WierszImportuPunktacjiZrodel.objects.create(
        parent=imp, dane_z_xls={"nazwa": "X"}, nr_wiersza=1, rezultat="ok"
    )
    assert imp.get_details_set().count() == 1
