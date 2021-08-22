import pytest
from model_mommy import mommy

from pbn_api.client import PBN_GET_LANGUAGES_URL, PBNClient
from pbn_api.models import Institution, Language, Publication, Scientist
from pbn_api.tests.utils import MockTransport

from bpp.models import Charakter_Formalny, Jezyk, Uczelnia, Wydawnictwo_Ciagle, const
from bpp.models.const import RODZAJ_PBN_KSIAZKA

MOCK_RETURNED_MONGODB_DATA = dict(
    status="foo",
    verificationLevel="bar",
    verified=True,
    versions=[{"current": True, "baz": "quux"}],
    mongoId="123",
)


@pytest.fixture
def pbnclient():
    transport = MockTransport()
    return PBNClient(transport=transport)


@pytest.fixture
def pbn_language():
    return Language.objects.create(code="pl", language={"lol": "XD"})


@pytest.fixture
def pbn_autor(autor_jan_nowak):
    autor_jan_nowak.pbn_uid = mommy.make(Scientist)
    return autor_jan_nowak


@pytest.fixture
def pbn_jednostka(jednostka):
    jednostka.pbn_uid = mommy.make(Institution)
    return jednostka


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
def pbn_charakter_formalny() -> Charakter_Formalny:
    return mommy.make(Charakter_Formalny, rodzaj_pbn=RODZAJ_PBN_KSIAZKA)


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


@pytest.fixture
def pbn_publication(db):
    return Publication.objects.create(mongoId=123, versions={})


@pytest.fixture
def pbn_wydawnictwo_zwarte_z_charakterem(
    pbn_wydawnictwo_zwarte, pbn_charakter_formalny
):
    pbn_wydawnictwo_zwarte.charakter_formalny = pbn_charakter_formalny
    pbn_wydawnictwo_zwarte.save()
    return pbn_wydawnictwo_zwarte


@pytest.fixture
def pbn_uczelnia(pbnclient):
    uczelnia = mommy.make(
        Uczelnia,
    )

    uczelnia.pbn_client = lambda *args, **kw: pbnclient
    pbnclient.transport.return_values[PBN_GET_LANGUAGES_URL] = {"1": "23"}

    uczelnia.pbn_integracja = True
    uczelnia.pbn_aktualizuj_na_biezaco = True
    uczelnia.pbn_app_name = "FOO"
    uczelnia.pbn_app_token = "BAR"
    uczelnia.pbn_api_root = "https://localhost/pbn/mockapi/v1/"
    uczelnia.save()

    return uczelnia
