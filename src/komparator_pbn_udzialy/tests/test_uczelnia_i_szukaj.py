"""„Problemy PBN”: oświadczenia tylko bieżącej uczelni (instalacja
wielouczelniana) i wyszukiwanie po autorze BPP (recenzja PR 1180)."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker

from komparator_pbn_udzialy.models import BrakAutoraWPublikacji, RozbieznoscDyscyplinPBN

URL = "/komparator-pbn-udzialy/2026-2030/"


def _oswiadczenie(instytucja, tytul="Praca"):
    return baker.make(
        "pbn_api.OswiadczenieInstytucji",
        institutionId=instytucja,
        personId=baker.make("pbn_api.Scientist", name="Jan", lastName="Pebeenowski"),
        publicationId=baker.make("pbn_api.Publication", year=2027, title=tytul),
    )


def _brak(instytucja, tytul):
    osw = _oswiadczenie(instytucja, tytul)
    return BrakAutoraWPublikacji.objects.create(
        pbn_scientist=osw.personId,
        oswiadczenie_instytucji=osw,
        typ=BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP,
    )


def _rozbieznosc(instytucja, nazwisko, imiona="Anna", model="bpp.Wydawnictwo_Ciagle"):
    from bpp.models import Uczelnia

    # Jednostka istniejącej uczelni: bez tego ``baker`` zakłada do każdej
    # jednostki nową uczelnię i instalacja „robi się” wielouczelniana.
    wa = baker.make(
        f"{model}_Autor",
        rekord=baker.make(model, tytul_oryginalny=f"Praca {nazwisko}", rok=2027),
        autor=baker.make("bpp.Autor", nazwisko=nazwisko, imiona=imiona),
        jednostka=baker.make("bpp.Jednostka", uczelnia=Uczelnia.objects.first()),
    )
    return RozbieznoscDyscyplinPBN.objects.create(
        content_type=ContentType.objects.get_for_model(wa),
        object_id=wa.pk,
        oswiadczenie_instytucji=_oswiadczenie(instytucja, f"Tytuł PBN {nazwisko}"),
        dyscyplina_bpp=baker.make("bpp.Dyscyplina_Naukowa"),
        dyscyplina_pbn=baker.make("bpp.Dyscyplina_Naukowa"),
    )


def _obiekty(response):
    return {p.obj for p in response.context["problemy"]}


@pytest.fixture
def instytucje(db):
    return (
        baker.make("pbn_api.Institution", mongoId="inst-1"),
        baker.make("pbn_api.Institution", mongoId="inst-2"),
    )


@pytest.fixture
def dwie_uczelnie(uczelnia1, uczelnia2, instytucje, settings):
    settings.ALLOWED_HOSTS = ["*"]
    uczelnia1.pbn_uid, uczelnia2.pbn_uid = instytucje
    uczelnia1.save()
    uczelnia2.save()
    return uczelnia1, uczelnia2


def test_wielouczelniana_lista_statystyki_i_szczegoly_tylko_swojej_uczelni(
    client_with_group, dwie_uczelnie, instytucje
):
    """Dawniej obie uczelnie widziały na liście i w kafelkach oświadczenia
    wszystkich instytucji z lustra PBN."""
    moj_brak = _brak(instytucje[0], "Moja praca")
    moja_rozb = _rozbieznosc(instytucje[0], "Mojski")
    cudzy_brak = _brak(instytucje[1], "Cudza praca")
    cudza_rozb = _rozbieznosc(instytucje[1], "Cudzy")
    u1 = {"HTTP_HOST": "uczelnia1.localhost"}
    u2 = {"HTTP_HOST": "uczelnia2.localhost"}

    moje = client_with_group.get(URL, **u1)
    cudze = client_with_group.get(URL, **u2)

    assert _obiekty(moje) == {moj_brak, moja_rozb}
    assert _obiekty(cudze) == {cudzy_brak, cudza_rozb}
    for response in (moje, cudze):
        assert response.context["total_count"] == 2
        assert response.context["brakujacy_total"] == 1
        assert response.context["rozbieznosci_total"] == 1
    # „Szukaj” też nie wychodzi poza uczelnię
    assert _obiekty(client_with_group.get(URL, {"search": "praca"}, **u1)) == {moj_brak}

    # strony szczegółów: swoje 200, cudze 404
    def szczegoly(obj, host):
        nazwa = (
            "missing_autor_detail"
            if isinstance(obj, BrakAutoraWPublikacji)
            else "detail"
        )
        url = reverse(f"komparator_pbn_udzialy:{nazwa}", args=[obj.pk])
        return client_with_group.get(url, **host).status_code

    assert szczegoly(moj_brak, u1) == 200
    assert szczegoly(moja_rozb, u1) == 200
    assert szczegoly(cudzy_brak, u1) == 404
    assert szczegoly(cudza_rozb, u1) == 404


def test_wielouczelniana_bez_identyfikatora_pbn_komunikat_zamiast_listy(
    client_with_group, uczelnia1, uczelnia2, instytucje, settings
):
    """Uczelnia bez „Odpowiednika w PBN” nie dostaje listy (nie wiadomo, które
    oświadczenia są jej) — zamiast pustej tabeli i zer w kafelkach widzi
    komunikat, gdzie to ustawić. To samo na stronach szczegółów."""
    settings.ALLOWED_HOSTS = ["*"]
    host = {"HTTP_HOST": "uczelnia1.localhost"}
    cudzy = _brak(instytucje[1], "Cudza praca")
    cudza = _rozbieznosc(instytucje[1], "Obcowski")
    adresy = [
        URL,
        URL + "?search=praca",
        reverse("komparator_pbn_udzialy:missing_autor_detail", args=[cudzy.pk]),
        reverse("komparator_pbn_udzialy:detail", args=[cudza.pk]),
    ]

    for adres in adresy:
        response = client_with_group.get(adres, **host)
        tresc = response.content.decode()

        assert response.status_code == 200, adres
        assert "nie ma ustawionego identyfikatora PBN" in tresc
        assert "Uczelnia Pierwsza" in tresc
        assert "Odpowiednik w PBN" in tresc
        assert "Cudza praca" not in tresc and "Obcowski" not in tresc
        assert "Statystyki" not in tresc
        assert "problemy" not in (response.context or {})


def test_wielouczelniana_adres_bez_uczelni_komunikat(
    client_with_group, uczelnia1, uczelnia2, instytucje, settings
):
    """Adres nieprzypisany do żadnej uczelni: też komunikat, nie cudze dane."""
    settings.ALLOWED_HOSTS = ["*"]
    settings.SITE_ID = None
    _brak(instytucje[1], "Cudza praca")

    tresc = client_with_group.get(URL, HTTP_HOST="inny.localhost").content.decode()

    assert "Nie udało się ustalić uczelni" in tresc
    assert "Cudza praca" not in tresc


def test_komunikat_tylko_dla_uprawnionych(client, uczelnia1, uczelnia2, settings):
    """Strażnik: komunikat nie zastępuje kontroli dostępu."""
    settings.ALLOWED_HOSTS = ["*"]

    response = client.get(URL, HTTP_HOST="uczelnia1.localhost")

    assert response.status_code in (302, 403)


@pytest.mark.parametrize("z_identyfikatorem", [True, False])
def test_jedna_uczelnia_widzi_wszystko_jak_dotad(
    client_with_group, uczelnia, instytucje, z_identyfikatorem
):
    """Strażnik: w instalacji z jedną uczelnią nic się nie zmienia — widać
    wszystkie oświadczenia, także gdy uczelnia nie ma identyfikatora PBN albo
    oświadczenie ma inną instytucję."""
    if z_identyfikatorem:
        uczelnia.pbn_uid = instytucje[0]
        uczelnia.save()
    swoj = _brak(instytucje[0], "Praca A")
    inna_instytucja = _rozbieznosc(instytucje[1], "Kowalska")

    response = client_with_group.get(URL)

    assert _obiekty(response) == {swoj, inna_instytucja}
    assert response.context["total_count"] == 2
    url = reverse("komparator_pbn_udzialy:detail", args=[inna_instytucja.pk])
    assert client_with_group.get(url).status_code == 200


@pytest.mark.parametrize("model", ["bpp.Wydawnictwo_Ciagle", "bpp.Wydawnictwo_Zwarte"])
def test_szukaj_znajduje_rozbieznosc_po_autorze_bpp(
    client_with_group, uczelnia, instytucje, model
):
    """W wierszu rozbieżności dyscyplin widać autora BPP — „Szukaj” po jego
    nazwisku albo imieniu ma ten wiersz znaleźć (dawniej szukało tylko po
    tytule i dyscyplinach)."""
    szukana = _rozbieznosc(instytucje[0], "Wyszukiwalska", "Bogumiła", model=model)
    _rozbieznosc(instytucje[0], "Inny", model=model)
    brak = _brak(instytucje[0], "Praca o czymś")

    assert _obiekty(client_with_group.get(URL, {"search": "wyszukiwal"})) == {szukana}
    assert _obiekty(client_with_group.get(URL, {"search": "bogumi"})) == {szukana}
    # strażnik: brakujący autorzy nadal po nazwisku naukowca z PBN i tytule
    assert _obiekty(client_with_group.get(URL, {"search": "pebeenowski"})) == {brak}
    assert _obiekty(client_with_group.get(URL, {"search": "o czymś"})) == {brak}
