import pytest
from model_bakery import baker

from import_pracownikow.models import ImportPracownikow, ProfilMapowania


@pytest.mark.django_db
def test_import_ma_pole_mapowanie_kolumn_domyslnie_puste():
    imp = baker.make(ImportPracownikow)
    assert imp.mapowanie_kolumn == {}


@pytest.mark.django_db
def test_stan_zmapowany_istnieje():
    assert ImportPracownikow.STAN_ZMAPOWANY == "zmapowany"
    kody = [k for k, _ in ImportPracownikow.STAN_CHOICES]
    assert "zmapowany" in kody


@pytest.mark.django_db
def test_profil_mapowania_zapis_i_odczyt(admin_user):
    p = ProfilMapowania.objects.create(
        nazwa="Uczelnia Vizja Q3",
        mapowanie={"jedn_org": "nazwa_jednostki", "nazwisko": "nazwisko"},
        utworzony_przez=admin_user,
    )
    p.refresh_from_db()
    assert p.mapowanie["jedn_org"] == "nazwa_jednostki"
    assert str(p) == "Uczelnia Vizja Q3"
