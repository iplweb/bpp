"""Kosz a kolejka eksportu do PBN — żadna operacja PBN nie ginie po cichu.

- kosz rekordu z aktywną WYSYŁKĄ wymaga zgody operatora
  (``anuluj_wysylke_pbn=True``); bez niej rekord ZOSTAJE;
- zgoda zamyka wpis wysyłki (anulowano) i zleca wycofanie oświadczeń;
- wysyłka już w toku blokuje kosz także ze zgodą;
- przywrócenie przy trwającym wycofaniu: wycofanie idzie dalej, a po jego
  zakończeniu system zleca świeżą wysyłkę.
"""

import pytest
from django.utils import timezone
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from pbn_export_queue.models import PBN_Export_Queue
from pbn_export_queue.operacje import RekordWKolejcePBN, wyslij_ponownie_po_wycofaniu


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


@pytest.mark.django_db
def test_kosz_z_aktywna_wysylka_bez_zgody_odmawia(
    wydawnictwo_ciagle, admin_user, bez_celery
):
    _wysylka(wydawnictwo_ciagle, admin_user)

    with pytest.raises(RekordWKolejcePBN):
        wydawnictwo_ciagle.delete(user=admin_user)

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
    aktywny = PBN_Export_Queue.objects.filter_rekord_do_wysylki(
        wydawnictwo_ciagle
    ).get()
    assert aktywny.operacja == PBN_Export_Queue.Operacja.WYCOFANIE


@pytest.mark.django_db
def test_wysylka_w_toku_blokuje_kosz_takze_ze_zgoda(
    wydawnictwo_ciagle, admin_user, bez_celery
):
    _wysylka(wydawnictwo_ciagle, admin_user, wysylke_podjeto=timezone.now())

    with pytest.raises(RekordWKolejcePBN) as exc:
        wydawnictwo_ciagle.delete(user=admin_user, anuluj_wysylke_pbn=True)

    assert exc.value.w_toku
    assert Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo_ciagle.pk).exists()


@pytest.mark.django_db
def test_po_zakonczeniu_wycofania_system_wysyla_ponownie(
    wydawnictwo_ciagle, admin_user, bez_celery, django_capture_on_commit_callbacks
):
    _z_pbn_uid(wydawnictwo_ciagle)
    wydawnictwo_ciagle.delete(user=admin_user)
    wydawnictwo_ciagle.restore(user=admin_user)

    wycofanie = PBN_Export_Queue.objects.filter_rekord_do_wysylki(
        wydawnictwo_ciagle
    ).get()
    assert wycofanie.wyslij_ponownie_po_zakonczeniu

    with django_capture_on_commit_callbacks(execute=True):
        wycofanie.wysylke_zakonczono = timezone.now()
        wycofanie.zakonczono_pomyslnie = True
        wycofanie.save()

    nowy = PBN_Export_Queue.objects.filter_rekord_do_wysylki(wydawnictwo_ciagle).get()
    assert nowy.operacja == PBN_Export_Queue.Operacja.WYSYLKA
    wycofanie.refresh_from_db()
    assert not wycofanie.wyslij_ponownie_po_zakonczeniu
    # Drugie wywołanie (np. ponowny zapis wpisu) nie dubluje zlecenia.
    assert wyslij_ponownie_po_wycofaniu(wycofanie.pk) is None


@pytest.mark.django_db
def test_ponowny_kosz_zdejmuje_flage_ponownej_wysylki(
    wydawnictwo_ciagle, admin_user, bez_celery
):
    _z_pbn_uid(wydawnictwo_ciagle)
    wydawnictwo_ciagle.delete(user=admin_user)
    wydawnictwo_ciagle.restore(user=admin_user)
    wydawnictwo_ciagle.delete(user=admin_user)

    wycofanie = PBN_Export_Queue.objects.filter_rekord_do_wysylki(
        wydawnictwo_ciagle
    ).get()
    assert wycofanie.operacja == PBN_Export_Queue.Operacja.WYCOFANIE
    assert not wycofanie.wyslij_ponownie_po_zakonczeniu
