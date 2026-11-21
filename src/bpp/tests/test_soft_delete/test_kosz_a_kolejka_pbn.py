"""Kosz a kolejka eksportu do PBN — JEDNA reguła pod wspólną blokadą.

Rekord z jakimkolwiek niezakończonym wpisem kolejki (czeka, podjęty,
czeka na ponowienie; wysyłka czy wycofanie) nie trafia do kosza ani z niego
nie wraca. Kolejkowanie (każda ścieżka) i kosz/przywrócenie biorą tę samą
transakcyjną blokadę rekordu; kolejkowanie odmawia rekordowi z kosza.
Worker tuż przed wysyłką czyta stan rekordu od nowa.
"""

import threading
import time
from unittest import mock

import pytest
from django.db import connection
from django.utils import timezone
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from pbn_export_queue.models import PBN_Export_Queue, RekordWKoszuPBN
from pbn_export_queue.operacje import KOMUNIKAT_REKORD_W_KOLEJCE, RekordWKolejcePBN


def _z_pbn_uid(rekord):
    from pbn_api.models import Publication

    rekord.pbn_uid = baker.make(Publication)
    rekord.save()
    return rekord


def _wysylka(rekord, user, **kw):
    kw.setdefault("wysylke_zakonczono", None)
    return baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=rekord,
        zamowil=user,
        operacja=PBN_Export_Queue.Operacja.WYSYLKA,
        **kw,
    )


def _do_kosza_bez_delete(rekord):
    """Rekord do kosza z pominięciem ``delete()`` (bez blokady doradczej,
    receiverów i kolejki) — symulacja stanu „w międzyczasie ktoś wyrzucił"."""
    from django.db import connection

    from bpp.models.soft_delete import operacja_kosza

    with operacja_kosza(), connection.cursor() as cur:
        cur.execute(
            f"UPDATE {rekord._meta.db_table} SET deleted_at = now() WHERE id = %s",
            [rekord.pk],
        )
    rekord.refresh_from_db()


def _aktywny(rekord):
    return PBN_Export_Queue.objects.filter_rekord_do_wysylki(rekord).first()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "stan",
    [
        {},
        {"wysylke_podjeto": timezone.now()},
        {"wysylke_podjeto": timezone.now(), "retry_after_user_authorised": True},
    ],
    ids=["czeka", "podjety", "czeka_na_ponowienie"],
)
def test_niezakonczony_wpis_blokuje_kosz(
    wydawnictwo_ciagle, admin_user, bez_celery, stan
):
    _wysylka(wydawnictwo_ciagle, admin_user, **stan)

    with pytest.raises(RekordWKolejcePBN) as exc:
        wydawnictwo_ciagle.delete(user=admin_user)

    assert str(exc.value) == KOMUNIKAT_REKORD_W_KOLEJCE
    assert Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo_ciagle.pk).exists()


@pytest.mark.django_db
def test_wiszaca_wysylke_mozna_usunac_z_kolejki_i_wtedy_kosz_przechodzi(
    wydawnictwo_ciagle, admin_user, bez_celery
):
    wysylka = _wysylka(wydawnictwo_ciagle, admin_user, wysylke_podjeto=timezone.now())
    wysylka.delete()

    wydawnictwo_ciagle.delete(user=admin_user)

    assert not Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo_ciagle.pk).exists()


@pytest.mark.django_db
def test_kolejkowanie_odmawia_rekordowi_z_kosza(
    wydawnictwo_ciagle, admin_user, bez_celery
):
    zakonczona = _wysylka(
        wydawnictwo_ciagle, admin_user, wysylke_zakonczono=timezone.now()
    )
    wydawnictwo_ciagle.delete(user=admin_user)

    with pytest.raises(RekordWKoszuPBN):
        PBN_Export_Queue.objects.sprobuj_utowrzyc_wpis(admin_user, wydawnictwo_ciagle)
    with pytest.raises(RekordWKoszuPBN):
        zakonczona.prepare_for_resend(user=admin_user)
    assert _aktywny(wydawnictwo_ciagle) is None


@pytest.mark.django_db
def test_kosz_czyta_pbn_uid_z_bazy_a_nie_z_instancji(
    wydawnictwo_ciagle, pbn_publication, admin_user, bez_celery
):
    """Regresja: instancja wczytana przed pierwszą udaną wysyłką nie ma
    ``pbn_uid``; wysyłka (zakończona) go dopisała. Kosz musi to zobaczyć
    i zlecić wycofanie."""
    nieaktualna = Wydawnictwo_Ciagle.objects.get(pk=wydawnictwo_ciagle.pk)
    assert nieaktualna.pbn_uid_id is None
    Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo_ciagle.pk).update(
        pbn_uid=pbn_publication
    )

    nieaktualna.delete(user=admin_user)

    assert _aktywny(wydawnictwo_ciagle).operacja == PBN_Export_Queue.Operacja.WYCOFANIE


