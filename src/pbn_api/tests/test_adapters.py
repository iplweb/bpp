import pytest
from model_mommy import mommy

from fixtures.pbn_api import _zrob_wydawnictwo_pbn
from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.exceptions import PKZeroExportDisabled, WillNotExportError

from bpp.models import (
    Autor,
    Czas_Udostepnienia_OpenAccess,
    Licencja_OpenAccess,
    Tryb_OpenAccess_Wydawnictwo_Ciagle,
    Wersja_Tekstu_OpenAccess,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
    const,
)


def test_WydawnictwoPBNAdapter_ciagle(pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina):
    res = WydawnictwoPBNAdapter(
        pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ).pbn_get_json()
    assert res["journal"]


def test_WydawnictwoPBNAdapter_nie_wysylaj_prac_bez_pk(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina, pbn_uczelnia
):
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina.punkty_kbn = 0
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina.save()

    pbn_uczelnia.pbn_api_nie_wysylaj_prac_bez_pk = True
    pbn_uczelnia.save()

    with pytest.raises(PKZeroExportDisabled):
        WydawnictwoPBNAdapter(
            pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina, None, pbn_uczelnia
        ).pbn_get_json()


def test_WydawnictwoPBNAdapter_zwarte_ksiazka(pbn_wydawnictwo_zwarte_ksiazka):
    res = WydawnictwoPBNAdapter(pbn_wydawnictwo_zwarte_ksiazka).pbn_get_json()
    assert not res.get("journal")


def test_WydawnictwoPBNAdapter_zwarte_rozdzial(pbn_rozdzial_z_autorem_z_dyscyplina):
    res = WydawnictwoPBNAdapter(pbn_rozdzial_z_autorem_z_dyscyplina).pbn_get_json()
    assert not res.get("journal")


@pytest.fixture
def praca_z_dyscyplina_pbn(praca_z_dyscyplina, pbn_jezyk):
    _zrob_wydawnictwo_pbn(praca_z_dyscyplina, pbn_jezyk)
    return praca_z_dyscyplina


@pytest.fixture
def rozdzial_z_dyscyplina_pbn(praca_z_dyscyplina_pbn):
    cf = praca_z_dyscyplina_pbn.charakter_formalny
    cf.rodzaj_pbn = const.RODZAJ_PBN_ROZDZIAL
    cf.save()

    return praca_z_dyscyplina_pbn


def test_WydawnictwoPBNAdapter_autor_eksport(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina, jednostka
):

    autor_bez_dyscypliny = mommy.make(Autor)
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina.dodaj_autora(
        autor_bez_dyscypliny, jednostka, "Jan Budnik"
    )

    res = WydawnictwoPBNAdapter(
        pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ).pbn_get_json()
    assert res["journal"]


@pytest.mark.django_db
def test_WydawnictwoPBNAdapter_pk_rowne_zero_eksport_wylaczony(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina, jednostka, rf, pbn_uczelnia
):

    autor_bez_dyscypliny = mommy.make(Autor)
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina.dodaj_autora(
        autor_bez_dyscypliny, jednostka, "Jan Budnik"
    )

    pbn_uczelnia.pbn_api_nie_wysylaj_prac_bez_pk = True
    pbn_uczelnia.save()

    with pytest.raises(PKZeroExportDisabled):
        WydawnictwoPBNAdapter(
            pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina, uczelnia=pbn_uczelnia
        ).pbn_get_json()


def test_WydawnictwoPBNAdapter_przypinanie_dyscyplin(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina, jednostka
):
    wydawnictwo_autor: Wydawnictwo_Zwarte_Autor = (
        pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina.autorzy_set.first()
    )
    wydawnictwo_autor.przypieta = False
    wydawnictwo_autor.save()

    with pytest.raises(WillNotExportError, match="bez zadeklarowanych"):
        WydawnictwoPBNAdapter(
            pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
        ).pbn_get_json()

    wydawnictwo_autor.przypieta = True
    wydawnictwo_autor.save()

    res = WydawnictwoPBNAdapter(
        pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ).pbn_get_json()
    assert res["statements"]


def test_WydawnictwoPBNAdapter_eksport_artykulu_bez_oswiadczen_zwraca_blad(
    praca_z_dyscyplina_pbn,
):
    with pytest.raises(WillNotExportError, match="bez zadeklarowanych"):
        WydawnictwoPBNAdapter(praca_z_dyscyplina_pbn).pbn_get_json()


