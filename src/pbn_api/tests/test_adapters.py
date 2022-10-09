import json
from decimal import Decimal

import pytest
from model_bakery import baker

from fixtures.pbn_api import _zrob_wydawnictwo_pbn
from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.exceptions import PKZeroExportDisabled, WillNotExportError

from bpp import const
from bpp.models import (
    Autor,
    Czas_Udostepnienia_OpenAccess,
    Licencja_OpenAccess,
    Tryb_OpenAccess_Wydawnictwo_Ciagle,
    Wersja_Tekstu_OpenAccess,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)


@pytest.mark.django_db
def test_WydawnictwoPBNAdapter_ciagle(pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina):
    res = WydawnictwoPBNAdapter(
        pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ).pbn_get_json()
    assert res["journal"]


@pytest.mark.django_db
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


@pytest.mark.django_db
def test_WydawnictwoPBNAdapter_zwarte_ksiazka(pbn_wydawnictwo_zwarte_ksiazka):
    res = WydawnictwoPBNAdapter(pbn_wydawnictwo_zwarte_ksiazka).pbn_get_json()
    assert not res.get("journal")


@pytest.mark.django_db
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


@pytest.mark.django_db
def test_WydawnictwoPBNAdapter_autor_eksport(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina, jednostka
):

    autor_bez_dyscypliny = baker.make(Autor)
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

    autor_bez_dyscypliny = baker.make(Autor)
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina.dodaj_autora(
        autor_bez_dyscypliny, jednostka, "Jan Budnik"
    )

    pbn_uczelnia.pbn_api_nie_wysylaj_prac_bez_pk = True
    pbn_uczelnia.save()

    with pytest.raises(PKZeroExportDisabled):
        WydawnictwoPBNAdapter(
            pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina, uczelnia=pbn_uczelnia
        ).pbn_get_json()


@pytest.mark.django_db
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


@pytest.mark.django_db
def test_WydawnictwoPBNAdapter_eksport_artykulu_bez_oswiadczen_zwraca_blad(
    praca_z_dyscyplina_pbn,
):
    with pytest.raises(WillNotExportError, match="bez zadeklarowanych"):
        WydawnictwoPBNAdapter(praca_z_dyscyplina_pbn).pbn_get_json()


@pytest.mark.django_db
def test_WydawnictwoPBNAdapter_eksport_rozdzialu_bez_oswiadczen_zwraca_blad(
    rozdzial_z_dyscyplina_pbn,
):
    with pytest.raises(WillNotExportError, match="bez zadeklarowanych"):
        WydawnictwoPBNAdapter(rozdzial_z_dyscyplina_pbn).pbn_get_json()


@pytest.mark.django_db
def test_WydawnictwoPBNAdapter_www_eksport(
    pbn_rozdzial_z_autorem_z_dyscyplina, wydawnictwo_nadrzedne, pbn_jezyk, denorms
):
    wydawnictwo_zwarte = pbn_rozdzial_z_autorem_z_dyscyplina

    assert wydawnictwo_zwarte.wydawnictwo_nadrzedne_id == wydawnictwo_nadrzedne.pk

    _zrob_wydawnictwo_pbn(
        wydawnictwo_zwarte, pbn_jezyk, rodzaj_pbn=const.RODZAJ_PBN_ROZDZIAL
    )

    WWW = "https://www.example.com/"
    WWW2 = "https://www.example2.com/"

    wydawnictwo_nadrzedne.public_www = WWW
    wydawnictwo_nadrzedne.save()

    wydawnictwo_zwarte.www = wydawnictwo_zwarte.public_www = None
    wydawnictwo_zwarte.wydawnictwo_nadrzedne = wydawnictwo_nadrzedne
    wydawnictwo_zwarte.save()

    res = WydawnictwoPBNAdapter(wydawnictwo_zwarte).pbn_get_json()
    assert res["publicUri"] == WWW

    wydawnictwo_zwarte.www = WWW2
    wydawnictwo_zwarte.save()

    assert wydawnictwo_zwarte.wydawnictwo_nadrzedne == wydawnictwo_nadrzedne

    res = WydawnictwoPBNAdapter(wydawnictwo_zwarte).pbn_get_json()
    assert res["publicUri"] == WWW2


@pytest.mark.django_db
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


@pytest.mark.django_db
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


