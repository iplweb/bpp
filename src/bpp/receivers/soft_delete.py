"""Receivery sygnałów ``django-soft-delete`` → ``SoftDeleteLog``.

JEDEN punkt podpięcia dla WSZYSTKICH modeli soft-delete (publikacje,
``*_Autor``, ``Autor``, ``Element_Repozytorium``) — receivery są rejestrowane
bez ``sender=``, więc nowy model soft-delete jest logowany bez dopisywania
czegokolwiek tutaj. Rejestracja: ``BppConfig.ready()``.

Usera i powód wnosi thread-local ``soft_delete_context`` — sygnały pakietu
ich nie niosą (patrz ``bpp/models/soft_delete_context.py``).
"""

from django.contrib.contenttypes.models import ContentType

from bpp.models.soft_delete import pk_dla_audytu
from bpp.models.soft_delete_context import (
    current_soft_delete_reason,
    current_soft_delete_user,
)
from bpp.models.soft_delete_log import SoftDeleteLog


def _utworz_log(instance, akcja, pbn_queue_entry=None, pbn_status=""):
    return SoftDeleteLog.objects.create(
        content_type=ContentType.objects.get_for_model(instance),
        object_id=pk_dla_audytu(instance),
        akcja=akcja,
        user=current_soft_delete_user(),
        powod=current_soft_delete_reason(),
        pbn_queue_entry=pbn_queue_entry,
        pbn_status=pbn_status,
    )


def on_post_hard_delete(sender, instance, **kwargs):
    """Hard-delete: rekord fizycznie znika, więc bez operacji PBN.

    Wycofanie oświadczeń wymaga ``pbn_uid`` odczytanego z rekordu, a tego
    już nie ma — dług opisany w handoffie fazy 05a §6. Log powstaje mimo
    to i jest wtedy JEDYNYM śladem, że rekord istniał.
    """
    _utworz_log(instance, SoftDeleteLog.Akcja.HARD_DELETE)


def register():
    """Podłącza receivery. Woła to ``BppConfig.ready()``.

    ``dispatch_uid`` przy każdym połączeniu: ``ready()`` bywa wołane więcej
    niż raz (m.in. przy ``TransactionTestCase``), a bez uid-a receiver
    zostałby podpięty dwa razy i każdy soft-delete produkowałby dwa wpisy
    logu. Import sygnałów jest lokalny, żeby moduł dał się zaimportować
    poza kontekstem gotowej aplikacji.
    """
    from django_softdelete.signals import post_hard_delete

    post_hard_delete.connect(
        on_post_hard_delete, dispatch_uid="bpp.soft_delete.post_hard_delete"
    )
