"""Wiązanie sesji importu ze zgłoszeniem publikacji (FD#443).

Jedno miejsce z regułami „które zgłoszenie domyka ta sesja importu" —
używane przez zadanie Celery (auto-wiązanie + zapis zwrotny), przez widok
wyboru kandydata oraz przez prefill dyscyplin. Reguły siedzą tutaj, żeby
``tasks.py``, ``wizard.py`` i widoki ich nie powielały.

Zasady (spec ``docs/superpowers/specs/2026-07-22-zgloszenie-zaimportowane-\
przez-importer-design.md``):

* wiązanie **wyłącznie po DOI** — dopasowanie po tytule jest wykluczone
  (D5: dwa zgłoszenia o identycznym tytule oznaczyłyby przypadkowe),
* kandydaci nie przekraczają granicy uczelni (D8) — ``Zgloszenie_Publikacji``
  nie ma pola ``uczelnia``, więc atrybucja idzie przez jednostki autorów,
* ``WYMAGA_ZMIAN`` jest wykluczony (D9) — zgłoszenie jest wtedy w rękach
  autora (aktywny ``kod_do_edycji``); przestemplowanie zabrałoby mu pracę,
* zapis zwrotny jest idempotentny i odporny na soft-delete (dostęp przez FK
  idzie ``_base_manager``, który **nie** filtruje usuniętych).

``SoftDeleteModel.delete()`` emuluje ``on_delete``, więc skasowanie zgłoszenia
zwykłą ścieżką samo wyzeruje ``ImportSession.zgloszenie``. Guard na
``deleted_at`` w :func:`oznacz_jako_zaimportowane` pilnuje ścieżek, które
``delete()`` omijają — bulk ``UPDATE deleted_at``, surowy SQL, migracje danych,
wyścig transakcji.
"""

import logging

from django.db import transaction
from django.utils import timezone

from import_common.normalization import normalize_doi

logger = logging.getLogger(__name__)


def _wykluczone_statusy():
    """Statusy, w których zgłoszenia nie ma już czym domykać.

    ``ZAAKCEPTOWANY`` i ``ZAIMPORTOWANY`` — praca jest już w BPP.
    ``ODRZUCONO``/``SPAM`` — zgłoszenie zamknięte.
    ``WYMAGA_ZMIAN`` — zgłoszenie jest po stronie zgłaszającego (D9).
    """
    from zglos_publikacje.models import Zgloszenie_Publikacji

    statusy = Zgloszenie_Publikacji.Statusy
    return (
        statusy.ODRZUCONO,
        statusy.SPAM,
        statusy.ZAIMPORTOWANY,
        statusy.ZAAKCEPTOWANY,
        statusy.WYMAGA_ZMIAN,
    )


def _doi_sesji(session):
    """Znormalizowane DOI sesji importu albo ``None``.

    Ta sama normalizacja, co w ``views.authors._find_matching_zgloszenie``
    — wspólny ``import_common.normalization.normalize_doi``.
    """
    return normalize_doi((session.normalized_data or {}).get("doi"))


def _zawez_do_uczelni(qs, session):
    """Zawęź kandydatów do uczelni sesji importu (D8).

    ``Zgloszenie_Publikacji`` nie ma FK do uczelni — jedyna droga w ORM
    prowadzi przez jednostki autorów zgłoszenia. JOIN przez autorów mnoży
    wiersze, więc wołający **musi** dołożyć ``.distinct()``.

    No-op (jak w :func:`bpp.util.uczelnia_scope.scope_rekord_do_uczelni`
    i ``permissions.scope_import_do_uczelni``), gdy:

    * sesja nie ma uczelni (brak mapowania Site→Uczelnia) — nie chcemy
      nagle ukryć wszystkiego,
    * w instalacji jest dokładnie jedna uczelnia — filtr byłby no-opem,
      a kosztowałby JOIN + DISTINCT.
    """
    from bpp.util.uczelnia_scope import tylko_jedna_uczelnia

    if not session.uczelnia_id or tylko_jedna_uczelnia():
        return qs
    return qs.filter(
        zgloszenie_publikacji_autor__jednostka__uczelnia_id=session.uczelnia_id
    )


