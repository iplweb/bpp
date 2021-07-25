import pytest
from model_mommy import mommy

from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.tests.conftest import _zrob_wydawnictwo_pbn

from bpp.models import Autor


def test_WydawnictwoPBNAdapter_ciagle(pbn_wydawnictwo_ciagle):
    res = WydawnictwoPBNAdapter(pbn_wydawnictwo_ciagle).pbn_get_json()
    assert res["journal"]


def test_WydawnictwoPBNAdapter_zwarte_ksiazka(pbn_wydawnictwo_zwarte_ksiazka):
    res = WydawnictwoPBNAdapter(pbn_wydawnictwo_zwarte_ksiazka).pbn_get_json()
    assert not res.get("journal")


def test_WydawnictwoPBNAdapter_zwarte_rozdzial(pbn_wydawnictwo_zwarte_rozdzial):
    res = WydawnictwoPBNAdapter(pbn_wydawnictwo_zwarte_rozdzial).pbn_get_json()
    assert not res.get("journal")


@pytest.fixture
def praca_z_dyscyplina_pbn(praca_z_dyscyplina, pbn_jezyk):
    _zrob_wydawnictwo_pbn(praca_z_dyscyplina, pbn_jezyk)
    return praca_z_dyscyplina


def test_WydawnictwoPBNAdapter_autor_eksport(praca_z_dyscyplina_pbn, jednostka):

    autor_bez_dyscypliny = mommy.make(Autor)
    praca_z_dyscyplina_pbn.dodaj_autora(autor_bez_dyscypliny, jednostka, "Jan Budnik")

    res = WydawnictwoPBNAdapter(praca_z_dyscyplina_pbn).pbn_get_json()
    assert res["journal"]


def test_WydawnictwoPBNAdapter_autor_z_orcid_bez_dyscypliny_idzie_bez_id(
    praca_z_dyscyplina_pbn, jednostka
):
    pierwszy_autor = praca_z_dyscyplina_pbn.autorzy_set.first().autor
    pierwszy_autor.orcid = "123456"
    pierwszy_autor.save()

    autor_bez_dyscypliny = mommy.make(
        Autor, imiona="Jan", nazwisko="Budnik", orcid="43567"
    )
    praca_z_dyscyplina_pbn.dodaj_autora(autor_bez_dyscypliny, jednostka, "Jan Budnik")

    res = WydawnictwoPBNAdapter(praca_z_dyscyplina_pbn).pbn_get_json()
    assert res["authors"][0].get("orcidId")
    assert not res["authors"][1].get("orcidId")


def test_WydawnictwoPBNAdapter_pod_redakcja_falsz(ksiazka, autor_jan_nowak, jednostka):
    ksiazka.dodaj_autora(autor_jan_nowak, jednostka)
    assert WydawnictwoPBNAdapter(ksiazka).pod_redakcja() is False


def test_WydawnictwoPBNAdapter_pod_redakcja_prawda(ksiazka, autor_jan_nowak, jednostka):
    ksiazka.dodaj_autora(autor_jan_nowak, jednostka, typ_odpowiedzialnosci_skrot="red.")
    assert WydawnictwoPBNAdapter(ksiazka).pod_redakcja() is True
