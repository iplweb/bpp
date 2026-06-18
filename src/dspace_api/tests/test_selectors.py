import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_uczelnie_z_autorzy_set():
    from dspace_api.selectors import uczelnie_rekordu

    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    j1 = baker.make("bpp.Jednostka", uczelnia=u1)
    j2 = baker.make("bpp.Jednostka", uczelnia=u2)

    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, jednostka=j1, kolejnosc=0)
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, jednostka=j2, kolejnosc=1)

    assert uczelnie_rekordu(rec) == {u1, u2}


@pytest.mark.django_db
def test_uczelnie_z_jednostki_rekordu_doktorat(typ_odpowiedzialnosci_autor):
    # ``Praca_Doktorska.autorzy_set`` sięga do modułowego cache
    # ``_Praca_Doktorska_PropertyCache.typ_odpowiedzialnosci_autor``, który
    # robi ``Typ_Odpowiedzialnosci.objects.get(skrot="aut.")``. Ten wiersz
    # musi istnieć w trakcie testu — sam baseline nie wystarcza, bo test
    # transakcyjny (live_server/playwright) w tym samym workerze potrafi
    # zflushować dane referencyjne. Fixture gwarantuje obecność "aut.".
    from dspace_api.selectors import uczelnie_rekordu

    u = baker.make("bpp.Uczelnia")
    j = baker.make("bpp.Jednostka", uczelnia=u)
    rec = baker.make("bpp.Praca_Doktorska", jednostka=j)

    assert uczelnie_rekordu(rec) == {u}
