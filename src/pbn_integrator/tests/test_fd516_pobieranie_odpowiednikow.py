"""FD#516 — akcja grupowa „Pobierz odpowiedniki z PBN (w tle)” na listach
wydawnictw ciągłych i zwartych.

Ta sama logika co przycisk w formularzu (FD#515). Odczyt z PBN — atrapa
klienta zna wyłącznie wyszukiwanie; każda próba wysyłki wywróciłaby test.
"""

import pytest
import requests
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from messages_extends.models import Message

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from pbn_api.models import Publication
from pbn_integrator import pobieranie_odpowiednikow as po
from pbn_integrator.models import PobieranieOdpowiednikowPBN
from pbn_integrator.tasks import pobierz_odpowiedniki_z_pbn

AKCJA = "pobierz_odpowiedniki_z_pbn_w_tle"
UID_1 = "6accb7c13d7d997e0c94d2a1"
UID_2 = "6accb7c13d7d997e0c94d2a2"
UID_3 = "6accb7c13d7d997e0c94d2a3"


def _publikacja_pbn(uid, **obiekt):
    obiekt.setdefault("year", 2024)
    return Publication.objects.create(
        mongoId=uid,
        status="ACTIVE",
        verificationLevel="x",
        verified=True,
        versions=[{"current": True, "object": obiekt}],
    )


def _zlecenie(user, obiekty, rodzaj="publikacje", uczelnia=None):
    return PobieranieOdpowiednikowPBN.objects.create(
        zlecil=user,
        uczelnia=uczelnia,
        rodzaj=rodzaj,
        content_type=ContentType.objects.get_for_model(type(obiekty[0])),
        identyfikatory=[o.pk for o in obiekty],
    )


def _grupy(zlecenie):
    return {w["pk"]: w["grupa"] for w in zlecenie.wyniki}


class SerwerNieodpowiada:
    def search_publications(self, **kw):
        raise requests.ConnectionError("PBN nie odpowiada")


@pytest.fixture
def wydawnictwo_ciagle_maker(
    db, jezyki, charaktery_formalne, typy_kbn, statusy_korekt, typy_odpowiedzialnosci
):
    from fixtures.conftest_publications import _wydawnictwo_ciagle_maker

    return _wydawnictwo_ciagle_maker


@pytest.fixture
def zwarte_maker(
    db, jezyki, charaktery_formalne, typy_kbn, statusy_korekt, typy_odpowiedzialnosci
):
    from fixtures.conftest_publications import _zwarte_maker

    return _zwarte_maker


@pytest.fixture
def prace(wydawnictwo_ciagle_maker, zwarte_maker, db):
    """Komplet przypadków z raportu."""
    _publikacja_pbn(UID_1, title="Praca z DOI", doi="10.5555/fd516.a")
    _publikacja_pbn(UID_2, title="Cała książka", isbn="9780128195178")
    _publikacja_pbn(UID_3, title="Zajęta", doi="10.5555/fd516.zajeta")
    return {
        "po_doi": wydawnictwo_ciagle_maker(
            tytul_oryginalny="Praca z DOI", doi="10.5555/FD516.A", www="", public_www=""
        ),
        "nie_znaleziono": wydawnictwo_ciagle_maker(
            tytul_oryginalny="Nieznana", doi="10.5555/fd516.nieznana", www=""
        ),
        "puste": wydawnictwo_ciagle_maker(
            tytul_oryginalny="Bez niczego", doi=None, www="", public_www=""
        ),
        "wlasciciel": wydawnictwo_ciagle_maker(
            tytul_oryginalny="Zajęta", doi="10.5555/fd516.zajeta", pbn_uid_id=UID_3
        ),
        "zajety": wydawnictwo_ciagle_maker(
            tytul_oryginalny="Zajęta (duplikat)", doi="10.5555/fd516.zajeta", www=""
        ),
    }


@pytest.mark.django_db
def test_wykonaj_ustawia_jednoznaczne_i_raportuje_reszte(prace, admin_user, uczelnia):
    zlecenie = _zlecenie(admin_user, list(prace.values()), uczelnia=uczelnia)

    po.wykonaj(zlecenie)

    zlecenie.refresh_from_db()
    assert zlecenie.zakonczono is not None and not zlecenie.blad
    assert zlecenie.przetworzono == 5
    grupy = _grupy(zlecenie)
    assert grupy[prace["po_doi"].pk] == po.G_USTAWIONO
    assert grupy[prace["nie_znaleziono"].pk] == po.G_NIE_ZNALEZIONO
    assert grupy[prace["puste"].pk] == po.G_PUSTE
    assert grupy[prace["wlasciciel"].pk] == po.G_MIALY
    assert grupy[prace["zajety"].pk] == po.G_ZAJETY

    for nazwa, praca in prace.items():
        praca.refresh_from_db()
        if nazwa == "po_doi":
            assert praca.pbn_uid_id == UID_1
        elif nazwa != "wlasciciel":
            assert praca.pbn_uid_id is None, nazwa

    wpis = LogEntry.objects.get(
        object_id=str(prace["po_doi"].pk),
        content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
        action_flag=CHANGE,
    )
    assert wpis.user == admin_user
    assert "PBN UID ustawiony automatycznie (grupowo) po: DOI" in wpis.change_message
    # Powiadomienie dla zlecającego.
    komunikat = Message.objects.get(user=admin_user)
    assert "ustawiono 1 z 5" in komunikat.message