@pytest.mark.django_db(transaction=True)
def test_kolejkowanie_i_kosz_sa_szeregowane(admin_user, monkeypatch):
    """Regresja: kolejkowanie trzyma blokadę rekordu, kosz na nią CZEKA,
    a po commicie widzi nowy wpis i odmawia (zamiast wyrzucić rekord,
    którego wysyłka właśnie trafiła do kolejki)."""
    from django.db import connections

    monkeypatch.setattr(
        "pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn", mock.Mock()
    )
    rekord = baker.make(Wydawnictwo_Ciagle)
    ma_blokade, puszczaj = threading.Event(), threading.Event()
    oryginal = PBN_Export_Queue.objects._utworz_wpis

    def _utworz_powoli(*args, **kwargs):
        ma_blokade.set()
        assert puszczaj.wait(30)
        return oryginal(*args, **kwargs)

    monkeypatch.setattr(PBN_Export_Queue.objects, "_utworz_wpis", _utworz_powoli)
    wyniki = {}

    def _kolejkuj():
        try:
            PBN_Export_Queue.objects.sprobuj_utowrzyc_wpis(admin_user, rekord)
        finally:
            connections.close_all()

    def _kosz():
        try:
            Wydawnictwo_Ciagle.objects.get(pk=rekord.pk).delete(user=admin_user)
            wyniki["kosz"] = "przeszedl"
        except RekordWKolejcePBN:
            wyniki["kosz"] = "odmowa"
        finally:
            connections.close_all()

    t1 = threading.Thread(target=_kolejkuj)
    t1.start()
    assert ma_blokade.wait(30)
    t2 = threading.Thread(target=_kosz)
    t2.start()
    time.sleep(0.5)
    assert t2.is_alive(), "kosz nie czekał na blokadę kolejkowania"
    puszczaj.set()
    t1.join(30)
    t2.join(30)

    assert wyniki["kosz"] == "odmowa"
    assert Wydawnictwo_Ciagle.objects.filter(pk=rekord.pk).exists()
    connection.close()


@pytest.mark.django_db
def test_wycofanie_blokuje_przywrocenie_do_konca(
    wydawnictwo_ciagle, pbn_publication, admin_user, bez_celery, monkeypatch
):
    """Przywrócenie jest zablokowane, dopóki wycofanie trwa; po jego
    zakończeniu przechodzi i zleca wysyłkę — która z kolei blokuje kosz."""
    wydawnictwo_ciagle.pbn_uid = pbn_publication
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.delete(user=admin_user)
    wpis = _aktywny(wydawnictwo_ciagle)
    assert wpis.operacja == PBN_Export_Queue.Operacja.WYCOFANIE

    w = Wydawnictwo_Ciagle.global_objects.get(pk=wydawnictwo_ciagle.pk)
    with pytest.raises(RekordWKolejcePBN):
        w.restore(user=admin_user)

    monkeypatch.setattr(
        PBN_Export_Queue, "_pozyskaj_klienta_pbn", lambda s: mock.Mock()
    )
    wpis.send_to_pbn()
    wpis.refresh_from_db()
    assert wpis.zakonczono_pomyslnie

    w = Wydawnictwo_Ciagle.global_objects.get(pk=w.pk)
    w.restore(user=admin_user)
    wysylka = _aktywny(w)
    assert wysylka.operacja == PBN_Export_Queue.Operacja.WYSYLKA

    with pytest.raises(RekordWKolejcePBN):
        w.delete(user=admin_user)
    wysylka.error("test")
    w.delete(user=admin_user)
    assert not Wydawnictwo_Ciagle.objects.filter(pk=w.pk).exists()


@pytest.mark.django_db
def test_worker_nie_wysyla_rekordu_z_kosza(wydawnictwo_ciagle, admin_user, bez_celery):
    """Wyścig masowego kolejkowania: wysyłka zlecona, rekord trafił do kosza
    (stan wpisu zmieniony poza kolejką) — worker czyta stan pod blokadą."""
    wpis = _wysylka(wydawnictwo_ciagle, admin_user)
    _do_kosza_bez_delete(wydawnictwo_ciagle)

    wpis.send_to_pbn()

    wpis.refresh_from_db()
    assert wpis.wysylke_zakonczono is not None
    assert "rekord w koszu" in wpis.komunikat


