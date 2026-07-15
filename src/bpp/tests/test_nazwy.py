import pytest

from bpp.nazwy import DOMYSLNE_LEMATY, lemat


@pytest.mark.django_db
def test_lemat_z_zasianego_wiersza():
    # migracja 0362 zasiewa UCZELNIA/WYDZIAL/JEDNOSTKA
    assert lemat("JEDNOSTKA") == "jednostka"


@pytest.mark.django_db
def test_lemat_override_przemianowanie(rzeczowniki):
    from bpp.models import Rzeczownik

    Rzeczownik.objects.filter(uid="JEDNOSTKA").update(m="dział")
    assert lemat("JEDNOSTKA") == "dział"


@pytest.mark.django_db
def test_lemat_brak_wiersza_uzywa_domyslnego():
    from bpp.models import Rzeczownik

    Rzeczownik.objects.filter(uid="JEDNOSTKA").delete()
    assert lemat("JEDNOSTKA") == DOMYSLNE_LEMATY["JEDNOSTKA"]
