"""Dodatki create_demo_data: dwudyscyplinowcy, rzadsze typy, celowe brudy,
lustro PBN, konta demo i sprzątanie tego wszystkiego.

Skany deduplikatorów i porównania BPP↔PBN uruchamia użytkownik — testy
uruchamiają je tak jak przyciski na ekranach i sprawdzają, że dane demo
dają wyniki. Testy NIE są transakcyjne (flush po takim teście kasuje
słowniki z baseline, z których korzystają inne testy na tym workerze xdist),
więc komparator czasopism wołamy źródło po źródle, bez puli wątków (wątki
mają własne połączenia i nie widzą transakcji testu).

Test transakcyjny: komparator czasopism PBN liczy w wątkach z własnymi
połączeniami, które nie widzą niezatwierdzonej transakcji testu."""

from decimal import Decimal

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db import connection
from model_bakery import baker

from bpp.demo_data.default_dyscypliny import seed_default_dyscypliny
from bpp.demo_data.generators.dwudyscyplinowcy import PSEUDONIM
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.preflight import REQUIRED_DICTIONARIES
from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Grant_Rekordu,
    Konferencja,
    Nagroda,
    Patent,
    Patent_Autor,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Zrodlo,
)

OD_ROKU, DO_ROKU = 2022, 2025


def _zapewnij_slowniki():
    seed_default_dyscypliny()
    for label, _ in REQUIRED_DICTIONARIES:
        model = apps.get_model(*label.split("."))
        if not model.objects.exists():
            baker.make(model)


def _create(manifest, *extra):
    call_command(
        "create_demo_data",
        "--wydzialow=1",
        "--jednostek-na-wydzial=2",
        "--autorow=40",
        "--ile-ciaglych=120",
        "--ile-zwartych=40",
        "--zrodel=20",
        "--wydawcow=6",
        f"--od-roku={OD_ROKU}",
        f"--do-roku={DO_ROKU}",
        "--procent-z-dyscyplina=100",
        "--dwudyscyplinowcow=4",
        "--seed=11",
        f"--manifest-out={manifest}",
        "--batch-size=50",
        "--yes-i-am-sure",
        f"--confirm-db={connection.settings_dict['NAME']}",
        *extra,
    )


@pytest.fixture
def demo(db, tmp_path):
    _zapewnij_slowniki()
    manifest = tmp_path / "m.json"
    _create(manifest, "--konta-demo")
    return manifest


def test_dwudyscyplinowcy(demo):
    autorzy = Autor.objects.filter(pseudonim=PSEUDONIM)
    assert autorzy.count() == 4
    ad = Autor_Dyscyplina.objects.filter(autor__in=autorzy)
    assert ad.count() == 4 * (DO_ROKU - OD_ROKU + 1)
    for a in ad:
        assert a.subdyscyplina_naukowa_id not in (None, a.dyscyplina_naukowa_id)
        assert a.procent_dyscypliny == Decimal(60)
        assert a.procent_subdyscypliny == Decimal(40)
        assert a.rodzaj_autora.skrot == "N"
    # Część prac przypisana do drugiej dyscypliny:
    w_drugiej = [
        wca
        for wca in Wydawnictwo_Ciagle_Autor.objects.filter(autor__in=autorzy)
        if Autor_Dyscyplina.objects.filter(
            autor=wca.autor,
            rok=wca.rekord.rok,
            subdyscyplina_naukowa=wca.dyscyplina_naukowa_id,
        ).exists()
    ]
    assert w_drugiej

    from ewaluacja_dwudyscyplinowcy.core import pobierz_autorow_z_dwiema_dyscyplinami

    wynik = pobierz_autorow_z_dwiema_dyscyplinami(
        lata=list(range(OD_ROKU, DO_ROKU + 1))
    )
    assert set(autorzy.values_list("pk", flat=True)) <= set(wynik)