def test_WydawnictwoPBNAdapter_eksport_rozdzialu_bez_oswiadczen_zwraca_blad(
    rozdzial_z_dyscyplina_pbn,
):
    with pytest.raises(WillNotExportError, match="bez zadeklarowanych"):
        WydawnictwoPBNAdapter(rozdzial_z_dyscyplina_pbn).pbn_get_json()


def test_WydawnictwoPBNAdapter_www_eksport(
    pbn_rozdzial_z_autorem_z_dyscyplina, wydawnictwo_nadrzedne, pbn_jezyk
):
    wydawnictwo_zwarte = pbn_rozdzial_z_autorem_z_dyscyplina

    assert wydawnictwo_zwarte.wydawnictwo_nadrzedne_id == wydawnictwo_nadrzedne.pk

    _zrob_wydawnictwo_pbn(
        wydawnictwo_zwarte, pbn_jezyk, rodzaj_pbn=const.RODZAJ_PBN_ROZDZIAL
    )

    wydawnictwo_nadrzedne.public_www = "123"
    wydawnictwo_nadrzedne.save()

    wydawnictwo_zwarte.www = wydawnictwo_zwarte.public_www = None
    wydawnictwo_zwarte.save()

    res = WydawnictwoPBNAdapter(wydawnictwo_zwarte).pbn_get_json()
    assert res["publicUri"] == "123"

    wydawnictwo_zwarte.www = "456"
    wydawnictwo_zwarte.save()

    assert wydawnictwo_zwarte.wydawnictwo_nadrzedne == wydawnictwo_nadrzedne

    res = WydawnictwoPBNAdapter(wydawnictwo_zwarte).pbn_get_json()
    assert res["publicUri"] == "456"


def test_WydawnictwoPBNAdapter_openaccess_zero_miesiecy_gdy_licencja(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina: Wydawnictwo_Zwarte, openaccess_data
):

    praca_z_dyscyplina_pbn = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina

    praca_z_dyscyplina_pbn.openaccess_licencja = Licencja_OpenAccess.objects.first()
    praca_z_dyscyplina_pbn.openaccess_tryb_dostepu = (
        Tryb_OpenAccess_Wydawnictwo_Ciagle.objects.first()
    )
    praca_z_dyscyplina_pbn.openaccess_wersja_tekstu = (
        Wersja_Tekstu_OpenAccess.objects.first()
    )
    praca_z_dyscyplina_pbn.openaccess_czas_publikacji = (
        Czas_Udostepnienia_OpenAccess.objects.get(nazwa="po opublikowaniu")
    )
    praca_z_dyscyplina_pbn.openaccess_ilosc_miesiecy = 12
    praca_z_dyscyplina_pbn.save()

    res = WydawnictwoPBNAdapter(praca_z_dyscyplina_pbn).pbn_get_json()
    assert res["openAccess"]["months"] == "12"

    praca_z_dyscyplina_pbn.openaccess_ilosc_miesiecy = None
    praca_z_dyscyplina_pbn.save()

    res = WydawnictwoPBNAdapter(praca_z_dyscyplina_pbn).pbn_get_json()
    assert res["openAccess"]["months"] == "0"


def test_WydawnictwoPBNAdapter_autor_isbn_eisbn(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina,
):
    praca_z_dyscyplina_pbn = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina

    praca_z_dyscyplina_pbn.isbn = None
    praca_z_dyscyplina_pbn.e_isbn = "123"

    res = WydawnictwoPBNAdapter(praca_z_dyscyplina_pbn).pbn_get_json()
    assert res["isbn"] == "123"

    praca_z_dyscyplina_pbn.isbn = "456"
    praca_z_dyscyplina_pbn.e_isbn = None

    res = WydawnictwoPBNAdapter(praca_z_dyscyplina_pbn).pbn_get_json()
    assert res["isbn"] == "456"

    praca_z_dyscyplina_pbn.isbn = "789"
    praca_z_dyscyplina_pbn.e_isbn = "123"

    res = WydawnictwoPBNAdapter(praca_z_dyscyplina_pbn).pbn_get_json()
    assert res["isbn"] == "789"


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
