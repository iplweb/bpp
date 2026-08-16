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


@pytest.mark.django_db
def test_soft_delete_tworzy_log_z_userem(wydawnictwo_ciagle, superuser):
    """Wariant z jawnym kontekstem — tak woła kod bez własnego ``delete()``."""
    with soft_delete_context(user=superuser, reason="duplikat"):
        wydawnictwo_ciagle.delete()
    log = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.DELETE).get()
    assert log.user == superuser
    assert log.powod == "duplikat"


@pytest.mark.django_db
def test_soft_delete_bez_usera_loguje_none(wydawnictwo_ciagle):
    """Operacja bez zalogowanego usera (celery, skrypt, scalanie duplikatów).

    ``user=None`` jest POPRAWNYM wynikiem, nie awarią — „nie wiadomo kto"
    jest uczciwsze niż podstawienie pierwszego lepszego konta.
    """
    wydawnictwo_ciagle.delete()
    log = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.DELETE).get()
    assert log.user is None
    assert log.powod == ""


@pytest.mark.django_db
def test_delete_z_argumentem_user_loguje_usera(wydawnictwo_ciagle, superuser):
    """REALNE API: ``delete(user=, reason=)``, bez ręcznego kontekstu.

    Fazy 02/04 przyjmowały te argumenty i je porzucały („konsumuje je
    SoftDeleteLog z fazy 06"). Ten test pilnuje, że faza 06 domknęła
    obietnicę — bez niego cały mechanizm atrybucji działałby wyłącznie dla
    wołających, którzy sami wejdą w context manager, czyli dla nikogo.
    """
    wydawnictwo_ciagle.delete(user=superuser, reason="zdublowany import")
    log = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.DELETE).get()
    assert log.user == superuser
    assert log.powod == "zdublowany import"


@pytest.mark.django_db
def test_restore_z_argumentem_user_loguje_usera(wydawnictwo_ciagle, superuser):
    wydawnictwo_ciagle.delete(user=superuser, reason="pomyłka")
    wydawnictwo_ciagle.restore(user=superuser)
    log = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.RESTORE).get()
    assert log.user == superuser


@pytest.mark.django_db
def test_autor_delete_z_userem_loguje_usera(autor_jan_kowalski, superuser):
    """``Autor`` ma własny ``delete()`` (faza 04) — osobna ścieżka do wpięcia."""
    autor_jan_kowalski.delete(user=superuser, reason="duplikat osoby")
    log = _logi(autor_jan_kowalski, SoftDeleteLog.Akcja.DELETE).get()
    assert log.user == superuser
    assert log.powod == "duplikat osoby"


@pytest.mark.django_db
def test_kaskada_autorstw_dziedziczy_usera(wydawnictwo_ciagle_z_autorem, superuser):
    """Kaskada ``*_Autor`` loguje się z tym samym userem i powodem.

    Soft-delete publikacji z N autorami emituje 1 + N sygnałów, bo wąska
    kaskada fazy 02 kasuje każdy wiersz osobno. Log jest wierny sygnałom:
    powstaje wpis dla rekordu i dla każdego autorstwa. Atrybucja przenosi
    się przez reentrancję context managera — gdyby zawiodła, wiersze
    ``*_Autor`` miałyby ``user=None`` mimo świadomej decyzji operatora.
    """
    from bpp.models import Wydawnictwo_Ciagle_Autor

    autorstwo = wydawnictwo_ciagle_z_autorem.autorzy_set.get()
    wydawnictwo_ciagle_z_autorem.delete(user=superuser, reason="wycofany artykuł")

    log_rekordu = _logi(wydawnictwo_ciagle_z_autorem, SoftDeleteLog.Akcja.DELETE).get()
    assert log_rekordu.user == superuser

    log_autorstwa = SoftDeleteLog.objects.get(
        content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle_Autor),
        object_id=autorstwo.pk,
        akcja=SoftDeleteLog.Akcja.DELETE,
    )
    assert log_autorstwa.user == superuser
    assert log_autorstwa.powod == "wycofany artykuł"