@pytest.mark.django_db
def test_isbn_ksiazki_nie_jest_przypisywany_rozdzialowi(
    zwarte_maker, admin_user, uczelnia
):
    """Niejednoznaczne zostają nietknięte — trafiają do ręcznego wyboru."""
    _publikacja_pbn(UID_2, title="Cała książka", isbn="9780128195178")
    rozdzial = zwarte_maker(
        tytul_oryginalny="Rozdział pierwszy", isbn="978-0-12-819517-8", doi=None, www=""
    )
    ksiazka = zwarte_maker(
        tytul_oryginalny="Cała książka", isbn="978-0-12-819517-8", doi=None, www=""
    )
    zlecenie = _zlecenie(admin_user, [rozdzial, ksiazka], uczelnia=uczelnia)

    po.wykonaj(zlecenie)

    grupy = _grupy(zlecenie)
    assert grupy[rozdzial.pk] == po.G_DO_WYBORU
    assert grupy[ksiazka.pk] == po.G_USTAWIONO
    rozdzial.refresh_from_db()
    ksiazka.refresh_from_db()
    assert rozdzial.pbn_uid_id is None
    assert ksiazka.pbn_uid_id == UID_2
    opis = next(w for w in zlecenie.wyniki if w["pk"] == rozdzial.pk)["opis"]
    assert "Cała książka" in opis and UID_2 in opis


@pytest.mark.django_db
def test_blad_polaczenia_trafia_do_raportu_i_nie_przerywa(
    wydawnictwo_ciagle_maker, admin_user, uczelnia, mocker
):
    _publikacja_pbn(UID_1, title="Lokalna", doi="10.5555/fd516.lokalna")
    siec = wydawnictwo_ciagle_maker(tytul_oryginalny="A", doi="10.5555/x1", www="")
    lokalna = wydawnictwo_ciagle_maker(
        tytul_oryginalny="Lokalna", doi="10.5555/fd516.lokalna", www=""
    )
    mocker.patch("bpp.models.Uczelnia.pbn_client", return_value=SerwerNieodpowiada())
    zlecenie = _zlecenie(admin_user, [siec, lokalna], uczelnia=uczelnia)

    po.wykonaj(zlecenie)

    grupy = _grupy(zlecenie)
    assert grupy[siec.pk] == po.G_BLAD
    assert grupy[lokalna.pk] == po.G_USTAWIONO
    assert not zlecenie.blad


@pytest.mark.django_db
def test_nieoczekiwany_blad_konczy_zlecenie_z_komunikatem(
    wydawnictwo_ciagle_maker, admin_user, uczelnia, mocker
):
    praca = wydawnictwo_ciagle_maker(tytul_oryginalny="A", doi="10.5555/x1")
    mocker.patch.object(po, "przetworz_publikacje", side_effect=RuntimeError("bum"))
    mocker.patch.object(po, "capture_exception")
    zlecenie = _zlecenie(admin_user, [praca], uczelnia=uczelnia)

    po.wykonaj(zlecenie)

    zlecenie.refresh_from_db()
    assert zlecenie.zakonczono is not None
    assert "RuntimeError: bum" in zlecenie.blad
    assert zlecenie.stan == "zakończono z błędem"
    assert "błędem" in Message.objects.get(user=admin_user).message


