import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp import const
from bpp.models import Autor
from powiazania_autorow.models import AuthorConnection

TRASY = (
    "browse_autor_powiazania",
    "browse_autor_powiazania_3d",
    "browse_autor_powiazania_dane",
    "browse_autor_powiazania_siec",
    "browse_autor_powiazania_zrodla",
)


@pytest.fixture
def redaktor(django_user_model):
    user = django_user_model.objects.create_user(username="redaktor", password="x")
    grp = Group.objects.get_or_create(name=const.GR_WPROWADZANIE_DANYCH)[0]
    user.groups.add(grp)
    return user


@pytest.fixture
def zwykly(django_user_model):
    return django_user_model.objects.create_user(username="zwykly", password="x")


@pytest.fixture
def ukryty_status(uczelnia):
    from bpp.models import Status_Korekty, Ukryj_Status_Korekty

    status = baker.make(Status_Korekty, nazwa="przed korektą (test)")
    Ukryj_Status_Korekty.objects.create(
        uczelnia=uczelnia, status_korekty=status, podglad=True
    )
    return status


@pytest.fixture
def jawny_status():
    from bpp.models import Status_Korekty

    return baker.make(Status_Korekty, nazwa="po korekcie (test)")


def _ukryty_autor_z_sasiadem():
    autor = baker.make(Autor, imiona="Jan", nazwisko="Ukryty", pokazuj=False)
    sasiad = baker.make(Autor, imiona="Ewa", nazwisko="Jawna", pokazuj=True)
    AuthorConnection.objects.create(
        primary_author=autor, secondary_author=sasiad, shared_publications_count=3
    )
    return autor


@pytest.mark.django_db
@pytest.mark.parametrize("trasa", TRASY)
def test_ukryty_autor_404_dla_anonima(client, uczelnia, trasa):
    autor = _ukryty_autor_z_sasiadem()
    url = reverse(f"bpp:{trasa}", args=[autor.pk])
    assert client.get(url).status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("trasa", TRASY)
def test_ukryty_autor_404_dla_zwyklego_zalogowanego(client, uczelnia, zwykly, trasa):
    autor = _ukryty_autor_z_sasiadem()
    client.force_login(zwykly)
    url = reverse(f"bpp:{trasa}", args=[autor.pk])
    assert client.get(url).status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("trasa", TRASY)
def test_ukryty_autor_200_dla_redaktora(client, uczelnia, redaktor, trasa):
    autor = _ukryty_autor_z_sasiadem()
    client.force_login(redaktor)
    url = reverse(f"bpp:{trasa}", args=[autor.pk])
    assert client.get(url).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("trasa", TRASY)
def test_ukryty_autor_200_dla_superusera(admin_client, uczelnia, trasa):
    autor = _ukryty_autor_z_sasiadem()
    url = reverse(f"bpp:{trasa}", args=[autor.pk])
    assert admin_client.get(url).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("trasa", TRASY)
def test_ukryty_autor_wylaczona_siec_404_takze_dla_redaktora(
    client, uczelnia, redaktor, trasa
):
    autor = _ukryty_autor_z_sasiadem()
    autor.pokazuj_siec_powiazan = False
    autor.save()
    client.force_login(redaktor)
    url = reverse(f"bpp:{trasa}", args=[autor.pk])
    assert client.get(url).status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("trasa", TRASY)
def test_jawny_autor_200_dla_anonima(client, uczelnia, trasa):
    autor = baker.make(Autor, imiona="Imie", nazwisko="Nazwisko1", pokazuj=True)
    url = reverse(f"bpp:{trasa}", args=[autor.pk])
    assert client.get(url).status_code == 200


def _praca(status, autorzy, jednostka, **kw):
    from bpp.models import Wydawnictwo_Ciagle

    w = baker.make(Wydawnictwo_Ciagle, status_korekty=status, **kw)
    for a in autorzy:
        w.dodaj_autora(a, jednostka)
    return w


@pytest.mark.django_db
def test_metryki_bez_prac_o_ukrytym_statusie(
    client,
    redaktor,
    jednostka,
    typy_odpowiedzialnosci,
    ukryty_status,
    jawny_status,
):
    centrum = baker.make(Autor, imiona="Imie", nazwisko="Nazwisko2", pokazuj=True)
    sasiad = baker.make(Autor, imiona="Imie", nazwisko="Nazwisko3", pokazuj=True)
    _praca(jawny_status, [centrum, sasiad], jednostka, rok=2020, impact_factor=1)
    _praca(ukryty_status, [centrum, sasiad], jednostka, rok=2021, impact_factor=5)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=sasiad, shared_publications_count=2
    )

    url = reverse("bpp:browse_autor_powiazania_dane", args=[centrum.pk])

    data = client.get(url).json()
    assert data["center"]["total_works"] == 1
    assert data["center"]["if_sum"] == 1.0
    assert data["neighbors"][0]["total_works"] == 1

    url_siec = reverse("bpp:browse_autor_powiazania_siec", args=[centrum.pk])
    siec = client.get(url_siec, {"depth": 1}).json()
    assert siec["rok_max"] == 2020
    wezly = {n["id"]: n for n in siec["nodes"]}
    assert wezly[centrum.pk]["total_works"] == 1

    client.force_login(redaktor)
    data = client.get(url).json()
    assert data["center"]["total_works"] == 2
    assert data["center"]["if_sum"] == 6.0
    siec = client.get(url_siec, {"depth": 1}).json()
    assert siec["rok_max"] == 2021


