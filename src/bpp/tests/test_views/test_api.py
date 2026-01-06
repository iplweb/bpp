import json
from collections import namedtuple

import pytest
from django.urls import reverse

from bpp.models import Autor_Dyscyplina, Typ_Odpowiedzialnosci, Uczelnia
from bpp.models.zrodlo import Punktacja_Zrodla
from bpp.tests.util import CURRENT_YEAR, any_autor, any_habilitacja, any_zrodlo
from bpp.views.api import (
    OstatniaJednostkaIDyscyplinaView,
    PunktacjaZrodlaView,
    RokHabilitacjiView,
    UploadPunktacjaZrodlaView,
    const,
)
from bpp.views.api.pbn_get_by_parameter import GetPBNPublicationsByISBN
from bpp.views.api.pubmed import GetPubmedIDView, get_data_from_ncbi
from fixtures import pbn_publication_json


def test_get_data_from_ncbi(mocker):
    query = mocker.patch("pymed.PubMed.query")
    query.return_value = "123"

    res = get_data_from_ncbi("foobar")
    assert res == ["1", "2", "3"]


def test_GetPubmedIDView_post_nie_ma_tytulu(rf):
    v = GetPubmedIDView()

    req = rf.get("/", data={"t": ""})
    res = json.loads(v.post(req).content)
    assert res == dict(error=const.PUBMED_BRAK_PARAMETRU)

    req = rf.get("/", data={"t": "    "})
    res = json.loads(v.post(req).content)
    assert res == dict(error=const.PUBMED_BRAK_PARAMETRU)


def test_GetPubmedIDView_post_brak_rezultaut(rf, mocker):
    query = mocker.patch("pymed.PubMed.query")
    query.return_value = []

    v = GetPubmedIDView()

    req = rf.post("/", data={"t": "razd dwa trzy test"})
    res = json.loads(v.post(req).content)
    assert res == dict(error=const.PUBMED_PO_TYTULE_BRAK)


def test_GetPubmedIDView_post_wiele_rezultatow(rf, mocker):
    query = mocker.patch("pymed.PubMed.query")
    query.return_value = ["1", "2", "3"]

    v = GetPubmedIDView()

    req = rf.post("/", data={"t": "razd dwa trzy test"})
    res = json.loads(v.post(req).content)
    assert res == dict(error=const.PUBMED_PO_TYTULE_WIELE)


def test_GetPubmedIDView_post_jeden_rezultat(rf, mocker):
    class FakePraca:
        pubmed_id = "lel"
        doi = "lol"
        pmc_id = "pmc_id"
        title = "none"

    query = mocker.patch("pymed.PubMed.query")
    query.return_value = [FakePraca()]

    v = GetPubmedIDView()

    req = rf.post("/", data={"t": "razd dwa trzy test"})
    res = json.loads(v.post(req).content)
    assert res["doi"] == "lol"


@pytest.mark.django_db
def test_GetPBNPublicationsByISBN_jedna_praca(
    rf, pbn_uczelnia, pbn_client, admin_user, wydawnictwo_nadrzedne
):
    ROK = 123
    ISBN = "123"
    UID_REKORDU = "foobar"
    TYTUL_REKORDU = "Jakis tytul"

    orig = Uczelnia.objects.get_default

    pub1 = pbn_publication_json(
        mongoId=UID_REKORDU, year=ROK, isbn=ISBN, title=TYTUL_REKORDU
    )

    wydawnictwo_nadrzedne.isbn = ISBN
    wydawnictwo_nadrzedne.rok = ROK
    wydawnictwo_nadrzedne.tytul_oryginalny = TYTUL_REKORDU
    wydawnictwo_nadrzedne.save()

    req = rf.post("/", data=dict(t=ISBN, rok="2021"))
    req.user = admin_user

    pbn_client.transport.return_values["/api/v1/search/publications?size=10"] = [pub1]
    pbn_client.transport.return_values[f"/api/v1/publications/id/{UID_REKORDU}"] = pub1
    try:
        Uczelnia.objects.get_default = lambda *args, **kw: pbn_uczelnia

        res = GetPBNPublicationsByISBN(request=req).post(req)
    finally:
        Uczelnia.objects.get_default = orig

    assert json.loads(res.content)["id"] == UID_REKORDU


