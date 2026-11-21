"""Kosz a kolejka eksportu do PBN — proste reguły pod blokadami.

KOSZ: aktywny wpis blokuje kosz, dopóki kolejka z nim nie skończy; wyjątek:
czekającą wysyłkę operator może jawnie ANULOWAĆ. „W trakcie" = worker
trzyma blokadę doradczą rekordu — wtedy kosz i przywrócenie odmawiają;
wysyłki czekające na ponowienie (RETRY_*) nie są „w trakcie". Wysyłka po
PRZYWRÓCENIU blokuje kosz do końca. Worker tuż przed wysyłką czyta stan
rekordu od nowa (wysyłka rekordu z kosza / wycofanie żywego — pomijane).

PRZYWRÓCENIE: aktywne wycofanie (podjęte czy nie) blokuje przywrócenie;
po zakończonym wycofaniu — od razu wysyłka. Żadnych flag „wyślij później".
"""

from contextlib import contextmanager
from unittest import mock

import pytest
from django.utils import timezone
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from pbn_export_queue.models import PBN_Export_Queue
from pbn_export_queue.operacje import RekordWKolejcePBN


def _z_pbn_uid(rekord):
    from pbn_api.models import Publication

    rekord.pbn_uid = baker.make(Publication)
    rekord.save()
    return rekord


def _wysylka(rekord, user, **kw):
    return baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=rekord,
        zamowil=user,
        operacja=PBN_Export_Queue.Operacja.WYSYLKA,
        wysylke_zakonczono=None,
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
def test_kosz_z_aktywna_wysylka_bez_zgody_odmawia(
    wydawnictwo_ciagle, admin_user, bez_celery
):
    _wysylka(wydawnictwo_ciagle, admin_user)

    with pytest.raises(RekordWKolejcePBN) as exc:
        wydawnictwo_ciagle.delete(user=admin_user)

    assert exc.value.powod == "oczekuje"
    assert Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo_ciagle.pk).exists()


@pytest.mark.django_db
def test_kosz_ze_zgoda_anuluje_wysylke_i_zleca_wycofanie(
    wydawnictwo_ciagle, admin_user, bez_celery
):
    _z_pbn_uid(wydawnictwo_ciagle)
    wysylka = _wysylka(wydawnictwo_ciagle, admin_user)

    wydawnictwo_ciagle.delete(user=admin_user, anuluj_wysylke_pbn=True)

    wysylka.refresh_from_db()
    assert wysylka.wysylke_zakonczono is not None
    assert wysylka.wykluczone
    assert "Anulowano" in wysylka.komunikat
    assert _aktywny(wydawnictwo_ciagle).operacja == PBN_Export_Queue.Operacja.WYCOFANIE


@contextmanager
def _worker_trzyma_blokade(rekord):
    """Symuluje workera w trakcie wysyłki: sesyjna blokada doradcza rekordu
    trzymana z OSOBNEGO połączenia (blokady doradcze są reentrantne w obrębie
    jednej sesji, więc z tego samego połączenia test niczego by nie sprawdził).
    """
    import psycopg2
    from django.contrib.contenttypes.models import ContentType
    from django.db import connection

    from pbn_export_queue.models import klucz_blokady_rekordu

    ustawienia = connection.settings_dict
    inne = psycopg2.connect(
        dbname=ustawienia["NAME"],
        user=ustawienia["USER"],
        password=ustawienia["PASSWORD"],
        host=ustawienia["HOST"],
        port=ustawienia["PORT"],
    )
    klucz = klucz_blokady_rekordu(
        ContentType.objects.get_for_model(rekord).pk, rekord.pk
    )
    try:
        with inne.cursor() as cur:
            # try_ — nigdy nie wisimy (np. gdy transakcja testu trzyma już
            # blokadę xact po wcześniejszym koszu/przywróceniu).
            cur.execute("SELECT pg_try_advisory_lock(%s)", [klucz])
            assert cur.fetchone()[0], "test: blokada rekordu już zajęta"
        yield
    finally:
        inne.close()


@pytest.mark.django_db
def test_kosz_odmawia_gdy_worker_trzyma_blokade(
    wydawnictwo_ciagle, admin_user, bez_celery
):
    _wysylka(wydawnictwo_ciagle, admin_user, wysylke_podjeto=timezone.now())

    with _worker_trzyma_blokade(wydawnictwo_ciagle):
        with pytest.raises(RekordWKolejcePBN) as exc:
            wydawnictwo_ciagle.delete(user=admin_user, anuluj_wysylke_pbn=True)
    assert exc.value.powod == "w_trakcie"
    assert Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo_ciagle.pk).exists()

    # Worker skończył (blokada zwolniona) — anulowanie i kosz przechodzą.
    wydawnictwo_ciagle.delete(user=admin_user, anuluj_wysylke_pbn=True)
    assert not Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo_ciagle.pk).exists()


