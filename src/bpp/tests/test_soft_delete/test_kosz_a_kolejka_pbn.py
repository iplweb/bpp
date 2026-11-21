"""Kosz a kolejka eksportu do PBN — reguła symetryczna, pod blokadą wiersza.

KOSZ: aktywny wpis blokuje kosz, dopóki kolejka z nim nie skończy; wyjątek:
niepodjętą wysyłkę operator może jawnie ANULOWAĆ. Wpis „w trakcie" (worker
go podjął) blokuje zawsze; wysyłki czekające na ponowienie (RETRY_*) nie są
„w trakcie". Wysyłka po PRZYWRÓCENIU blokuje kosz do końca.

PRZYWRÓCENIE: aktywne wycofanie (podjęte czy nie) blokuje przywrócenie;
po zakończonym wycofaniu — od razu wysyłka. Żadnych flag „wyślij później".
"""

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


@pytest.mark.django_db
def test_wpis_w_trakcie_blokuje_kosz_takze_ze_zgoda(
    wydawnictwo_ciagle, admin_user, bez_celery
):
    _wysylka(
        wydawnictwo_ciagle, admin_user, wysylke_podjeto=timezone.now(), w_trakcie=True
    )

    with pytest.raises(RekordWKolejcePBN) as exc:
        wydawnictwo_ciagle.delete(user=admin_user, anuluj_wysylke_pbn=True)

    assert exc.value.powod == "w_trakcie"
    assert Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo_ciagle.pk).exists()


@pytest.mark.django_db
def test_wysylka_czekajaca_na_ponowienie_daje_sie_anulowac(
    wydawnictwo_ciagle, admin_user, bez_celery
):
    """Recenzja #7: RETRY_LATER/RETRY_MUCH_LATER/RETRY_AFTER_USER_AUTHORISED
    zostawiają ``wysylke_podjeto`` — to NIE jest „w trakcie"."""
    wysylka = _wysylka(
        wydawnictwo_ciagle,
        admin_user,
        wysylke_podjeto=timezone.now(),
        w_trakcie=False,
        retry_after_user_authorised=True,
    )

    wydawnictwo_ciagle.delete(user=admin_user, anuluj_wysylke_pbn=True)

    wysylka.refresh_from_db()
    assert wysylka.wysylke_zakonczono is not None
    assert not Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo_ciagle.pk).exists()


@pytest.mark.django_db
def test_porzucony_znacznik_w_trakcie_wygasa(
    wydawnictwo_ciagle, admin_user, bez_celery
):
    """Worker padł w środku próby — po ``W_TRAKCIE_WAZNE_MINUT`` wpis znów da
    się anulować (inaczej rekord byłby zablokowany na zawsze)."""
    _wysylka(
        wydawnictwo_ciagle,
        admin_user,
        wysylke_podjeto=timezone.now() - timezone.timedelta(hours=2),
        w_trakcie=True,
    )
    wydawnictwo_ciagle.delete(user=admin_user, anuluj_wysylke_pbn=True)
    assert not Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo_ciagle.pk).exists()


@pytest.mark.django_db
def test_wycofanie_w_trakcie_blokuje_przywrocenie(
    wydawnictwo_ciagle, pbn_publication, admin_user, bez_celery, monkeypatch
):
    """Regresja (recenzja, „lost update"): worker podjął wycofanie, operator
    przywraca. Dawniej przywrócenie ustawiało flagę, którą pełny ``save()``
    workera nadpisywał — wysyłka po przywróceniu przepadała. Teraz
    przywrócenie jest blokowane, dopóki wycofanie trwa, a po nim przechodzi
    i zleca wysyłkę."""
    wydawnictwo_ciagle.pbn_uid = pbn_publication
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.delete(user=admin_user)
    wpis = _aktywny(wydawnictwo_ciagle)
    assert wpis.operacja == PBN_Export_Queue.Operacja.WYCOFANIE

    assert wpis._zajmij_atomowo()  # worker podjął wpis

    w = Wydawnictwo_Ciagle.global_objects.get(pk=wydawnictwo_ciagle.pk)
    with pytest.raises(RekordWKolejcePBN) as exc:
        w.restore(user=admin_user)
    assert exc.value.powod == "wycofanie"
    assert Wydawnictwo_Ciagle.deleted_objects.filter(pk=w.pk).exists()

    # Worker kończy wycofanie swoją (nieaktualną) instancją.
    monkeypatch.setattr(
        PBN_Export_Queue, "_pozyskaj_klienta_pbn", lambda s: mock.Mock()
    )
    wpis.withdraw_from_pbn()
    PBN_Export_Queue.objects.filter(pk=wpis.pk).update(w_trakcie=False)

    w = Wydawnictwo_Ciagle.global_objects.get(pk=w.pk)
    w.restore(user=admin_user)
    nowy = _aktywny(w)
    assert nowy.operacja == PBN_Export_Queue.Operacja.WYSYLKA
    assert nowy.po_przywroceniu


@pytest.mark.django_db
def test_send_to_pbn_zdejmuje_znacznik_w_trakcie(
    wydawnictwo_ciagle, pbn_publication, admin_user, bez_celery, monkeypatch
):
    wydawnictwo_ciagle.pbn_uid = pbn_publication
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.delete(user=admin_user)
    wpis = _aktywny(wydawnictwo_ciagle)
    monkeypatch.setattr(
        PBN_Export_Queue, "_pozyskaj_klienta_pbn", lambda s: mock.Mock()
    )

    wpis.send_to_pbn()

    wpis.refresh_from_db()
    assert wpis.wysylke_zakonczono is not None
    assert wpis.w_trakcie is False


@pytest.mark.django_db
def test_po_przywroceniu_rekordu_nie_da_sie_usunac_do_konca_wysylki(
    wydawnictwo_ciagle, admin_user, bez_celery
):
    wydawnictwo_ciagle.delete(user=admin_user)
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
