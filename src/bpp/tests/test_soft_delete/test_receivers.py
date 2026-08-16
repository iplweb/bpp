"""Receivery sygnałów soft-delete → ``SoftDeleteLog`` (faza 06)."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django_softdelete.signals import post_hard_delete

from bpp.models.soft_delete_context import soft_delete_context
from bpp.models.soft_delete_log import SoftDeleteLog


def _logi(instance, akcja):
    return SoftDeleteLog.objects.filter(
        content_type=ContentType.objects.get_for_model(instance),
        object_id=instance.pk,
        akcja=akcja,
    )


@pytest.mark.django_db
def test_pakiet_zeruje_pk_przed_wyslaniem_post_hard_delete(wydawnictwo_ciagle):
    """Fakt o pakiecie, na którym opiera się cała obsługa HARD_DELETE.

    ``SoftDeleteModel.hard_delete()`` woła ``Model.delete()``, a kolektor
    Django na koniec zeruje ``pk`` skasowanych instancji — ``post_hard_delete``
    leci PO tym. Receiver nie ma więc z czego wziąć ``object_id`` i musi
    dostać ``pk`` zapamiętany wcześniej.

    Ten test jest strażnikiem założenia: gdyby aktualizacja pakietu
    przestawiła kolejność (sygnał przed zerowaniem), zapali się tutaj,
    a nie w postaci logów z ``object_id`` wziętym z zapasowego pola.
    """
    zebrane = []

    def _sonda(sender, instance, **kwargs):
        zebrane.append(instance.pk)

    post_hard_delete.connect(_sonda, dispatch_uid="test.sonda.pk", weak=False)
    try:
        wydawnictwo_ciagle.hard_delete()
    finally:
        post_hard_delete.disconnect(dispatch_uid="test.sonda.pk")

    assert zebrane == [None], (
        "Pakiet zaczął wysyłać post_hard_delete z niewyzerowanym pk — "
        "stash pk w BppPkPrzedHardDeleteMixin można wtedy uprościć."
    )


def test_kazdy_model_soft_delete_zachowuje_pk():
    """KAŻDY model soft-delete musi mieć ``BppPkPrzedHardDeleteMixin``.

    Bez niego ``post_hard_delete`` dostaje instancję z ``pk is None``,
    a ``pk_dla_audytu()`` rzuca ``RuntimeError`` — czyli twarde skasowanie
    takiego modelu przewróciłoby się w produkcji. Ten test przenosi wykrycie
    z produkcji do testów: nowy model soft-delete zapala się TUTAJ.
    """
    from django.apps import apps
    from django_softdelete.models import SoftDeleteModel

    from bpp.models.soft_delete import BppPkPrzedHardDeleteMixin

    bez_mixinu = [
        model._meta.label
        for model in apps.get_models()
        if issubclass(model, SoftDeleteModel)
        and not issubclass(model, BppPkPrzedHardDeleteMixin)
    ]
    assert bez_mixinu == [], (
        "Modele soft-delete bez BppPkPrzedHardDeleteMixin — ich hard_delete() "
        f"wywali sie na pk_dla_audytu(): {bez_mixinu}"
    )


@pytest.mark.django_db
def test_hard_delete_tworzy_log(wydawnictwo_ciagle, superuser):
    pk = wydawnictwo_ciagle.pk
    ct = ContentType.objects.get_for_model(wydawnictwo_ciagle)
    with soft_delete_context(user=superuser, reason="trwałe"):
        wydawnictwo_ciagle.hard_delete()
    log = SoftDeleteLog.objects.get(
        content_type=ct, object_id=pk, akcja=SoftDeleteLog.Akcja.HARD_DELETE
    )
    assert log.user == superuser
    assert log.powod == "trwałe"
    assert log.pbn_queue_entry is None
