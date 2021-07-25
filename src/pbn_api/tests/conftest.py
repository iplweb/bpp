import pytest

from pbn_api.models import Language

from bpp.models import Jezyk, Wydawnictwo_Ciagle, const


@pytest.fixture
def pbn_language():
    return Language.objects.create(code="pl", language={"lol": "XD"})


@pytest.fixture
def pbn_jezyk(jezyki, pbn_language):
    polski = Jezyk.objects.get(nazwa="polski")
    polski.pbn_uid = pbn_language
    polski.save()
    return polski


def _zrob_wydawnictwo_pbn(wydawnictwo_ciagle, jezyk):
    cf = wydawnictwo_ciagle.charakter_formalny
    cf.rodzaj_pbn = const.RODZAJ_PBN_ARTYKUL
    cf.save()

    wydawnictwo_ciagle.jezyk = jezyk

    wydawnictwo_ciagle.doi = "123;.123/doi"
    wydawnictwo_ciagle.save()


@pytest.fixture
def pbn_wydawnictwo_ciagle(wydawnictwo_ciagle, pbn_jezyk) -> Wydawnictwo_Ciagle:
    _zrob_wydawnictwo_pbn(wydawnictwo_ciagle, pbn_jezyk)
    return wydawnictwo_ciagle


@pytest.fixture
def pbn_wydawnictwo_zwarte(wydawnictwo_zwarte, pbn_jezyk):
    cf = wydawnictwo_zwarte.charakter_formalny
    cf.rodzaj_pbn = const.RODZAJ_PBN_ARTYKUL
    cf.save()

    wydawnictwo_zwarte.jezyk = pbn_jezyk

    wydawnictwo_zwarte.doi = "123;.123/doi"
    wydawnictwo_zwarte.save()

    return wydawnictwo_zwarte


@pytest.fixture
def pbn_wydawnictwo_zwarte_ksiazka(pbn_wydawnictwo_zwarte):
    cf = pbn_wydawnictwo_zwarte.charakter_formalny
    cf.rodzaj_pbn = const.RODZAJ_PBN_KSIAZKA
    cf.save()

    return pbn_wydawnictwo_zwarte


@pytest.fixture
def pbn_wydawnictwo_zwarte_rozdzial(pbn_wydawnictwo_zwarte):
    cf = pbn_wydawnictwo_zwarte.charakter_formalny
    cf.rodzaj_pbn = const.RODZAJ_PBN_ROZDZIAL
    cf.save()

    return pbn_wydawnictwo_zwarte
