"""Krok „Dane demonstracyjne” kreatora pierwszego uruchomienia."""

from datetime import timedelta
from unittest import mock

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from first_run_wizard.models import FirstRunWizardState
from first_run_wizard.registry import registry
from model_bakery import baker

from bpp.demo_data.themes.registry import THEMES
from bpp.models import Uczelnia, Wydawnictwo_Ciagle
from bpp_setup_wizard import dane_demo
from bpp_setup_wizard.dane_demo import (
    GenerowanieNiedozwolone,
    RaportPostepu,
    rozpocznij_generowanie,
)
from bpp_setup_wizard.forms import DaneDemoForm
from bpp_setup_wizard.models import GenerowanieDanychDemo, KreatorDanychDemo
from bpp_setup_wizard.steps import DaneDemoSetupStep, PbnSetupStep

URL = "/setup/step/dane_demo/"
URL_POSTEPU = "/setup/step/dane_demo/postep/"
URL_UCZELNI = "/setup/step/uczelnia/"


@pytest.fixture
def pusta_baza(admin_user, first_run_wizard_state):
    """Stan po kroku 1: jest administrator, nie ma uczelni ani danych,
    kreator otwarty."""
    Uczelnia.objects.all().delete()
    FirstRunWizardState.objects.filter(pk=1).update(completed_at=None)
    return admin_user


@pytest.fixture
def klient(pusta_baza):
    client = Client()
    client.force_login(pusta_baza)
    return client


def _operacja(owner, **kw):
    return GenerowanieDanychDemo.objects.create(owner=owner, motyw="lem", **kw)


def _zakonczona(owner, *, sukces, **kw):
    teraz = timezone.now()
    return _operacja(
        owner,
        started_on=teraz,
        finished_on=teraz,
        finished_successfully=sukces,
        **kw,
    )


# --- motywy --------------------------------------------------------------


def test_motywy_to_wszystkie_motywy_create_demo_data():
    motywy = dane_demo.motywy()
    assert {k for k, _, _ in motywy} == set(THEMES)
    assert motywy[0][0] == dane_demo.MOTYW_DOMYSLNY
    for klucz, nazwa, opis in motywy:
        assert nazwa == THEMES[klucz].label
        assert opis, f"motyw {klucz!r} nie ma opisu w OPISY_MOTYWOW"


def test_formularz_przyjmuje_tylko_znane_motywy():
    assert DaneDemoForm({"motyw": "wiedzmin"}).is_valid()
    assert not DaneDemoForm({"motyw": "nie-ma-takiego"}).is_valid()


# --- kolejność kroków ----------------------------------------------------


def test_kolejnosc_krokow():
    nazwy = [s.name for s in registry.all_steps()]
    assert nazwy == ["admin_user", "dane_demo", "uczelnia", "pbn"]


@pytest.mark.django_db
def test_krok_niekompletny_na_pustej_bazie(pusta_baza):
    assert DaneDemoSetupStep().is_complete() is False


@pytest.mark.django_db
def test_krok_ukonczony_gdy_uczelnia_juz_jest(uczelnia):
    """Dane demo z konsoli (``bpp-ctl init --demo``), dump, istniejąca
    instalacja — kreator nie pyta o dane demo."""
    assert DaneDemoSetupStep().is_complete() is True


@pytest.mark.django_db
def test_krok_ukonczony_po_odpowiedzi_nie(pusta_baza):
    KreatorDanychDemo.objects.create(pk=1, odpowiedz="nie")
    assert DaneDemoSetupStep().is_complete() is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "kw,oczekiwane",
    [
        ({}, False),  # zakolejkowana
        ({"started_on": timezone.now()}, False),  # w toku
    ],
)
def test_krok_niekompletny_w_trakcie_generowania(pusta_baza, kw, oczekiwane):
    _operacja(pusta_baza, **kw)
    assert DaneDemoSetupStep().is_complete() is oczekiwane


@pytest.mark.django_db
def test_krok_po_bledzie(pusta_baza):
    op = _zakonczona(pusta_baza, sukces=False, dane_usuniete=False)
    assert DaneDemoSetupStep().is_complete() is False  # pokaż błąd
    op.blad_zaakceptowany = True
    op.save()
    assert DaneDemoSetupStep().is_complete() is True
    op.blad_zaakceptowany = False
    op.dane_usuniete = True
    op.save()
    assert DaneDemoSetupStep().is_complete() is False  # pytanie wraca