def kandydaci_dla_sesji(session):
    """Zgłoszenia, które ta sesja importu mogłaby domknąć.

    Zwraca ``QuerySet`` (możliwie pusty — nigdy ``None``), żeby wołający
    mógł go bezpiecznie filtrować (walidacja wyboru operatora) i liczyć.
    """
    from zglos_publikacje.models import Zgloszenie_Publikacji

    doi = _doi_sesji(session)
    if not doi:
        return Zgloszenie_Publikacji.objects.none()

    qs = Zgloszenie_Publikacji.objects.filter(doi__iexact=doi).exclude(
        status__in=_wykluczone_statusy()
    )
    return _zawez_do_uczelni(qs, session).distinct()


def zwiaz_automatycznie(session):
    """Ustaw ``session.zgloszenie``, gdy kandydat jest dokładnie jeden.

    Zwraca ``True`` tylko wtedy, gdy wiązanie faktycznie powstało. Zero
    kandydatów → nie ma czego wiązać; dwa lub więcej → decyduje operator
    (ścieżka C, ``views.zgloszenie.ZgloszenieWyborView``).

    Nie nadpisuje istniejącego wiązania — jawny wybór (ścieżka A) jest
    zawsze mocniejszy od heurystyki po DOI.
    """
    if session.zgloszenie_id:
        return False

    # LIMIT 2 wystarczy do rozstrzygnięcia „dokładnie jeden".
    kandydaci = list(kandydaci_dla_sesji(session)[:2])
    if len(kandydaci) != 1:
        return False

    session.zgloszenie = kandydaci[0]
    session.save(update_fields=["zgloszenie"])
    return True


def oznacz_jako_zaimportowane(session, record):
    """Zapis zwrotny na zgłoszeniu po udanym imporcie. Idempotentny.

    Zwraca ``True``, gdy zgłoszenie zostało oznaczone; ``False``, gdy
    pominięto (brak wiązania, zgłoszenie soft-usunięte, albo już
    oznaczone — ponowienie zadania nie przesuwa daty ani nie zmienia
    autora).

    ``zaimportowal`` bierzemy z ``session.created_by``, nie
    ``modified_by`` — „kto to zrobił" znaczy kto uruchomił import, nie kto
    ostatnio dotknął wiersza.
    """
    from zglos_publikacje.models import Zgloszenie_Publikacji

    if not session.zgloszenie_id:
        return False

    # Dostęp przez FK idzie ``_base_manager``, który NIE filtruje
    # soft-usuniętych. Zwykłe ``zgl.delete()`` samo wyzeruje to FK (biblioteka
    # emuluje ``on_delete``), ale bulk UPDATE, surowy SQL czy migracja danych
    # już nie — stąd jawny guard na ``deleted_at`` niżej.
    zgl = session.zgloszenie

    if zgl.deleted_at is not None:
        logger.warning(
            "Sesja importu %s wskazuje na soft-usunięte zgłoszenie %s — "
            "pomijam oznaczanie jako zaimportowane.",
            session.pk,
            zgl.pk,
        )
        return False

    if zgl.status == Zgloszenie_Publikacji.Statusy.ZAIMPORTOWANY:
        logger.info(
            "Zgłoszenie %s jest już oznaczone jako zaimportowane — "
            "pomijam (sesja importu %s).",
            zgl.pk,
            session.pk,
        )
        return False

    with transaction.atomic():
        zgl.status = Zgloszenie_Publikacji.Statusy.ZAIMPORTOWANY
        zgl.zaimportowano = timezone.now()
        zgl.zaimportowal = session.created_by
        # GenericForeignKey — zapisuje się przez content_type + object_id.
        zgl.odpowiednik_w_bpp = record
        zgl.save(
            update_fields=[
                "status",
                "zaimportowano",
                "zaimportowal",
                "content_type",
                "object_id",
            ]
        )

    logger.info(
        "Zgłoszenie %s oznaczone jako zaimportowane przez sesję importu %s "
        "(rekord %s).",
        zgl.pk,
        session.pk,
        record.pk,
    )
    return True