@pytest.mark.django_db
def test_GetPBNPublicationsByISBN_wiele_isbn(
    rf, pbn_uczelnia, pbn_client, admin_user, wydawnictwo_nadrzedne
):
    ROK = 123
    ISBN = "123"
    UID_REKORDU = "foobar"
    TYTUL_REKORDU = "Jakis tytul"

    orig = Uczelnia.objects.get_default

    pub1 = pbn_publication_json(
        mongoId=UID_REKORDU, year=ROK, isbn=ISBN, title=TYTUL_REKORDU
    )
    pub2 = pbn_publication_json(
        mongoId=UID_REKORDU + "2", year=ROK, isbn=ISBN, title=TYTUL_REKORDU
    )

    wydawnictwo_nadrzedne.isbn = ISBN
    wydawnictwo_nadrzedne.rok = ROK
    wydawnictwo_nadrzedne.tytul_oryginalny = TYTUL_REKORDU
    wydawnictwo_nadrzedne.save()

    req = rf.post("/", data=dict(t=ISBN, rok="2021"))
    req.user = admin_user

    pbn_client.transport.return_values["/api/v1/search/publications?size=10"] = [
        pub1,
        pub2,
    ]
    pbn_client.transport.return_values[f"/api/v1/publications/id/{UID_REKORDU}"] = pub1
    pbn_client.transport.return_values[f"/api/v1/publications/id/{UID_REKORDU}2"] = pub2

    try:
        Uczelnia.objects.get_default = lambda *args, **kw: pbn_uczelnia

        res = GetPBNPublicationsByISBN(request=req).post(req)
    finally:
        Uczelnia.objects.get_default = orig

    assert json.loads(res.content)["id"] == UID_REKORDU


@pytest.fixture
def ojv():
    return OstatniaJednostkaIDyscyplinaView()


def test_ostatnia_jednostka_view(autor, jednostka, rf, ojv, dyscyplina1):
    jednostka.dodaj_autora(autor)

    Autor_Dyscyplina.objects.create(
        rok=2000, autor=autor, dyscyplina_naukowa=dyscyplina1
    )

    fr = rf.post("/", data=dict(autor_id=autor.pk, rok=2000))
    res = ojv.post(fr)
    res = json.loads(res.content)
    assert "jednostka_id" in res
    assert "dyscyplina_id" in res


def test_ostatnia_jednostka_view_dwie_dysc(
    autor, jednostka, rf, ojv, dyscyplina1, dyscyplina2
):
    jednostka.dodaj_autora(autor)

    Autor_Dyscyplina.objects.create(
        rok=2000,
        autor=autor,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2,
    )

    fr = rf.post("/", data=dict(autor_id=autor.pk, rok=2000))
    res = ojv.post(fr)
    res = json.loads(res.content)
    assert "jednostka_id" in res
    assert "dyscyplina_id" not in res


def test_ostatnia_jednostka_view_rok_empty(autor, jednostka, rf, ojv):
    jednostka.dodaj_autora(autor)

    fr = rf.post("/", data=dict(autor_id=autor.pk, rok=""))
    res = ojv.post(fr)
    res = json.loads(res.content)
    assert "jednostka_id" in res
    assert "dyscyplina_id" not in res


def test_ostatnia_jednostka_errors_autor_null(rf, ojv):
    fr = rf.post("/", data=dict(autor_id=""))
    res = ojv.post(fr)
    assert json.loads(res.content)["status"] == "error"


@pytest.mark.django_db
def test_ostatnia_jednostka_errors_autor_404(rf, ojv):
    fr = rf.post("/", data=dict(autor_id=10))
    res = ojv.post(fr)
    assert json.loads(res.content)["status"] == "error"


@pytest.mark.django_db
def test_ostatnia_jednostka_errors_autor_404_2(rf, ojv):
    fr = rf.post("/", data=dict(autor_id="heyyy"))
    res = ojv.post(fr)
    assert json.loads(res.content)["status"] == "error"


