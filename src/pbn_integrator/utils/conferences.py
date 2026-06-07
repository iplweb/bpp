"""Conference operations for PBN integrator."""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING

from django.db import IntegrityError, transaction

from bpp.models import Konferencja
from pbn_api.models import Conference
from pbn_integrator.utils.mongodb_ops import pobierz_mongodb

if TYPE_CHECKING:
    from pbn_api.client import PBNClient

logger = logging.getLogger("pbn_integrator")


def pobierz_konferencje(client: PBNClient, callback=None):
    """Fetch conferences from PBN.

    Args:
        client: PBN client.
        callback: Optional progress callback.
    """
    pobierz_mongodb(
        client.get_conferences_mnisw(page_size=1000),
        Conference,
        pbar_label="Pobieranie konferencji",
        callback=callback,
    )


def _parse_pbn_date(value):
    """Sparsuj 'YYYY-MM-DD' na date; None gdy brak/niepoprawne."""
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        logger.debug("Niepoprawna data konferencji PBN: %r", value)
        return None


def integruj_konferencje(callback=None):
    """Integruj lustro pbn_api.Conference → bpp.Konferencja.

    Re-entrant: dopasowuje po pbn_uid, potem po (nazwa, rozpoczecie).
    Aktualizuje pola pochodzące z PBN; nie nadpisuje pól, których PBN nie
    dostarcza (typ_konferencji, bazy indeksujące). Zwraca liczbę
    utworzonych/zaktualizowanych konferencji.

    WAŻNE: czytamy przez ``value_or_none``, bo gołe ``value("object", k)``
    zwraca STRING-sentinel ``"[brak k]"`` przy braku klucza (base.py:81-88).
    """
    qs = Conference.objects.all()
    total = qs.count()
    przetworzone = 0

    for i, conf in enumerate(qs.iterator(), 1):
        if callback is not None:
            callback.update(i, total, "Integracja konferencji")

        if conf.status == "DELETED":
            logger.info("Pomijam usuniętą konferencję PBN %s", conf.mongoId)
            continue

        nazwa = conf.value_or_none("object", "fullName")
        if not nazwa:
            logger.info("Pomijam konferencję PBN %s bez nazwy", conf.mongoId)
            continue

        rozpoczecie = _parse_pbn_date(conf.value_or_none("object", "startDate"))
        zakonczenie = _parse_pbn_date(conf.value_or_none("object", "endDate"))
        miasto = conf.value_or_none("object", "city")
        panstwo = conf.value_or_none("object", "country")
        skrot = conf.value_or_none("object", "abbreviation")

        konferencja = Konferencja.objects.filter(pbn_uid_id=conf.pk).first()
        if konferencja is None:
            konferencja = Konferencja.objects.filter(
                nazwa=nazwa, rozpoczecie=rozpoczecie
            ).first()

        if konferencja is None:
            konferencja = Konferencja(nazwa=nazwa, rozpoczecie=rozpoczecie)

        konferencja.pbn_uid_id = conf.pk
        konferencja.nazwa = nazwa
        konferencja.rozpoczecie = rozpoczecie
        konferencja.zakonczenie = zakonczenie
        konferencja.miasto = miasto
        konferencja.panstwo = panstwo
        if skrot:
            konferencja.skrocona_nazwa = skrot

        try:
            with transaction.atomic():
                konferencja.save()
            przetworzone += 1
        except IntegrityError:
            logger.warning(
                "Konflikt unikalności (nazwa, rozpoczecie) dla konferencji PBN "
                "%s (%r, %r) — pomijam",
                conf.mongoId,
                nazwa,
                rozpoczecie,
            )

    return przetworzone
