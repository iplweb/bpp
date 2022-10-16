import json

import pytest
from django.urls import reverse

from fixtures import pbn_publication_json

from bpp.models import Autor_Dyscyplina, Uczelnia
from bpp.views.api import OstatniaJednostkaIDyscyplinaView, const
from bpp.views.api.pbn_get_by_parameter import GetPBNPublicationsByISBN
from bpp.views.api.pubmed import GetPubmedIDView, get_data_from_ncbi


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