def test_rzadkie_typy(demo):
    assert Praca_Doktorska.objects.exists()
    assert Praca_Doktorska.objects.exclude(promotor=None).exists()
    assert Praca_Habilitacyjna.objects.exists()
    assert Patent_Autor.objects.filter(rekord__in=Patent.objects.all()).exists()
    assert Konferencja.objects.exists()
    assert Wydawnictwo_Ciagle.objects.exclude(konferencja=None).exists()
    assert Wydawnictwo_Zwarte.objects.exclude(seria_wydawnicza=None).exists()
    assert Grant_Rekordu.objects.exists()
    assert Nagroda.objects.exists()


def test_generator_nie_uruchamia_skanow_ani_porownan(demo):
    from deduplikator_autorow.models import DuplicateScanRun
    from deduplikator_publikacji.models import PublicationDuplicateScanRun
    from deduplikator_zrodel.models import ScanZrodelForDuplicates
    from komparator_pbn_udzialy.models import RozbieznoscDyscyplinPBN
    from pbn_komparator_zrodel.models import RozbieznoscZrodlaPBN

    assert not DuplicateScanRun.objects.exists()
    assert not PublicationDuplicateScanRun.objects.exists()
    assert not ScanZrodelForDuplicates.objects.exists()
    assert not RozbieznoscDyscyplinPBN.objects.exists()
    assert not RozbieznoscZrodlaPBN.objects.exists()


def test_brudy_widoczne_po_skanach(demo):
    from liveops.progress import TextProgress

    from deduplikator_autorow.models import DuplicateCandidate
    from deduplikator_autorow.tasks import scan_for_duplicates as skan_autorow
    from deduplikator_publikacji.models import PublicationDuplicateCandidate
    from deduplikator_publikacji.tasks import (
        scan_for_duplicates as skan_publikacji,
    )
    from deduplikator_zrodel.models import (
        ScanZrodelForDuplicates,
        SourceDuplicateCandidate,
    )
    from deduplikator_zrodel.operations import perform_scan
    from rozbieznosci_dyscyplin.models import RozbieznosciView

    skan_autorow.apply()
    skan_publikacji.apply(kwargs={"year_from": OD_ROKU, "year_to": DO_ROKU})
    op = ScanZrodelForDuplicates.objects.create(
        owner=get_user_model().objects.get(username="admin")
    )
    perform_scan(op, TextProgress(op))

    duplikaty_autorow = Autor.objects.filter(slug__contains="-duplikat-")
    assert duplikaty_autorow.exists()
    assert (
        DuplicateCandidate.objects.filter(
            duplicate_autor__in=duplikaty_autorow
        ).exists()
        or DuplicateCandidate.objects.filter(main_autor__in=duplikaty_autorow).exists()
    )

    duplikaty_zrodel = Zrodlo.objects.filter(skrot__endswith="-DUP")
    assert duplikaty_zrodel.exists()
    assert (
        SourceDuplicateCandidate.objects.filter(
            duplicate_zrodlo__in=duplikaty_zrodel
        ).exists()
        or SourceDuplicateCandidate.objects.filter(
            main_zrodlo__in=duplikaty_zrodel
        ).exists()
    )

    assert PublicationDuplicateCandidate.objects.exists()
    assert RozbieznosciView.objects.exists()


