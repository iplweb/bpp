from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter

from bpp.models import const


def test_WydawnictwoPBNAdapter_ciagle(wydawnictwo_ciagle):
    cf = wydawnictwo_ciagle.charakter_formalny
    cf.rodzaj_pbn = const.RODZAJ_PBN_ARTYKUL
    cf.save()

    wydawnictwo_ciagle.doi = "123;.123/doi"
    assert WydawnictwoPBNAdapter(wydawnictwo_ciagle).pbn_get_json()
    raise NotImplementedError


def test_WydawnictwoPBNAdapter_zwarte_ksiazka(wydawnictwo_zwarte):
    cf = wydawnictwo_zwarte.charakter_formalny
    cf.rodzaj_pbn = const.RODZAJ_PBN_KSIAZKA
    cf.save()

    wydawnictwo_zwarte.doi = "123;.123/doi"
    assert WydawnictwoPBNAdapter(wydawnictwo_zwarte).pbn_get_json()
    raise NotImplementedError


def test_WydawnictwoPBNAdapter_zwarte_rozdzial(wydawnictwo_zwarte):
    cf = wydawnictwo_zwarte.charakter_formalny
    cf.rodzaj_pbn = const.CONST_PBN_ROZDZIAL
    cf.save()

    wydawnictwo_zwarte.doi = "123;.123/doi"
    assert WydawnictwoPBNAdapter(wydawnictwo_zwarte).pbn_get_json()
    raise NotImplementedError
