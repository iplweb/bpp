"""Obsługa trafienia importu w rekord soft-skasowany („w koszu").

Kontekst decyzyjny jest w docstringu ``RekordPrzywroconyPrzezImport``.
"""

import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from pbn_integrator.models import RekordPrzywroconyPrzezImport

logger = logging.getLogger(__name__)


def przywroc_jesli_w_koszu(rekord, pbn_publication, zrodlo_importu):
    """Wskrzesza ``rekord``, jeśli jest w koszu, i odnotowuje to w rejestrze.

    Zwraca ``True`` tylko przy REALNYM wskrzeszeniu — dzięki temu wołający
    może to policzyć, a rejestr nie zapełnia się zwykłymi re-importami.

    ⚠️ ``rekord`` bywa czymś innym niż instancją modelu. ``rekord_w_bpp``
    zwraca STRING ze sklejonymi tytułami, gdy po ``pbn_uid`` trafi więcej niż
    jedna publikacja (zachowanie historyczne, utrzymane w Tasku 2), albo
    ``None``, gdy nie ma nic. Ten helper stoi na ścieżce importu, więc musi to
    przyjąć bez wyjątku — inaczej wywróciłby cały przebieg z powodu, który
    z koszem nie ma nic wspólnego. Stąd ``getattr`` zamiast ``isinstance``
    i wczesny zwrot.
    """
    if getattr(rekord, "deleted_at", None) is None:
        return False

    with transaction.atomic():
        # `restore()` mixinu fazy 02 podnosi też autorstwa skasowane tym samym
        # `transaction_id` — czyli dokładnie te, które zniknęły RAZEM z tą
        # publikacją. Autorstwa skasowane wcześniej, osobną decyzją operatora,
        # zostają w koszu.
        rekord.restore()

        RekordPrzywroconyPrzezImport.objects.create(
            content_type=ContentType.objects.get_for_model(type(rekord)),
            object_id=rekord.pk,
            pbn_uid=pbn_publication,
            zrodlo_importu=zrodlo_importu,
        )

    logger.warning(
        "Import (%s) wskrzesil rekord z kosza: %r (pk=%s, pbn_uid=%s). "
        "Wpis w rejestrze RekordPrzywroconyPrzezImport.",
        zrodlo_importu,
        rekord,
        rekord.pk,
        getattr(pbn_publication, "pk", None),
    )
    return True
