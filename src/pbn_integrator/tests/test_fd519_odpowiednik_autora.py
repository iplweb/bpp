"""FD#519 — przycisk „Pobierz z PBN” w edycji autora.

ORCID → pewny odpowiednik (także pobrany z serwera PBN); bez ORCID — imię
i nazwisko, a przy kilku kandydatach lista do wyboru z osobami z profilu
instytucji na początku. Testy bez sieci.
"""

import json

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor
from pbn_api.models import OsobaZInstytucji, Scientist
from pbn_integrator.models import PobieranieOdpowiednikowPBN
from pbn_integrator.utils.odpowiednik_autora import (
    STATUS_BRAK,
    STATUS_DO_WYBORU,
    STATUS_PEWNY,
    szukaj_odpowiednika_autora,
)

OSOBA_1 = "5e709189878c28a04737dc71"
OSOBA_2 = "5e709189878c28a04737dc72"
OSOBA_3 = "5e709189878c28a04737dc73"
ORCID = "0000-0002-1825-0097"


def _osoba(pk, nazwisko, imiona, *, orcid=None, z_instytucji=False):
    obiekt = {"lastName": nazwisko, "name": imiona}
    if orcid:
        obiekt["orcid"] = orcid
    osoba = baker.make(
        Scientist,
        mongoId=pk,
        status="ACTIVE",
        versions=[{"current": True, "object": obiekt}],
    )
    if z_instytucji:
        baker.make(
            OsobaZInstytucji, personId=osoba, firstName=imiona, lastName=nazwisko
        )
    return osoba


def _autor(**kw):
    kw.setdefault("nazwisko", "Kowalski")
    kw.setdefault("imiona", "Jan")
    return baker.make(Autor, pbn_uid=None, **kw)


class KlientTylkoOrcid:
    """Atrapa klienta PBN: zna wyłącznie szukanie osoby po ORCID. Każde
    inne wywołanie (np. wysyłka) kończy się ``AttributeError``."""

    def __init__(self, osoby):
        self.osoby = osoby
        self.zapytania = []

    def get_person_by_orcid(self, orcid):
        self.zapytania.append(orcid)
        return self.osoby


@pytest.mark.django_db
def test_autor_z_orcid_dostaje_pewny_odpowiednik(uczelnia):
    _osoba(OSOBA_1, "Kowalski", "Jan", orcid=ORCID)
    _osoba(OSOBA_2, "Kowalski", "Jan")
    autor = _autor(orcid=ORCID)

    wynik = szukaj_odpowiednika_autora(autor, uczelnia=uczelnia)

    assert wynik.status == STATUS_PEWNY
    assert wynik.kandydaci[0]["id"] == OSOBA_1
    assert "ORCID" in wynik.komunikat
    autor.refresh_from_db()
    assert autor.pbn_uid_id is None  # szukanie niczego nie zapisuje


@pytest.mark.django_db
def test_orcid_i_profil_instytucji_wskazuja_rozne_osoby(uczelnia):
    """Sprzeczne wskazania nigdy nie są rozstrzygane automatycznie."""
    _osoba(OSOBA_1, "Kowalski", "Jan", orcid=ORCID)
    _osoba(OSOBA_2, "Kowalski", "Jan", z_instytucji=True)

    wynik = szukaj_odpowiednika_autora(_autor(orcid=ORCID), uczelnia=uczelnia)

    assert wynik.status == STATUS_DO_WYBORU
    # Zgodny ORCID zawsze na górze, dopiero potem osoby z profilu instytucji.
    assert [k["id"] for k in wynik.kandydaci] == [OSOBA_1, OSOBA_2]
    assert "zgodny ORCID" in wynik.kandydaci[0]["opis"]
    assert [k["oficjalny"] for k in wynik.kandydaci] == [False, True]


@pytest.mark.django_db
def test_orcid_spoza_lokalnej_kopii_jest_pobierany_z_serwera_pbn(uczelnia):
    klient = KlientTylkoOrcid(
        [
            {
                "mongoId": OSOBA_1,
                "status": "ACTIVE",
                "verificationLevel": "x",
                "verified": True,
                "versions": [
                    {
                        "current": True,
                        "object": {
                            "lastName": "Kowalski",
                            "name": "Jan",
                            "orcid": ORCID,
                        },
                    }
                ],
            }
        ]
    )
    autor = _autor(orcid=ORCID)

    wynik = szukaj_odpowiednika_autora(autor, uczelnia=uczelnia, klient=lambda: klient)

    assert klient.zapytania == [ORCID]
    assert Scientist.objects.filter(pk=OSOBA_1).exists()
    assert wynik.status == STATUS_PEWNY
    assert wynik.kandydaci[0]["id"] == OSOBA_1