@pytest.mark.django_db
def test_zadanie_nie_wykonuje_zlecenia_drugi_raz(prace, admin_user, uczelnia, mocker):
    zlecenie = _zlecenie(admin_user, [prace["po_doi"]], uczelnia=uczelnia)
    pobierz_odpowiedniki_z_pbn.apply(args=(zlecenie.pk,))
    wykonaj = mocker.patch.object(po, "wykonaj")

    pobierz_odpowiedniki_z_pbn.apply(args=(zlecenie.pk,))

    wykonaj.assert_not_called()
    assert Wydawnictwo_Ciagle.objects.get(pk=prace["po_doi"].pk).pbn_uid_id == UID_1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model", [Wydawnictwo_Ciagle, Wydawnictwo_Zwarte], ids=["ciagle", "zwarte"]
)
def test_akcja_na_liscie_zleca_zadanie_w_tle(
    model,
    admin_client,
    admin_user,
    uczelnia,
    wydawnictwo_ciagle_maker,
    zwarte_maker,
    mocker,
    django_capture_on_commit_callbacks,
):
    maker = wydawnictwo_ciagle_maker if model is Wydawnictwo_Ciagle else zwarte_maker
    _publikacja_pbn(UID_1, title="Ma już", doi="10.5555/ma")
    bez = maker(tytul_oryginalny="Bez odpowiednika", doi="10.5555/bez")
    ma = maker(tytul_oryginalny="Ma już", doi="10.5555/ma", pbn_uid_id=UID_1)
    delay = mocker.patch.object(pobierz_odpowiedniki_z_pbn, "delay")
    url = reverse(f"admin:bpp_{model._meta.model_name}_changelist")

    assert (
        "Pobierz odpowiedniki z PBN (w tle)" in admin_client.get(url).content.decode()
    )
    with django_capture_on_commit_callbacks(execute=True):
        odp = admin_client.post(
            url,
            {"action": AKCJA, "_selected_action": [bez.pk, ma.pk]},
            follow=True,
        )

    zlecenie = PobieranieOdpowiednikowPBN.objects.get()
    # Rekord z odpowiednikiem nie wchodzi do zlecenia.
    assert zlecenie.identyfikatory == [bez.pk]
    assert zlecenie.zlecil == admin_user
    assert zlecenie.rodzaj == "publikacje"
    delay.assert_called_once_with(zlecenie.pk)
    html = odp.content.decode()
    assert "Zlecono wyszukiwanie odpowiedników w PBN dla 1 rekordu" in html
    assert (
        reverse(
            "admin:pbn_integrator_pobieranieodpowiednikowpbn_change",
            args=(zlecenie.pk,),
        )
        in html
    )


@pytest.mark.django_db
def test_akcja_ponad_limit_niczego_nie_zleca(
    admin_client, uczelnia, wydawnictwo_ciagle_maker, mocker
):
    mocker.patch.object(po, "MAKS_REKORDOW", 1)
    delay = mocker.patch.object(pobierz_odpowiedniki_z_pbn, "delay")
    prace = [wydawnictwo_ciagle_maker(tytul_oryginalny=f"P{i}") for i in range(2)]

    odp = admin_client.post(
        reverse("admin:bpp_wydawnictwo_ciagle_changelist"),
        {"action": AKCJA, "_selected_action": [p.pk for p in prace]},
        follow=True,
    )

    assert "najwyżej 1 rekordów" in odp.content.decode()
    assert not PobieranieOdpowiednikowPBN.objects.exists()
    delay.assert_not_called()


@pytest.mark.django_db
def test_strona_raportu_pokazuje_grupy_i_linki(
    prace, admin_client, admin_user, uczelnia
):
    zlecenie = po.wykonaj(
        _zlecenie(admin_user, list(prace.values()), uczelnia=uczelnia)
    )

    html = admin_client.get(
        reverse(
            "admin:pbn_integrator_pobieranieodpowiednikowpbn_change",
            args=(zlecenie.pk,),
        )
    ).content.decode()

    assert "Znaleziono i ustawiono odpowiednik" in html
    assert "Nie znaleziono odpowiednika" in html
    assert "już przypisany do innego rekordu" in html
    assert (
        reverse("admin:bpp_wydawnictwo_ciagle_change", args=(prace["zajety"].pk,))
        in html
    )
    assert 'http-equiv="refresh"' not in html
    # Raport da się znaleźć z listy zleceń w module redagowania.
    lista = admin_client.get(
        reverse("admin:pbn_integrator_pobieranieodpowiednikowpbn_changelist")
    ).content.decode()
    assert "zakończono" in lista


@pytest.mark.django_db
def test_strona_postepu_odswieza_sie_a_cudzego_raportu_nie_widac(
    prace, admin_client, admin_user, staff_client, uczelnia
):
    zlecenie = _zlecenie(admin_user, [prace["po_doi"]], uczelnia=uczelnia)
    url = reverse(
        "admin:pbn_integrator_pobieranieodpowiednikowpbn_change", args=(zlecenie.pk,)
    )

    html = admin_client.get(url).content.decode()

    assert 'http-equiv="refresh"' in html
    assert "Czeka w kolejce" in html
    # Inny redaktor (nie superuser) nie ogląda cudzych zleceń.
    assert staff_client.get(url, follow=True).status_code != 200 or (
        "Praca z DOI" not in staff_client.get(url, follow=True).content.decode()
    )
