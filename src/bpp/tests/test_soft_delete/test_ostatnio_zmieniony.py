"""``ostatnio_zmieniony`` przy soft-delete i restore.

Soft-delete JEST modyfikacją rekordu i tak musi wyglądać dla konsumentów
przyrostowych (OAI-PMH, CERIF, REST API). Zapis idzie przez
``save(update_fields=['deleted_at', 'restored_at', 'transaction_id'])``,
a Django woła ``auto_now`` tylko dla pól z ``update_fields`` — stąd
``dopisz_znacznik_zmiany``. Lista nagrobków „co skasowano od X" to
``Model.deleted_objects.filter(ostatnio_zmieniony__gte=X)``.
"""

import datetime

import pytest
from django.utils import timezone
from model_bakery import baker

from bpp.models import Autor, Wydawnictwo_Ciagle
from bpp.models.soft_delete import dopisz_znacznik_zmiany


def _znacznik(model, pk):
    return model.global_objects.values_list("ostatnio_zmieniony", flat=True).get(pk=pk)


def _cofnij_znacznik(model, pk):
    stary = timezone.now() - datetime.timedelta(hours=1)
    from bpp.models.soft_delete import operacja_kosza

    # Rekord bywa w koszu (zamrożony triggerem) — test „cofa zegar" z flagą.
    with operacja_kosza():
        model.global_objects.filter(pk=pk).update(ostatnio_zmieniony=stary)
    return stary


@pytest.mark.django_db
@pytest.mark.parametrize("model", [Wydawnictwo_Ciagle, Autor])
def test_soft_delete_i_restore_bumpuja_ostatnio_zmieniony(model):
    obj = baker.make(model)

    stary = _cofnij_znacznik(model, obj.pk)
    obj.refresh_from_db()
    obj.delete()
    po_delete = _znacznik(model, obj.pk)
    assert po_delete > stary

    _cofnij_znacznik(model, obj.pk)
    obj = model.global_objects.get(pk=obj.pk)
    obj.restore()
    assert _znacznik(model, obj.pk) > stary


@pytest.mark.django_db
def test_nagrobki_odpytywalne_po_ostatnio_zmieniony():
    skasowany = baker.make(Wydawnictwo_Ciagle)
    zywy = baker.make(Wydawnictwo_Ciagle)
    for obj in (skasowany, zywy):
        _cofnij_znacznik(Wydawnictwo_Ciagle, obj.pk)
    okno_od = timezone.now() - datetime.timedelta(minutes=5)

    Wydawnictwo_Ciagle.objects.get(pk=skasowany.pk).delete()

    nagrobki = Wydawnictwo_Ciagle.deleted_objects.filter(
        ostatnio_zmieniony__gte=okno_od
    )
    assert list(nagrobki.values_list("pk", flat=True)) == [skasowany.pk]
    assert _znacznik(Wydawnictwo_Ciagle, zywy.pk) < okno_od


def test_dopisz_znacznik_zmiany_model_bez_pola():
    """``Element_Repozytorium`` jest soft-delete, ale bez
    ``ostatnio_zmieniony`` — helper oddaje ``update_fields`` bez zmian."""
    from bpp.models.repozytorium import Element_Repozytorium

    pola = ["deleted_at", "restored_at", "transaction_id"]
    assert dopisz_znacznik_zmiany(Element_Repozytorium(), pola) == pola


def test_dopisz_znacznik_zmiany_nie_rusza_zwyklego_zapisu():
    obj = Wydawnictwo_Ciagle()
    assert dopisz_znacznik_zmiany(obj, ["tytul"]) == ["tytul"]
    assert dopisz_znacznik_zmiany(obj, None) is None