@pytest.mark.django_db
def test_worker_nie_wycofuje_rekordu_zywego(
    wydawnictwo_ciagle, pbn_publication, admin_user, bez_celery
):
    wydawnictwo_ciagle.pbn_uid = pbn_publication
    wydawnictwo_ciagle.save()
    wpis = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        operacja=PBN_Export_Queue.Operacja.WYCOFANIE,
        wysylke_zakonczono=None,
    )

    wpis.send_to_pbn()

    wpis.refresh_from_db()
    assert wpis.wysylke_zakonczono is not None
    assert "przywrócony" in wpis.komunikat


@pytest.mark.django_db
def test_aktywne_wycofanie_nie_do_usuniecia_ani_ponowienia(
    wydawnictwo_ciagle, pbn_publication, admin_user, bez_celery
):
    from pbn_export_queue.models import WycofanieZablokowane

    wydawnictwo_ciagle.pbn_uid = pbn_publication
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.delete(user=admin_user)
    wpis = _aktywny(wydawnictwo_ciagle)

    with pytest.raises(WycofanieZablokowane):
        wpis.delete()
    with pytest.raises(WycofanieZablokowane):
        wpis.prepare_for_resend(user=admin_user)
    assert PBN_Export_Queue.objects.filter(pk=wpis.pk).exists()


@pytest.mark.django_db
def test_niepodjete_wycofanie_tez_blokuje_przywrocenie(
    wydawnictwo_ciagle, pbn_publication, admin_user, bez_celery
):
    wydawnictwo_ciagle.pbn_uid = pbn_publication
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.delete(user=admin_user)
    w = Wydawnictwo_Ciagle.global_objects.get(pk=wydawnictwo_ciagle.pk)

    with pytest.raises(RekordWKolejcePBN):
        w.restore(user=admin_user)

    # Wycofanie zakończone (choćby błędem) → przywrócenie + wysyłka.
    _aktywny(w).error("test")
    w.restore(user=admin_user)
    assert _aktywny(w).operacja == PBN_Export_Queue.Operacja.WYSYLKA


@pytest.mark.django_db
def test_kosz_rekordu_w_koszu_i_przywrocenie_zywego_rzucaja(
    wydawnictwo_ciagle, pbn_publication, admin_user, bez_celery
):
    """Recenzja (B), twardy niezmiennik: ``delete()`` rekordu już w koszu
    i ``restore()`` żywego RZUCAJĄ — nie przesuwają ``deleted_at``, nie
    dopisują logu i nie zlecają drugiego wycofania."""
    from bpp.models.soft_delete import NiedozwolonaZmianaKosza
    from bpp.models.soft_delete_log import SoftDeleteLog

    wydawnictwo_ciagle.pbn_uid = pbn_publication
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.delete(user=admin_user)
    pierwsza = Wydawnictwo_Ciagle.global_objects.get(pk=wydawnictwo_ciagle.pk)

    with pytest.raises(NiedozwolonaZmianaKosza):
        pierwsza.delete(user=admin_user)

    assert (
        Wydawnictwo_Ciagle.global_objects.get(pk=pierwsza.pk).deleted_at
        == pierwsza.deleted_at
    )
    assert (
        SoftDeleteLog.objects.filter(
            object_id=pierwsza.pk, akcja=SoftDeleteLog.Akcja.DELETE
        ).count()
        == 1
    )
    assert (
        PBN_Export_Queue.objects.filter(
            object_id=pierwsza.pk, operacja=PBN_Export_Queue.Operacja.WYCOFANIE
        ).count()
        == 1
    )

    zywy = baker.make(Wydawnictwo_Ciagle)
    with pytest.raises(NiedozwolonaZmianaKosza):
        zywy.restore()
    assert not SoftDeleteLog.objects.filter(object_id=zywy.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("nazwa", ["autor", "zrodlo"])
def test_podwojny_kosz_rzuca_dla_autora_i_slownika(nazwa):
    from bpp.models import Autor, Zrodlo
    from bpp.models.soft_delete import NiedozwolonaZmianaKosza

    obj = baker.make({"autor": Autor, "zrodlo": Zrodlo}[nazwa])
    obj.delete()
    with pytest.raises(NiedozwolonaZmianaKosza):
        obj.delete()
    obj.restore()
    with pytest.raises(NiedozwolonaZmianaKosza):
        obj.restore()
