"""Ślad w historii (admin „Historia") dla danych z ``create_demo_data``."""

import pytest
import reversion
from django.apps import apps
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from model_bakery import baker
from reversion.models import Revision, Version

from bpp.demo_data.historia import (
    MODELE_Z_HISTORIA,
    usun_historie,
    zapisz_historie_utworzenia,
)
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.preflight import REQUIRED_DICTIONARIES
from bpp.models import Autor, Wydawca, Wydawnictwo_Ciagle
from pbn_export_queue.operacje import NAZWA_KONTA_TECHNICZNEGO

KOMENTARZ = "Utworzono poleceniem create_demo_data"


@pytest.fixture
def fixtures_loaded(db):
    for label, _ in REQUIRED_DICTIONARIES:
        model = apps.get_model(label)
        if not model.objects.exists():
            baker.make(model)


def _create(manifest_path, *extra):
    call_command(
        "create_demo_data",
        "--wydzialow=1",
        "--jednostek-na-wydzial=2",
        "--autorow=4",
        "--ile-ciaglych=3",
        "--ile-zwartych=3",
        "--zrodel=2",
        "--wydawcow=2",
        "--zgloszen=7",
        "--seed=7",
        "--bez-ewaluacji",
        f"--manifest-out={manifest_path}",
        "--batch-size=3",
        "--yes-i-am-sure",
        f"--confirm-db={connection.settings_dict['NAME']}",
        *extra,
    )
    return Manifest.load(manifest_path)


def _wpisy(model, pk):
    return LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(model),
        object_id=str(pk),
    )


@pytest.mark.django_db
def test_create_demo_data_zapisuje_wpis_utworzono(fixtures_loaded, tmp_path):
    manifest = _create(tmp_path / "m.json")

    sprawdzone = []
    for label, _ in MODELE_Z_HISTORIA:
        pks = manifest.objects_for(label)
        if not pks:
            continue
        model = apps.get_model(label)
        for pk in pks[:3]:
            wpisy = list(_wpisy(model, pk))
            assert len(wpisy) == 1, (label, pk)
            assert wpisy[0].action_flag == ADDITION
            assert wpisy[0].change_message.startswith(KOMENTARZ)
            assert "seed=7" in wpisy[0].change_message
            assert wpisy[0].user.username == NAZWA_KONTA_TECHNICZNEGO
        sprawdzone.append(label)

    # Generator stworzył co najmniej te modele — każdy musi mieć historię:
    for label in (
        "bpp.Jednostka",
        "bpp.Autor",
        "bpp.Zrodlo",
        "bpp.Wydawca",
        "bpp.Wydawnictwo_Ciagle",
        "bpp.Wydawnictwo_Zwarte",
        "zglos_publikacje.Zgloszenie_Publikacji",
    ):
        assert label in sprawdzone


@pytest.mark.django_db
def test_create_demo_data_zapisuje_wersje_autora(fixtures_loaded, tmp_path):
    manifest = _create(tmp_path / "m.json")

    pks = manifest.objects_for("bpp.Autor")
    for pk in pks:
        wersje = list(Version.objects.get_for_object_reference(Autor, pk))
        assert len(wersje) == 1
        assert wersje[0].revision.comment.startswith(KOMENTARZ)
        assert wersje[0].revision.user.username == NAZWA_KONTA_TECHNICZNEGO
    # Każdy autor ma WŁASNĄ rewizję — przywrócenie wersji jednego autora
    # nie może cofnąć pozostałych:
    rewizje = Version.objects.get_for_model(Autor).filter(
        object_id__in=[str(pk) for pk in pks]
    )
    assert rewizje.values("revision_id").distinct().count() == len(pks)


@pytest.mark.django_db
def test_create_demo_data_uzytkownik(fixtures_loaded, tmp_path, admin_user):
    manifest = _create(tmp_path / "m.json", f"--uzytkownik={admin_user.username}")

    pk = manifest.objects_for("bpp.Wydawnictwo_Ciagle")[0]
    assert _wpisy(Wydawnictwo_Ciagle, pk).get().user == admin_user
    autor_pk = manifest.objects_for("bpp.Autor")[0]
    wersja = Version.objects.get_for_object_reference(Autor, autor_pk).get()
    assert wersja.revision.user == admin_user


@pytest.mark.django_db
def test_create_demo_data_nieznany_uzytkownik(fixtures_loaded, tmp_path):
    with pytest.raises(SystemExit):
        _create(tmp_path / "m.json", "--uzytkownik=nie-ma-takiego")
    assert not Autor.objects.exists()