# --- ścieżka „Nie” ---------------------------------------------------------


@pytest.mark.django_db
def test_middleware_prowadzi_do_pytania_o_dane_demo(klient):
    response = klient.get("/")
    assert response.status_code == 302
    assert response.url == URL


@pytest.mark.django_db
def test_pytanie_o_dane_demo(klient):
    response = klient.get(URL)
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Utworzyć dane demo?" in body
    assert "fikcyjne" in body
    assert "Krok 2 z 4" in body
    assert 'name="motyw"' not in body


@pytest.mark.django_db
def test_odpowiedz_nie_prowadzi_do_uczelni_i_pbn(klient):
    response = klient.post(URL, {"akcja": "nie"})
    assert response.status_code == 302
    assert KreatorDanychDemo.objects.get(pk=1).odpowiedz == "nie"
    response = klient.get("/")
    assert response.url == URL_UCZELNI
    body = klient.get(URL_UCZELNI).content.decode("utf-8")
    assert "Krok 3 z 4" in body
    assert "Integracja z PBN" in body
    # Pytanie o dane demo nie wraca.
    assert klient.get(URL).status_code == 302


# --- ścieżka „Tak” ---------------------------------------------------------


@pytest.mark.django_db
def test_wybor_motywu_pokazuje_wszystkie_motywy(klient):
    response = klient.get(URL + "?odpowiedz=tak")
    body = response.content.decode("utf-8")
    assert "Krok 2 z 3" in body
    assert "Generowanie danych" in body
    assert "Dane uczelni" not in body
    assert "Integracja z PBN" not in body
    assert "fikcyjne" in body
    for klucz, nazwa, opis in dane_demo.motywy():
        assert f'value="{klucz}"' in body
        assert escape(nazwa) in body
        assert escape(opis) in body


@pytest.fixture
def kolejka(monkeypatch):
    """Podmienia ``enqueue`` — zapamiętuje operacje zamiast je uruchamiać."""
    zakolejkowane = []
    monkeypatch.setattr(
        GenerowanieDanychDemo, "enqueue", lambda self: zakolejkowane.append(self.pk)
    )
    return zakolejkowane