@pytest.mark.django_db
def test_orcid_znany_lokalnie_nie_pyta_serwera(uczelnia):
    _osoba(OSOBA_1, "Kowalski", "Jan", orcid=ORCID)
    klient = KlientTylkoOrcid([])

    szukaj_odpowiednika_autora(
        _autor(orcid=ORCID), uczelnia=uczelnia, klient=lambda: klient
    )

    assert klient.zapytania == []


@pytest.mark.django_db
def test_bez_orcid_lista_do_wyboru_oficjalni_pierwsi(uczelnia):
    _osoba(OSOBA_1, "Kowalski", "Jan")
    _osoba(OSOBA_2, "Kowalski", "Jan", z_instytucji=True)
    _osoba(OSOBA_3, "Kowalski", "Jan Maria")
    _osoba("5e709189878c28a04737dc7f", "Kowalski", "Piotr", z_instytucji=True)

    wynik = szukaj_odpowiednika_autora(_autor(), uczelnia=uczelnia)

    assert wynik.status == STATUS_DO_WYBORU
    assert [k["id"] for k in wynik.kandydaci][0] == OSOBA_2
    assert {k["id"] for k in wynik.kandydaci} == {OSOBA_1, OSOBA_2, OSOBA_3}
    assert [k["oficjalny"] for k in wynik.kandydaci] == [True, False, False]
    assert "profilu instytucji" in wynik.kandydaci[0]["opis"]


@pytest.mark.django_db
def test_jedyny_imiennik_z_instytucji_nie_jest_ustawiany_bez_pytania(uczelnia):
    """Samo imię i nazwisko to za mało na automat — zawsze wybór redaktora."""
    _osoba(OSOBA_1, "Kowalski", "Jan", z_instytucji=True)

    wynik = szukaj_odpowiednika_autora(_autor(), uczelnia=uczelnia)

    assert wynik.status == STATUS_DO_WYBORU
    assert [k["id"] for k in wynik.kandydaci] == [OSOBA_1]


@pytest.mark.django_db
def test_osoba_przypisana_do_innego_autora_jest_oznaczona(uczelnia):
    osoba = _osoba(OSOBA_1, "Kowalski", "Jan", orcid=ORCID)
    inny = baker.make(Autor, nazwisko="Kowalski", imiona="Jan", pbn_uid=osoba)

    wynik = szukaj_odpowiednika_autora(_autor(orcid=ORCID), uczelnia=uczelnia)

    assert wynik.status == STATUS_DO_WYBORU
    assert f"ID {inny.pk}" in wynik.kandydaci[0]["zajety"]
    assert "duplikat" in wynik.komunikat


@pytest.mark.django_db
def test_brak_kandydatow(uczelnia):
    wynik = szukaj_odpowiednika_autora(_autor(orcid=ORCID), uczelnia=uczelnia)

    assert wynik.status == STATUS_BRAK
    assert wynik.kandydaci == []
    assert ORCID in wynik.komunikat


def _post(admin_client, **dane):
    odp = admin_client.post(reverse("bpp:api_pobierz_z_pbn_autora"), data=dane)
    assert odp.status_code == 200
    return json.loads(odp.content)


@pytest.mark.django_db
def test_widok_uzywa_wartosci_z_formularza(admin_client, uczelnia):
    """Redaktor wpisał ORCID i od razu klika przycisk — liczy się to, co
    jest w formularzu, nie to, co zapisane."""
    _osoba(OSOBA_1, "Kowalski", "Jan", orcid=ORCID)
    autor = _autor(orcid=None)

    res = _post(
        admin_client,
        pk=autor.pk,
        imiona="Jan",
        nazwisko="Kowalski",
        orcid=ORCID,
    )

    assert res["status"] == STATUS_PEWNY
    assert res["id"] == OSOBA_1
    autor.refresh_from_db()
    assert autor.pbn_uid_id is None
    assert autor.orcid is None


@pytest.mark.django_db
def test_widok_dziala_dla_niezapisanego_autora_i_pustych_pol(admin_client, uczelnia):
    _osoba(OSOBA_1, "Nowak", "Anna", z_instytucji=True)

    nowy = _post(admin_client, pk="", imiona="Anna", nazwisko="Nowak")
    pusty = _post(admin_client, pk="", imiona="", nazwisko="Nowak")

    assert nowy["status"] == STATUS_DO_WYBORU
    assert nowy["kandydaci"][0]["id"] == OSOBA_1
    assert "id" not in nowy
    assert pusty["status"] == "puste"
    assert "Uzupełnij ORCID" in pusty["komunikat"]