def test_ostatnia_jednostka_errors_autor_bez_dysc(rf, ojv, autor):
    fr = rf.post("/", data=dict(autor_id=autor.pk))
    res = ojv.post(fr)

    res = json.loads(res.content)
    assert res["jednostka_id"] is None
    assert res["nazwa"] is None
    assert res["status"] == "ok"


def test_ustaw_orcid_autora(csrf_exempt_django_admin_app, autor_jan_kowalski):
    ORCID = "1" * 19

    assert autor_jan_kowalski.orcid != ORCID
    csrf_exempt_django_admin_app.post(
        reverse("bpp:api_ustaw_orcid"),
        params={"autor": autor_jan_kowalski.pk, "orcid": ORCID},
    )

    autor_jan_kowalski.refresh_from_db()
    assert autor_jan_kowalski.orcid == ORCID


# =============================================================================
# Testy przeniesione z tests_legacy/test_views/test_api.py
# =============================================================================

FakeRequest = namedtuple("FakeRequest", ["POST"])


@pytest.mark.django_db
def test_rok_habilitacji_view():
    Typ_Odpowiedzialnosci.objects.get_or_create(skrot="aut.", nazwa="autor")

    a = any_autor()
    h = any_habilitacja(tytul_oryginalny="Testowa habilitacja", rok=CURRENT_YEAR)
    h.autor = a
    h.save()

    request = FakeRequest({"autor_pk": a.pk})

    rhv = RokHabilitacjiView()

    res = rhv.post(request)
    assert res.status_code == 200
    assert str(CURRENT_YEAR) in res.content.decode()
    assert json.loads(res.content)["rok"] == CURRENT_YEAR

    h.delete()
    res = rhv.post(request)
    assert res.status_code == 404
    assert "Habilitacja" in res.content.decode()

    a.delete()
    res = rhv.post(request)
    assert res.status_code == 404
    assert "Autor" in res.content.decode()


@pytest.mark.django_db
def test_punktacja_zrodla_view():
    z = any_zrodlo()
    Punktacja_Zrodla.objects.create(zrodlo=z, rok=CURRENT_YEAR, impact_factor=50)

    res = PunktacjaZrodlaView().post(None, z.pk, CURRENT_YEAR)
    analyze = json.loads(res.content.decode(res.charset))
    assert analyze["impact_factor"] == "50.000"

    res = PunktacjaZrodlaView().post(None, z.pk, CURRENT_YEAR + 100)
    assert res.status_code == 404
    assert "Rok" in res.content.decode()


@pytest.mark.django_db
def test_punktacja_zrodla_view_404():
    res = PunktacjaZrodlaView().post(None, 1, CURRENT_YEAR)
    assert res.status_code == 404
    assert "Zrodlo" in res.content.decode()


@pytest.mark.django_db
def test_upload_punktacja_zrodla_404():
    res = UploadPunktacjaZrodlaView().post(None, 1, CURRENT_YEAR)
    assert res.status_code == 404
    assert "Zrodlo" in res.content.decode()


@pytest.mark.django_db
def test_upload_punktacja_zrodla_simple():
    z = any_zrodlo()
    fr = FakeRequest(dict(impact_factor="50.00"))
    UploadPunktacjaZrodlaView().post(fr, z.pk, CURRENT_YEAR)
    assert Punktacja_Zrodla.objects.count() == 1
    assert Punktacja_Zrodla.objects.all()[0].impact_factor == 50


@pytest.mark.django_db
def test_upload_punktacja_zrodla_overwrite():
    z = any_zrodlo()
    Punktacja_Zrodla.objects.create(rok=CURRENT_YEAR, zrodlo=z, impact_factor=50)
    fr = FakeRequest(dict(impact_factor="60.00", punkty_kbn="60"))
    res = UploadPunktacjaZrodlaView().post(fr, z.pk, CURRENT_YEAR)
    assert res.status_code == 200
    assert "exists" in res.content.decode()

    fr = FakeRequest(dict(impact_factor="60.00", overwrite="1"))
    UploadPunktacjaZrodlaView().post(fr, z.pk, CURRENT_YEAR)
    assert Punktacja_Zrodla.objects.count() == 1
    assert Punktacja_Zrodla.objects.all()[0].impact_factor == 60