@pytest.mark.django_db
def test_start_generowania_kolejkuje_po_commicie(
    klient, kolejka, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        response = klient.post(
            URL + "?odpowiedz=tak", {"akcja": "generuj", "motyw": "wiedzmin"}
        )
    assert response.status_code == 302
    assert response.url == URL
    op = GenerowanieDanychDemo.objects.get()
    assert op.motyw == "wiedzmin"
    assert op.owner == klient_user(klient)
    assert kolejka == [op.pk]


@pytest.mark.django_db
def test_podwojny_start_tworzy_jedna_operacje(
    klient, kolejka, django_capture_on_commit_callbacks
):
    """Podwójne kliknięcie, przeładowanie po POST-cie, druga karta."""
    dane = {"akcja": "generuj", "motyw": "lem"}
    with django_capture_on_commit_callbacks(execute=True):
        klient.post(URL + "?odpowiedz=tak", dane)
        klient.post(URL + "?odpowiedz=tak", dane)
        Client().post(URL, dane)  # anonim — odbity przez widok
        druga_karta = Client()
        druga_karta.force_login(klient_user(klient))
        druga_karta.post(URL + "?odpowiedz=tak", {**dane, "motyw": "disney"})
    assert GenerowanieDanychDemo.objects.count() == 1
    assert len(kolejka) == 1


@pytest.mark.django_db
def test_rozpocznij_generowanie_zwraca_trwajaca_operacje(pusta_baza, kolejka):
    pierwsza = rozpocznij_generowanie(pusta_baza, "lem")
    druga = rozpocznij_generowanie(pusta_baza, "miks")
    assert druga.pk == pierwsza.pk
    assert GenerowanieDanychDemo.objects.count() == 1


@pytest.mark.django_db
def test_rozpocznij_generowanie_tylko_na_pustej_bazie(pusta_baza, kolejka):
    baker.make(Wydawnictwo_Ciagle)
    with pytest.raises(GenerowanieNiedozwolone):
        rozpocznij_generowanie(pusta_baza, "lem")
    assert not GenerowanieDanychDemo.objects.exists()


@pytest.mark.django_db
def test_rozpocznij_generowanie_nie_po_zakonczeniu_kreatora(pusta_baza, kolejka):
    FirstRunWizardState.mark_completed()
    with pytest.raises(GenerowanieNiedozwolone):
        rozpocznij_generowanie(pusta_baza, "lem")


@pytest.mark.django_db
def test_rozpocznij_generowanie_odrzuca_nieznany_motyw(pusta_baza, kolejka):
    with pytest.raises(GenerowanieNiedozwolone):
        rozpocznij_generowanie(pusta_baza, "nie-ma-takiego")


@pytest.mark.django_db
def test_widok_pokazuje_blad_gdy_baza_niepusta(klient, kolejka):
    baker.make(Wydawnictwo_Ciagle)
    response = klient.post(URL + "?odpowiedz=tak", {"akcja": "generuj", "motyw": "lem"})
    assert response.status_code == 200
    assert "tylko na pustej bazie" in response.content.decode("utf-8")
    assert not GenerowanieDanychDemo.objects.exists()


@pytest.mark.django_db
def test_strona_postepu_w_trakcie_generowania(klient):
    _operacja(
        klient_user(klient),
        started_on=timezone.now(),
        percent=42,
        status_text="Autorzy — Autorzy",
    )
    # Każdy request admina trafia na stronę postępu.
    assert klient.get("/").url == URL
    response = klient.get(URL)
    body = response.content.decode("utf-8")
    assert 'role="progressbar"' in body
    assert 'aria-valuenow="42"' in body
    assert "Autorzy — Autorzy" in body
    assert URL_POSTEPU in body
    assert "Krok 3 z 3" in body
    # „Nie” w trakcie generowania niczego nie zmienia.
    klient.post(URL, {"akcja": "nie"})
    assert not KreatorDanychDemo.objects.filter(odpowiedz="nie").exists()


def klient_user(klient):
    return get_user_model().objects.get(pk=klient.session["_auth_user_id"])


# --- widok postępu (JSON) ------------------------------------------------


@pytest.mark.django_db
def test_postep_json_w_toku(klient):
    _operacja(
        klient_user(klient),
        started_on=timezone.now(),
        percent=37,
        status_text="Artykuły w czasopismach",
        postep_zaktualizowano=timezone.now(),
    )
    dane = klient.get(URL_POSTEPU).json()
    assert dane["stan"] == "STARTED"
    assert dane["procent"] == 37
    assert dane["opis"] == "Artykuły w czasopismach"
    assert dane["w_toku"] is True
    assert dane["zawieszone"] is False


@pytest.mark.django_db
def test_postep_json_zawieszone(klient):
    dawno = timezone.now() - dane_demo.PROG_ZAWIESZENIA - timedelta(minutes=1)
    _operacja(klient_user(klient), started_on=dawno, postep_zaktualizowano=dawno)
    assert klient.get(URL_POSTEPU).json()["zawieszone"] is True


@pytest.mark.django_db
def test_postep_json_sukces_i_blad(klient):
    user = klient_user(klient)
    _zakonczona(user, sukces=False, traceback="Traceback…\nValueError: zepsute")
    dane = klient.get(URL_POSTEPU).json()
    assert dane["stan"] == "FINISHED_ERROR"
    assert dane["w_toku"] is False
    assert dane["blad"] == "ValueError: zepsute"

    _zakonczona(user, sukces=True, percent=100)
    dane = klient.get(URL_POSTEPU).json()
    assert dane["stan"] == "FINISHED_OK"
    assert dane["url_dalej"] == "/"


@pytest.mark.django_db
def test_postep_json_brak_operacji(klient):
    assert klient.get(URL_POSTEPU).json() == {"stan": "BRAK"}


@pytest.mark.django_db
def test_postep_json_tylko_dla_superusera(pusta_baza):
    _operacja(pusta_baza, started_on=timezone.now())
    assert Client().get(URL_POSTEPU).status_code == 403
    zwykly = Client()
    zwykly.force_login(baker.make(get_user_model(), is_superuser=False))
    assert zwykly.get(URL_POSTEPU).status_code == 403


# --- błąd generowania ------------------------------------------------------


@pytest.mark.django_db
def test_blad_z_danymi_w_bazie_wymaga_potwierdzenia(klient):
    op = _zakonczona(
        klient_user(klient),
        sukces=False,
        dane_usuniete=False,
        traceback="RuntimeError: brak miejsca",
        manifest="/tmp/m.json",
    )
    assert klient.get("/").url == URL
    body = klient.get(URL).content.decode("utf-8")
    assert "RuntimeError: brak miejsca" in body
    assert "cleanup_demo_data --manifest /tmp/m.json" in body

    response = klient.post(URL, {"akcja": "dalej"})
    assert response.status_code == 302
    op.refresh_from_db()
    assert op.blad_zaakceptowany is True
    # Brak uczelni — kreator prowadzi do kroku uczelni.
    assert klient.get("/").url == URL_UCZELNI


@pytest.mark.django_db
def test_blad_z_usunietymi_danymi_wraca_do_pytania(klient):
    _zakonczona(
        klient_user(klient),
        sukces=False,
        dane_usuniete=True,
        traceback="RuntimeError: brak miejsca",
    )
    body = klient.get(URL).content.decode("utf-8")
    assert "Utworzyć dane demo?" in body
    assert "Poprzednia próba" in body
    assert "RuntimeError: brak miejsca" in body


# --- worker ---------------------------------------------------------------


@pytest.mark.django_db
def test_worker_nie_generuje_dwa_razy(pusta_baza):
    op = _operacja(pusta_baza, przejete=True)
    with pytest.raises(dane_demo.BladGenerowaniaDanychDemo, match="już uruchomione"):
        dane_demo.generuj_dane_demo(op, mock.Mock())


@pytest.mark.django_db
def test_worker_odmawia_na_niepustej_bazie(pusta_baza):
    baker.make(Wydawnictwo_Ciagle)
    op = _operacja(pusta_baza)
    with pytest.raises(dane_demo.BladGenerowaniaDanychDemo, match="tylko"):
        dane_demo.generuj_dane_demo(op, mock.Mock())


@pytest.mark.django_db
def test_worker_po_bledzie_sprzata_i_zapisuje_stan(pusta_baza, monkeypatch):
    def zepsuty_generator(operacja, manifest, wyjscie):
        wyjscie.write("[BLAD] cos poszlo nie tak\n")
        raise RuntimeError("awaria generatora")

    monkeypatch.setattr(dane_demo, "_uruchom_generator", zepsuty_generator)
    op = _operacja(pusta_baza)
    with pytest.raises(RuntimeError, match="awaria generatora"):
        dane_demo.generuj_dane_demo(op, mock.Mock())
    op.refresh_from_db()
    assert op.dane_usuniete is True


def test_raport_postepu_mapuje_etapy_i_nie_cofa_paska(monkeypatch):
    op = mock.Mock(pk=1)
    zapisy = []
    monkeypatch.setattr(
        GenerowanieDanychDemo.objects,
        "filter",
        lambda **kw: mock.Mock(update=lambda **u: zapisy.append(u)),
    )
    raport = RaportPostepu(op, mock.Mock())
    raport.MIN_ODSTEP = 0

    raport.pasek("Autorzy", 0, 2)
    autorzy = raport.procent
    raport.pasek("Wydawnictwa ciągłe", 1, 2)
    wc = raport.procent
    assert dane_demo.PROCENT_GENERATOR_OD <= autorzy < wc
    assert "Artykuły w czasopismach" in raport.tekst
    assert "(1/2)" in raport.tekst

    # Pasek spoza tabeli: zmienia tylko opis.
    raport.pasek("Coś nowego", 1, 1)
    assert raport.procent == wc
    assert raport.tekst == "Coś nowego"

    raport.pasek("PBN — publikacje", 1, 1)
    assert raport.procent == dane_demo.PROCENT_GENERATOR_DO
    assert zapisy[-1]["percent"] == dane_demo.PROCENT_GENERATOR_DO


def test_etapy_generatora_pokrywaja_opisy_paskow():
    """Każdy pasek generatora (``desc=`` w bpp.demo_data) trafia do etapu —
    inaczej pasek kreatora stałby w miejscu przez cały ten etap."""
    for desc in (
        "Wydziały",
        "Jednostki",
        "Autorzy",
        "Autor_Jednostka",
        "Autor_Dyscyplina",
        "Źródła",
        "Wydawcy",
        "Punktacja źródeł",
        "Dyscypliny źródeł",
        "Poziomy wydawców",
        "Wydawnictwa ciągłe",
        "WC ↔ autorzy",
        "WZ nadrzędne",
        "WZ zwykłe",
        "WZ ↔ autorzy",
        "Streszczenia WC",
        "Zgłoszenia publikacji",
        "Prace doktorskie",
        "Patenty",
        "Dwudyscyplinowcy",
        "Brudy — zdublowane prace",
        "Punkty/sloty WC",
        "PBN — publikacje",
    ):
        assert any(
            desc.startswith(prefiksy) for prefiksy, _, _ in dane_demo.ETAPY_GENERATORA
        ), desc


# --- pełna ścieżka „Tak” --------------------------------------------------


@pytest.mark.django_db
def test_sciezka_demo_pomija_uczelnie_i_pbn(
    klient, monkeypatch, django_capture_on_commit_callbacks
):
    """Generator (tu: atrapa) tworzy uczelnię — kroki „Dane uczelni”
    i „Integracja z PBN” są ukończone, kreator kończy się po generowaniu."""

    def atrapa(operacja, p):
        baker.make(Uczelnia, nazwa="Demo — Uniwersytet")

    monkeypatch.setattr(dane_demo, "generuj_dane_demo", atrapa)
    with django_capture_on_commit_callbacks(execute=True):
        klient.post(URL + "?odpowiedz=tak", {"akcja": "generuj", "motyw": "lem"})

    op = GenerowanieDanychDemo.objects.get()
    assert op.get_state() == "FINISHED_OK"
    assert klient.get(URL_POSTEPU).json()["stan"] == "FINISHED_OK"
    assert PbnSetupStep().is_complete() is True

    response = klient.get("/")
    assert "/setup/" not in response.get("Location", "")
    assert FirstRunWizardState.is_completed()
    assert klient.get(reverse("bpp_setup_wizard:pbn")).status_code == 404


@pytest.mark.django_db
def test_generowanie_naprawde_tworzy_dane(pusta_baza, monkeypatch):
    """Prawdziwy generator w małej skali — sprawdza, że kreator woła
    ``run_create`` z poprawnymi opcjami i że postęp dochodzi do 100%."""
    from bpp.demo_data.preflight import REQUIRED_DICTIONARIES

    for label, _ in REQUIRED_DICTIONARIES:
        model = apps.get_model(*label.split("."))
        if not model.objects.exists():
            baker.make(model)

    monkeypatch.setitem(dane_demo.PARAMETRY_GENERATORA, "wydzialow", 1)
    monkeypatch.setitem(dane_demo.PARAMETRY_GENERATORA, "jednostek_na_wydzial", 2)
    monkeypatch.setitem(dane_demo.PARAMETRY_GENERATORA, "autorow", 5)
    monkeypatch.setitem(dane_demo.PARAMETRY_GENERATORA, "ile_ciaglych", 5)
    monkeypatch.setitem(dane_demo.PARAMETRY_GENERATORA, "ile_zwartych", 5)
    monkeypatch.setitem(dane_demo.PARAMETRY_GENERATORA, "zrodel", 3)
    monkeypatch.setitem(dane_demo.PARAMETRY_GENERATORA, "wydawcow", 2)
    monkeypatch.setitem(dane_demo.PARAMETRY_GENERATORA, "od_roku", 2024)
    monkeypatch.setitem(dane_demo.PARAMETRY_GENERATORA, "do_roku", 2025)

    op = _operacja(pusta_baza)
    dane_demo.generuj_dane_demo(op, mock.Mock())

    op.refresh_from_db()
    assert op.percent == 100
    assert Uczelnia.objects.get().nazwa.startswith("Demo — ")
    assert Wydawnictwo_Ciagle.objects.count() >= 5