# --- akcja grupowa na liście autorów -----------------------------------------


@pytest.mark.django_db
def test_akcja_dla_autorow_ustawia_tylko_pewne(
    admin_client, admin_user, uczelnia, django_capture_on_commit_callbacks
):
    baker.make(
        Scientist,
        mongoId=OSOBA_1,
        status="ACTIVE",
        versions=[
            {
                "current": True,
                "object": {"lastName": "Kowalski", "name": "Jan", "orcid": ORCID},
            }
        ],
    )
    baker.make(
        Scientist,
        mongoId=OSOBA_2,
        status="ACTIVE",
        versions=[{"current": True, "object": {"lastName": "Nowak", "name": "Anna"}}],
    )
    z_orcid = baker.make(
        Autor, nazwisko="Kowalski", imiona="Jan", orcid=ORCID, pbn_uid=None
    )
    nieznany = baker.make(Autor, nazwisko="Wiśniewski", imiona="Adam", pbn_uid=None)
    url = reverse("admin:bpp_autor_changelist")

    assert (
        "Pobierz odpowiedniki z PBN (w tle)" in admin_client.get(url).content.decode()
    )
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.post(
            url,
            {
                "action": "pobierz_odpowiedniki_autorow_z_pbn_w_tle",
                "_selected_action": [z_orcid.pk, nieznany.pk],
            },
        )

    zlecenie = PobieranieOdpowiednikowPBN.objects.get()
    assert zlecenie.rodzaj == "autorzy"
    assert zlecenie.zakonczono is not None and not zlecenie.blad, zlecenie.blad
    grupy = {w["pk"]: w["grupa"] for w in zlecenie.wyniki}
    assert grupy[z_orcid.pk] == "ustawiono"
    assert grupy[nieznany.pk] == "nie_znaleziono"
    z_orcid.refresh_from_db()
    nieznany.refresh_from_db()
    assert z_orcid.pbn_uid_id == OSOBA_1
    assert nieznany.pbn_uid_id is None


# --- recenzja PR 1184 ---------------------------------------------------------


def _json_osoby(pk, orcid=ORCID):
    return {
        "mongoId": pk,
        "status": "ACTIVE",
        "verificationLevel": "x",
        "verified": True,
        "versions": [
            {
                "current": True,
                "object": {"lastName": "Kowalski", "name": "Jan", "orcid": orcid},
            }
        ],
    }


@pytest.mark.django_db
def test_dwa_profile_pbn_z_tym_samym_orcid_to_wybor_nie_automat(uczelnia):
    """Serwer PBN zwraca DWA profile dla ORCID nieznanego lokalnie. Oba
    trafiają do kopii i do oceny — zapisanie tylko pierwszego sprawiłoby,
    że wyglądałby na jedyny, czyli pewny."""
    klient = KlientTylkoOrcid([_json_osoby(OSOBA_1), _json_osoby(OSOBA_2)])

    wynik = szukaj_odpowiednika_autora(
        _autor(orcid=ORCID), uczelnia=uczelnia, klient=lambda: klient
    )

    assert Scientist.objects.filter(pk__in=[OSOBA_1, OSOBA_2]).count() == 2
    assert wynik.status == STATUS_DO_WYBORU
    assert {k["id"] for k in wynik.kandydaci} == {OSOBA_1, OSOBA_2}


@pytest.mark.django_db
def test_inny_orcid_kandydata_wyklucza_automat(
    uczelnia, jednostka, wydawnictwo_ciagle_maker
):
    """ORCID autora jest PBN nieznany, a imiennik potwierdzony nazwiskiem
    i publikacją ma INNY ORCID — dwa różne niepuste ORCID to nie ta sama
    osoba; nigdy automatycznie (także w komendzie z FD#510)."""
    from pbn_api.models import Publication
    from pbn_integrator.utils.dopasowanie_autorow import (
        PEWNE,
        SPRZECZNE,
        zbadaj_autorow,
    )

    _osoba(OSOBA_1, "Kowalski", "Jan", orcid="0000-0001-2345-6789", z_instytucji=True)
    autor = _autor(orcid=ORCID)
    publikacja = baker.make(
        Publication,
        mongoId="5e709189878c28a04737dcaa",
        versions=[
            {
                "current": True,
                "object": {
                    "title": "Praca",
                    "authors": {OSOBA_1: {"lastName": "Kowalski", "name": "Jan"}},
                    "orderList": {"AUTHOR": [OSOBA_1]},
                },
            }
        ],
    )
    praca = wydawnictwo_ciagle_maker(tytul_oryginalny="Praca", pbn_uid=publikacja)
    praca.dodaj_autora(autor, jednostka)

    # Strażnik: bez sprzecznego ORCID ten sam dowód JEST pewny.
    bez_orcid = _autor(orcid=None)
    praca.dodaj_autora(bez_orcid, jednostka)
    assert zbadaj_autorow([bez_orcid], uczelnia=uczelnia)[0].poziom != SPRZECZNE

    propozycja = zbadaj_autorow([autor], uczelnia=uczelnia)[0]
    wynik = szukaj_odpowiednika_autora(autor, uczelnia=uczelnia)

    assert propozycja.poziom == SPRZECZNE
    assert propozycja.poziom != PEWNE and not propozycja.do_zapisu
    assert "różni się od ORCID" in "; ".join(propozycja.uwagi)
    assert wynik.status == STATUS_DO_WYBORU


