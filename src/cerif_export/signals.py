"""Nagrobek OAI-PMH/CERIF po odpięciu OSTATNIEGO autora uczelni.

Patrz ``cerif_export.models.OdpietaPrzynaleznosc``.
"""

from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_delete, post_save
from django.utils import timezone


def _modele_autorstw():
    from bpp.models import (
        Patent_Autor,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte_Autor,
    )

    return (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor, Patent_Autor)


def _uczelnia_jednostki(jednostka_id):
    from bpp.models import Jednostka

    return (
        Jednostka._base_manager.filter(pk=jednostka_id)
        .values_list("uczelnia_id", flat=True)
        .first()
    )


def _odpiecie_wprost(sender, origin):
    """Czy kasowano SAMO autorstwo (inline, ``.delete()`` wiersza/querysetu),
    a nie kaskadą z publikacji, jednostki, uczelni czy autora.

    Przy kaskadzie (np. teardown uczelni) wiersz ``OdpietaPrzynaleznosc``
    nie ma sensu — a w tej samej transakcji znika jego uczelnia, więc
    odroczony FK wywaliłby COMMIT.
    """
    if isinstance(origin, sender):
        return True
    return getattr(origin, "model", None) is sender


def autorstwo_usuniete(sender, instance, origin=None, **kwargs):
    from cerif_export.models import OdpietaPrzynaleznosc

    if not _odpiecie_wprost(sender, origin):
        return
    rekord_model = sender._meta.get_field("rekord").related_model
    stan = list(
        rekord_model._base_manager.filter(pk=instance.rekord_id).values_list(
            "deleted_at", flat=True
        )[:1]
    )
    if not stan:
        return  # kaskada twardego kasowania publikacji — nie ma czego grzebać
    if stan[0] is not None:
        # Publikacja w koszu: nagrobek daje sam kosz, a rekord z kosza jest
        # zamrożony (trigger odrzuciłby UPDATE ``ostatnio_zmieniony``).
        return

    uczelnia_id = _uczelnia_jednostki(instance.jednostka_id)
    if uczelnia_id is None:
        return
    if sender.all_objects.filter(
        rekord_id=instance.rekord_id, jednostka__uczelnia_id=uczelnia_id
    ).exists():
        return  # uczelnia ma jeszcze innego autora — rekord dalej w secie

    OdpietaPrzynaleznosc.objects.update_or_create(
        content_type=ContentType.objects.get_for_model(rekord_model),
        object_id=instance.rekord_id,
        uczelnia_id=uczelnia_id,
    )
    # Datestamp nagrobka = ``ostatnio_zmieniony`` publikacji. Bez podbicia
    # harvester przyrostowy (``from=`` ostatni harvest) nagrobka nie zobaczy.
    rekord_model._base_manager.filter(pk=instance.rekord_id).update(
        ostatnio_zmieniony=timezone.now()
    )


def autorstwo_zapisane(sender, instance, **kwargs):
    from cerif_export.models import OdpietaPrzynaleznosc

    uczelnia_id = _uczelnia_jednostki(instance.jednostka_id)
    if uczelnia_id is None:
        return
    rekord_model = sender._meta.get_field("rekord").related_model
    OdpietaPrzynaleznosc.objects.filter(
        content_type=ContentType.objects.get_for_model(rekord_model),
        object_id=instance.rekord_id,
        uczelnia_id=uczelnia_id,
    ).delete()


def podlacz():
    for model in _modele_autorstw():
        post_delete.connect(
            autorstwo_usuniete,
            sender=model,
            dispatch_uid=f"cerif_export.odpiecie.{model._meta.label}",
        )
        post_save.connect(
            autorstwo_zapisane,
            sender=model,
            dispatch_uid=f"cerif_export.przypiecie.{model._meta.label}",
        )