def test_lustro_pbn(demo):
    from komparator_pbn_udzialy.models import RozbieznoscDyscyplinPBN
    from komparator_pbn_udzialy.utils import porownaj_dyscypliny_pbn
    from pbn_api.models import OswiadczenieInstytucji, Publication, SentData
    from pbn_downloader_app.freshness import is_all_pbn_data_fresh
    from pbn_downloader_app.models import PbnDownloadTask
    from pbn_komparator_zrodel.models import RozbieznoscZrodlaPBN
    from pbn_komparator_zrodel.utils import KomparatorZrodelPBN

    # „Pobrane z PBN” w chwili generowania, bez użytkownika:
    assert is_all_pbn_data_fresh()[0]
    assert PbnDownloadTask.objects.get().user is None

    assert Zrodlo.objects.exclude(pbn_uid=None).count() >= 20
    assert Zrodlo.objects.filter(pbn_uid__status="DELETED").exists()
    assert Wydawnictwo_Ciagle.objects.exclude(pbn_uid=None).exists()
    assert Autor.objects.exclude(pbn_uid=None).exists()
    # Publikacje obecne tylko w PBN:
    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    assert Publication.objects.filter(wydawnictwo_ciagle=None).count() >= 5
    assert OswiadczenieInstytucji.objects.exists()
    assert SentData.objects.filter(content_type=ct, uploaded_okay=True).exists()
    assert SentData.objects.filter(uploaded_okay=False).exclude(exception="").exists()
    porownaj_dyscypliny_pbn(show_progress=False)
    komparator = KomparatorZrodelPBN(min_rok=OD_ROKU, show_progress=False)
    for zrodlo in Zrodlo.objects.exclude(pbn_uid=None):
        komparator.compare_zrodlo(zrodlo)
    assert RozbieznoscDyscyplinPBN.objects.exists()
    assert RozbieznoscZrodlaPBN.objects.exists()


def test_konta_demo(demo):
    User = get_user_model()
    for login in ("admin", "redaktor", "raporty", "user"):
        user = User.objects.get(username=login)
        assert user.check_password(login)
    assert User.objects.get(username="admin").is_superuser
    redaktor = User.objects.get(username="redaktor")
    assert redaktor.is_staff and not redaktor.is_superuser
    assert redaktor.groups.filter(name="wprowadzanie danych").exists()
    assert User.objects.get(username="user").autor_id is not None


@pytest.mark.django_db
def test_konta_demo_nie_zmieniaja_istniejacego(tmp_path):
    _zapewnij_slowniki()
    User = get_user_model()
    # Konto bez hasła (nieużywalne) — generator nie może ustawić mu „admin”.
    # Bez hasła w kodzie: skaner sekretów (GitGuardian) traktuje parę
    # login + hasło w teście jak wyciek.
    User.objects.create_user(username="admin")
    _create(
        tmp_path / "m.json",
        "--konta-demo",
        "--dwudyscyplinowcow=0",
        "--bez-rzadkich-typow",
        "--bez-brudow",
        "--bez-pbn",
        "--zgloszen=0",
    )
    admin = User.objects.get(username="admin")
    assert not admin.has_usable_password()
    assert not admin.is_superuser
    assert User.objects.filter(username="redaktor").exists()


@pytest.mark.django_db
def test_bez_kont_domyslnie(tmp_path):
    _zapewnij_slowniki()
    _create(tmp_path / "m.json", "--bez-pbn", "--bez-brudow")
    assert (
        not get_user_model()
        .objects.filter(username__in=["admin", "redaktor", "raporty", "user"])
        .exists()
    )


def test_cleanup_usuwa_dodatki(demo):
    from pbn_api.models import Journal, OswiadczenieInstytucji, Publication, SentData
    from zglos_publikacje.models import Zgloszenie_Publikacji

    manifest = Manifest.load(demo)
    assert manifest.objects_for("pbn_api.Publication")
    call_command(
        "cleanup_demo_data",
        f"--manifest={demo}",
        "--yes-i-am-sure",
        f"--confirm-db={connection.settings_dict['NAME']}",
    )
    assert not Autor.objects.exists()
    assert not Wydawnictwo_Ciagle.objects.exists()
    assert not Praca_Doktorska.objects.exists()
    assert not Patent.objects.exists()
    assert not Konferencja.objects.exists()
    assert not Publication.objects.exists()
    assert not Journal.objects.exists()
    assert not OswiadczenieInstytucji.objects.exists()
    assert not SentData.objects.exists()
    assert not Zgloszenie_Publikacji.global_objects.exists()
    assert not get_user_model().objects.filter(username="redaktor").exists()