@pytest.mark.django_db
def test_WydawnictwoPBNAdapter_autor_z_orcid_bez_dyscypliny_idzie_bez_id(
    praca_z_dyscyplina_pbn, jednostka, denorms
):
    pierwszy_autor = praca_z_dyscyplina_pbn.autorzy_set.first().autor
    pierwszy_autor.orcid = "123456"
    pierwszy_autor.save()

    autor_bez_dyscypliny = baker.make(
        Autor, imiona="Jan", nazwisko="Budnik", orcid="43567"
    )
    praca_z_dyscyplina_pbn.dodaj_autora(autor_bez_dyscypliny, jednostka, "Jan Budnik")

    res = WydawnictwoPBNAdapter(praca_z_dyscyplina_pbn).pbn_get_json()
    assert res["authors"][0].get("orcidId")
    assert not res["authors"][1].get("orcidId")


@pytest.mark.django_db
def test_WydawnictwoPBNAdapter_pod_redakcja_falsz(
    ksiazka, autor_jan_nowak, jednostka, denorms
):
    ksiazka.dodaj_autora(autor_jan_nowak, jednostka)
    assert WydawnictwoPBNAdapter(ksiazka).pod_redakcja() is False


@pytest.mark.django_db
def test_WydawnictwoPBNAdapter_pod_redakcja_prawda(
    ksiazka, autor_jan_nowak, jednostka, denorms
):
    ksiazka.dodaj_autora(autor_jan_nowak, jednostka, typ_odpowiedzialnosci_skrot="red.")
    assert WydawnictwoPBNAdapter(ksiazka).pod_redakcja() is True


@pytest.mark.django_db
def test_WydawnictwoPBNAdapter_slowa_kluczowe(pbn_wydawnictwo_zwarte_ksiazka):
    pbn_wydawnictwo_zwarte_ksiazka.slowa_kluczowe.add("test")
    pbn_wydawnictwo_zwarte_ksiazka.slowa_kluczowe.add("best")

    ret = WydawnictwoPBNAdapter(pbn_wydawnictwo_zwarte_ksiazka).pbn_get_json()
    assert "best" in ret["languageData"]["keywords"][0]["keywords"]


@pytest.mark.django_db
def test_WydawnictwoPBNAdapter_streszczenia(pbn_wydawnictwo_zwarte_ksiazka):
    pbn_wydawnictwo_zwarte_ksiazka.streszczenia.create(
        jezyk_streszczenia=None, streszczenie="123 test streszczenia"
    )
    ret = WydawnictwoPBNAdapter(pbn_wydawnictwo_zwarte_ksiazka).pbn_get_json()
    assert "test" in ret["languageData"]["abstracts"][0]["text"]


@pytest.mark.django_db
def test_WydawnictwoPBNAdapter_wydawnictwo_zwarte_strony(
    pbn_wydawnictwo_zwarte_ksiazka,
):
    pbn_wydawnictwo_zwarte_ksiazka.strony = "pincset"

    ret = WydawnictwoPBNAdapter(pbn_wydawnictwo_zwarte_ksiazka).pbn_get_json()
    assert "pagesFromTo" in ret


@pytest.mark.django_db
def test_WydawnictwoPBNAdapter_wydawnictwo_ciagle_strony(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina,
):
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina.strony = "pincset"
    ret = WydawnictwoPBNAdapter(
        pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ).pbn_get_json()
    assert "pagesFromTo" in ret


@pytest.mark.django_db
def test_WydawnictwoPBNAdapter_wydawnictwo_ciagle_zakres_stron(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina,
):
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina.szczegoly = "s. 20-30"
    ret = WydawnictwoPBNAdapter(
        pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ).pbn_get_json()
    assert "pagesFromTo" in ret


def encode_then_decode_json(in_json):
    return json.loads(json.dumps(in_json))


@pytest.mark.django_db
def test_WydawnictwoPBNAdapter_oplata_za_publikacje_platna(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina,
):
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina.opl_pub_amount = Decimal("50.4")
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina.opl_pub_research_potential = True

    ret = encode_then_decode_json(
        WydawnictwoPBNAdapter(
            pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
        ).pbn_get_json()
    )
    assert ret["fee"]["amount"] == "50.4"
    assert ret["fee"]["researchPotentialFinancialResources"]


@pytest.mark.django_db
def test_WydawnictwoPBNAdapter_oplata_za_publikacje_darmowa(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina,
):
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina.opl_pub_cost_free = True

    ret = encode_then_decode_json(
        WydawnictwoPBNAdapter(
            pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
        ).pbn_get_json()
    )
    assert ret["fee"]["amount"] == Decimal("0")
    assert ret["fee"]["costFreePublication"]