@pytest.mark.django_db
def test_przywrocenie_odmawia_gdy_worker_trzyma_blokade(
    wydawnictwo_ciagle, admin_user, bez_celery
):
    # Do kosza BEZ ``delete()`` — ``delete()`` wziąłby blokadę xact rekordu
    # na resztę transakcji testu i „worker" nie mógłby jej zająć.
    _do_kosza_bez_delete(wydawnictwo_ciagle)
    w = Wydawnictwo_Ciagle.global_objects.get(pk=wydawnictwo_ciagle.pk)

    with _worker_trzyma_blokade(w):
        with pytest.raises(RekordWKolejcePBN) as exc:
            w.restore(user=admin_user)
    assert exc.value.powod == "w_trakcie"


@pytest.mark.django_db
def test_wysylka_czekajaca_na_ponowienie_daje_sie_anulowac(
    wydawnictwo_ciagle, admin_user, bez_celery
):
    """Recenzja #7: wpis z ``wysylke_podjeto`` (RETRY_*) bez blokady workera
    NIE jest „w trakcie" — da się go anulować."""
    wysylka = _wysylka(
        wydawnictwo_ciagle,
        admin_user,
        wysylke_podjeto=timezone.now(),
        retry_after_user_authorised=True,
    )

    wydawnictwo_ciagle.delete(user=admin_user, anuluj_wysylke_pbn=True)

    wysylka.refresh_from_db()
    assert wysylka.wysylke_zakonczono is not None
    assert not Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo_ciagle.pk).exists()


@pytest.mark.django_db
def test_wycofanie_blokuje_przywrocenie_do_konca(
    wydawnictwo_ciagle, pbn_publication, admin_user, bez_celery, monkeypatch
):
    """Regresja (recenzja, „lost update"): przywrócenie jest zablokowane,
    dopóki wycofanie trwa; po jego zakończeniu przechodzi i zleca wysyłkę."""
    wydawnictwo_ciagle.pbn_uid = pbn_publication
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.delete(user=admin_user)
    wpis = _aktywny(wydawnictwo_ciagle)
    assert wpis.operacja == PBN_Export_Queue.Operacja.WYCOFANIE

    w = Wydawnictwo_Ciagle.global_objects.get(pk=wydawnictwo_ciagle.pk)
    with pytest.raises(RekordWKolejcePBN) as exc:
        w.restore(user=admin_user)
    assert exc.value.powod == "wycofanie"

    monkeypatch.setattr(
        PBN_Export_Queue, "_pozyskaj_klienta_pbn", lambda s: mock.Mock()
    )
    wpis.send_to_pbn()
    wpis.refresh_from_db()
    assert wpis.zakonczono_pomyslnie

    w = Wydawnictwo_Ciagle.global_objects.get(pk=w.pk)
    w.restore(user=admin_user)
    nowy = _aktywny(w)
    assert nowy.operacja == PBN_Export_Queue.Operacja.WYSYLKA
    assert nowy.po_przywroceniu


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
def test_po_przywroceniu_rekordu_nie_da_sie_usunac_do_konca_wysylki(
    wydawnictwo_ciagle, pbn_publication, admin_user, bez_celery
):
    wydawnictwo_ciagle.delete(user=admin_user)
    # PBN UID dopisany „w koszu" (z flagą) — bez wycofania w kolejce, żeby
    # przywrócenie od razu zleciło wysyłkę.
    from bpp.models.soft_delete import operacja_kosza

    with operacja_kosza():
        Wydawnictwo_Ciagle.global_objects.filter(pk=wydawnictwo_ciagle.pk).update(
            pbn_uid=pbn_publication
        )
    wydawnictwo_ciagle.refresh_from_db()
    wydawnictwo_ciagle.restore(user=admin_user)
    wysylka = _aktywny(wydawnictwo_ciagle)
    assert wysylka.po_przywroceniu

    with pytest.raises(RekordWKolejcePBN) as exc:
        wydawnictwo_ciagle.delete(user=admin_user, anuluj_wysylke_pbn=True)
    assert exc.value.powod == "po_przywroceniu"

    # Wysyłka się zakończyła (choćby błędem) — kosz znów możliwy.
    wysylka.error("test")
    wydawnictwo_ciagle.delete(user=admin_user)
    assert not Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo_ciagle.pk).exists()


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