@pytest.fixture
def wydawnictwo_ciagle_maker(
    db, jezyki, charaktery_formalne, typy_kbn, statusy_korekt, typy_odpowiedzialnosci
):
    def maker(**kw):
        return baker.make("bpp.Wydawnictwo_Ciagle", **kw)

    return maker


class KlientNiedostepny:
    def __init__(self):
        self.proby = 0

    def get_person_by_orcid(self, orcid):
        import requests

        self.proby += 1
        raise requests.ConnectionError("PBN nie odpowiada")


@pytest.mark.django_db
def test_niedostepny_pbn_w_formularzu_autora_daje_kandydatow_z_kopii(uczelnia):
    """Przycisk nie kończy się „nieznanym błędem”: przy niedostępnym PBN
    redaktor dostaje kandydatów z lokalnej kopii i uwagę."""
    from bpp.views.api.pbn_odpowiednik import KOMUNIKAT_NIEDOSTEPNY, SerwerPBN

    _osoba(OSOBA_1, "Kowalski", "Jan", z_instytucji=True)
    klient = KlientNiedostepny()

    wynik = szukaj_odpowiednika_autora(
        _autor(orcid=ORCID),
        uczelnia=uczelnia,
        klient=SerwerPBN(lambda: klient, lagodnie=True),
    )

    assert klient.proby == 1
    assert wynik.status == STATUS_DO_WYBORU
    assert [k["id"] for k in wynik.kandydaci] == [OSOBA_1]
    assert wynik.uwaga == KOMUNIKAT_NIEDOSTEPNY


@pytest.mark.django_db
def test_niedostepny_pbn_w_akcji_grupowej_autorow_nie_wiesza_zlecenia(
    admin_user, uczelnia, mocker
):
    """Po serii błędów połączenia zadanie przestaje pytać serwer i kończy
    na lokalnej kopii — nie ponawia w nieskończoność."""
    from django.contrib.contenttypes.models import ContentType

    from pbn_integrator import pobieranie_odpowiednikow as po

    klient = KlientNiedostepny()
    mocker.patch("bpp.models.Uczelnia.pbn_client", return_value=klient)
    autorzy = [
        _autor(nazwisko=f"Nieznany{i}", orcid=f"0000-0002-0000-000{i}")
        for i in range(8)
    ]
    zlecenie = PobieranieOdpowiednikowPBN.objects.create(
        zlecil=admin_user,
        uczelnia=uczelnia,
        rodzaj="autorzy",
        content_type=ContentType.objects.get_for_model(Autor),
        identyfikatory=[a.pk for a in autorzy],
    )

    po.wykonaj(zlecenie)

    assert klient.proby == po.MAKS_BLEDOW_Z_RZEDU
    assert zlecenie.zakonczono is not None and not zlecenie.blad, zlecenie.blad
    assert len(zlecenie.wyniki) == 8


@pytest.mark.django_db
def test_widok_autora_trzyma_sie_zakresu_panelu(admin_client, uczelnia, mocker):
    """Autor, którego konto nie może otworzyć w panelu redagowania (inna
    uczelnia), nie jest też dostępny przez przycisk."""
    from django.contrib import admin

    _osoba(OSOBA_1, "Kowalski", "Jan", z_instytucji=True)
    autor = _autor()
    mocker.patch.object(
        type(admin.site._registry[Autor]),
        "get_queryset",
        return_value=Autor.objects.none(),
    )

    odp = admin_client.post(
        reverse("bpp:api_pobierz_z_pbn_autora"),
        data={"pk": autor.pk, "imiona": "Jan", "nazwisko": "Kowalski"},
    )

    assert odp.status_code == 403