@pytest.mark.django_db
def test_historia_widoczna_na_stronie_historii(fixtures_loaded, tmp_path, admin_client):
    manifest = _create(tmp_path / "m.json")

    for model, label in (
        (Autor, "bpp.Autor"),
        (Wydawnictwo_Ciagle, "bpp.Wydawnictwo_Ciagle"),
    ):
        pk = manifest.objects_for(label)[0]
        opts = model._meta
        url = reverse(f"admin:{opts.app_label}_{opts.model_name}_history", args=[pk])
        res = admin_client.get(url)
        assert res.status_code == 200
        # Dokładnie raz — u autora wersja i LogEntry nie mogą się dublować:
        assert res.content.decode().count(KOMENTARZ) == 1, label


def _manifest_z(tmp_path, label, pks):
    m = Manifest(tmp_path / "m.json", database="x", command_args={})
    m.append(label, pks)
    return m


@pytest.mark.django_db
def test_logentry_stala_liczba_zapytan_na_paczke(tmp_path, admin_user):
    def zapytania(n):
        pks = [w.pk for w in baker.make(Wydawca, _quantity=n)]
        m = _manifest_z(tmp_path, "bpp.Wydawca", pks)
        with CaptureQueriesContext(connection) as ctx:
            zapisz_historie_utworzenia(
                m, user=admin_user, komentarz="x", batch_size=100
            )
        return len(ctx.captured_queries)

    zapytania(2)  # rozgrzanie cache ContentType
    assert zapytania(3) == zapytania(30)


@pytest.mark.django_db
def test_wersje_autora_ograniczona_liczba_zapytan(tmp_path, admin_user):
    """Autor dostaje rewizję per rekord (patrz ``zapisz_wersje_utworzenia``),
    więc koszt rośnie liniowo — ale ze stałą liczbą zapytań na autora (bez
    N+1 na ``__str__`` czy śledzonych relacjach)."""

    def zapytania(n):
        pks = [a.pk for a in baker.make(Autor, _quantity=n)]
        m = _manifest_z(tmp_path, "bpp.Autor", pks)
        with CaptureQueriesContext(connection) as ctx:
            zapisz_historie_utworzenia(
                m, user=admin_user, komentarz="x", batch_size=100
            )
        return len(ctx.captured_queries)

    zapytania(1)  # rozgrzanie cache ContentType
    q5, q10, q15 = zapytania(5), zapytania(10), zapytania(15)
    na_autora = (q10 - q5) / 5
    assert q15 - q10 == q10 - q5
    assert na_autora <= 8


@pytest.mark.django_db
def test_usun_historie_zostawia_cudza(tmp_path, admin_user):
    demo = baker.make(Autor, _quantity=2)
    cudzy = baker.make(Autor)
    pks = [a.pk for a in demo]
    m = _manifest_z(tmp_path, "bpp.Autor", [*pks, cudzy.pk])
    zapisz_historie_utworzenia(m, user=admin_user, komentarz="x", batch_size=100)

    usun_historie(Autor, pks)

    for pk in pks:
        assert not _wpisy(Autor, pk).exists()
        assert not Version.objects.get_for_object_reference(Autor, pk).exists()
    assert _wpisy(Autor, cudzy.pk).count() == 1
    assert Version.objects.get_for_object_reference(Autor, cudzy.pk).count() == 1
    assert Revision.objects.count() == 1


@pytest.mark.django_db
def test_cleanup_usuwa_historie(fixtures_loaded, tmp_path):
    manifest_path = tmp_path / "m.json"
    manifest = _create(manifest_path)
    swiadek = baker.make(Autor)
    user_pk = LogEntry.objects.first().user_id
    LogEntry.objects.log_actions(user_pk, [swiadek], ADDITION, change_message="swiadek")

    call_command(
        "cleanup_demo_data",
        f"--manifest={manifest_path}",
        "--yes-i-am-sure",
        f"--confirm-db={connection.settings_dict['NAME']}",
    )

    for label, _ in MODELE_Z_HISTORIA:
        model = apps.get_model(label)
        ids = [str(pk) for pk in manifest.objects_for(label)]
        assert not LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(model),
            object_id__in=ids,
        ).exists(), label
        if reversion.is_registered(model):
            wersje = Version.objects.get_for_model(model)
            assert not wersje.filter(object_id__in=ids).exists(), label
    assert not Revision.objects.filter(comment__startswith=KOMENTARZ).exists()
    assert _wpisy(Autor, swiadek.pk).get().user_id == user_pk