@pytest.mark.django_db
def test_lista_zrodel_bez_prac_o_ukrytym_statusie(
    client,
    redaktor,
    jednostka,
    typy_odpowiedzialnosci,
    ukryty_status,
    jawny_status,
):
    from bpp.models import Zrodlo

    centrum = baker.make(Autor, imiona="Imie", nazwisko="Nazwisko4", pokazuj=True)
    zrodlo = baker.make(Zrodlo, nazwa="Czasopismo testowe")
    for rok in range(2010, 2014):
        _praca(jawny_status, [centrum], jednostka, rok=rok, zrodlo=zrodlo)
    _praca(ukryty_status, [centrum], jednostka, rok=2015, zrodlo=zrodlo)

    url = reverse("bpp:browse_autor_powiazania_zrodla", args=[centrum.pk])

    zrodla = client.get(url).json()["zrodla"]
    assert [(z["id"], z["n"]) for z in zrodla] == [(zrodlo.pk, 4)]

    client.force_login(redaktor)
    zrodla = client.get(url).json()["zrodla"]
    assert [(z["id"], z["n"]) for z in zrodla] == [(zrodlo.pk, 5)]


@pytest.mark.django_db
def test_lista_zrodel_ukryte_ponizej_progu_dla_anonima(
    client,
    redaktor,
    jednostka,
    typy_odpowiedzialnosci,
    ukryty_status,
):
    from bpp.models import Zrodlo

    centrum = baker.make(Autor, imiona="Imie", nazwisko="Nazwisko5", pokazuj=True)
    zrodlo = baker.make(Zrodlo, nazwa="Czasopismo ukryte")
    for rok in range(2010, 2014):
        _praca(ukryty_status, [centrum], jednostka, rok=rok, zrodlo=zrodlo)

    url = reverse("bpp:browse_autor_powiazania_zrodla", args=[centrum.pk])
    assert client.get(url).json()["zrodla"] == []

    client.force_login(redaktor)
    zrodla = client.get(url).json()["zrodla"]
    assert [z["id"] for z in zrodla] == [zrodlo.pk]


@pytest.mark.django_db
def test_krawedzie_z_filtrem_bez_prac_o_ukrytym_statusie(
    client,
    redaktor,
    jednostka,
    typy_odpowiedzialnosci,
    ukryty_status,
    jawny_status,
):
    centrum = baker.make(Autor, imiona="Imie", nazwisko="Nazwisko6", pokazuj=True)
    jawny = baker.make(Autor, imiona="Imie", nazwisko="Nazwisko7", pokazuj=True)
    przez_ukryta = baker.make(Autor, imiona="Imie", nazwisko="Nazwisko8", pokazuj=True)
    _praca(jawny_status, [centrum, jawny], jednostka, rok=2020)
    _praca(ukryty_status, [centrum, przez_ukryta], jednostka, rok=2020)
    filtr = {"rok_od": 2018, "rok_do": 2025, "depth": 1}

    url_siec = reverse("bpp:browse_autor_powiazania_siec", args=[centrum.pk])
    url_dane = reverse("bpp:browse_autor_powiazania_dane", args=[centrum.pk])

    ids = {n["id"] for n in client.get(url_siec, filtr).json()["nodes"]}
    assert jawny.pk in ids
    assert przez_ukryta.pk not in ids
    ids = {n["id"] for n in client.get(url_dane, filtr).json()["neighbors"]}
    assert ids == {jawny.pk}

    client.force_login(redaktor)
    ids = {n["id"] for n in client.get(url_siec, filtr).json()["nodes"]}
    assert {jawny.pk, przez_ukryta.pk} <= ids
    ids = {n["id"] for n in client.get(url_dane, filtr).json()["neighbors"]}
    assert ids == {jawny.pk, przez_ukryta.pk}


@pytest.mark.django_db
def test_krawedzie_poprzeczne_z_filtrem_bez_prac_o_ukrytym_statusie(
    client,
    redaktor,
    jednostka,
    typy_odpowiedzialnosci,
    ukryty_status,
    jawny_status,
):
    centrum = baker.make(Autor, imiona="Imie", nazwisko="Nazwisko9", pokazuj=True)
    a = baker.make(Autor, imiona="Imie", nazwisko="Nazwisko10", pokazuj=True)
    b = baker.make(Autor, imiona="Imie", nazwisko="Nazwisko11", pokazuj=True)
    _praca(jawny_status, [centrum, a], jednostka, rok=2020)
    _praca(jawny_status, [centrum, b], jednostka, rok=2020)
    _praca(ukryty_status, [a, b], jednostka, rok=2020)
    filtr = {"rok_od": 2018, "rok_do": 2025, "depth": 1}

    url = reverse("bpp:browse_autor_powiazania_siec", args=[centrum.pk])

    def pary(resp):
        return {tuple(sorted((e["source"], e["target"]))) for e in resp["extra_edges"]}

    assert tuple(sorted((a.pk, b.pk))) not in pary(client.get(url, filtr).json())

    client.force_login(redaktor)
    assert tuple(sorted((a.pk, b.pk))) in pary(client.get(url, filtr).json())
