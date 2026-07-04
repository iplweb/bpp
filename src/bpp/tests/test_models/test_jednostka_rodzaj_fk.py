import pytest
from model_bakery import baker

from bpp.models import Jednostka, RodzajJednostki


@pytest.mark.django_db
def test_rodzaj_fk_da_sie_przypisac():
    std = RodzajJednostki.objects.get(nazwa="Standard")
    j = baker.make(Jednostka, rodzaj=std)
    j.refresh_from_db()
    assert j.rodzaj == std


@pytest.mark.django_db
def test_rodzaj_domyslnie_null_dla_nowego_obiektu():
    # W fazie A rodzaj FK jest addytywne; stary kod ustawia tylko string.
    # Nowy obiekt bez jawnego rodzaj ma NULL (re-backfill dopiero w fazie B).
    j = baker.make(Jednostka, rodzaj=None, rodzaj_jednostki="normalna")
    j.refresh_from_db()
    assert j.rodzaj is None


@pytest.mark.django_db
def test_istniejace_jednostki_bez_rodzaju_daja_sie_zbackfillowac():
    # symulacja: jednostka z NULL rodzaj (jak wiersz sprzed migracji)
    j = baker.make(Jednostka, rodzaj_jednostki="normalna")
    Jednostka.objects.filter(pk=j.pk).update(rodzaj=None)
    # ręczny backfill jak w migracji
    std = RodzajJednostki.objects.get(nazwa="Standard")
    Jednostka.objects.filter(rodzaj_jednostki="normalna", rodzaj__isnull=True).update(
        rodzaj=std
    )
    j.refresh_from_db()
    assert j.rodzaj == std
