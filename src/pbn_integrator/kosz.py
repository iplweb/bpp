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


def wskrzes_z_kosza_po_pbn_uid(model, pbn_publication, zrodlo_importu):
    """Szuka w koszu rekordu ``model`` po ``pbn_uid`` i wskrzesza go.

    Zwraca wskrzeszony rekord albo ``None``, gdy w koszu nic nie ma.

    To jest JAWNE zajrzenie do kosza po stronie importera. Akcesory
    (``rekord_w_bpp``, ``get_bpp_publication``, ``matchuj_publikacje``) tego nie
    robią i robić nie będą — idą po ``Rekord``, czyli po widoku odfiltrowanym
    po ``deleted_at``. Skoro soft-delete znaczy „rekordu nie ma", to decyzja
    „a jednak zajrzyj do kosza" należy do wołającego, nie do akcesora.

    Bez tego re-import publikacji, której rekord BPP jest w koszu, wchodzi
    w gałąź „utwórz nowy" i wywala się ``IntegrityError`` — ``pbn_uid`` to
    ``OneToOneField(unique=True)`` BEZ warunku partial, więc rekord w koszu
    nadal to pole trzyma. Kosz jest jednocześnie niewidoczny dla matchingu
    i widoczny dla bazy.

    ⚠️ ``model`` musi mieć pole ``pbn_uid`` (mixin ``ModelZPBN_UID``). ``Patent``
    go NIE ma — ``.filter(pbn_uid_id=…)`` na nim wywala ``FieldError``, bo
    Django resolwuje nazwy pól natychmiast. Stąd model jest parametrem, a nie
    pętlą po wszystkich modelach publikacji.
    """
    rekord = model.deleted_objects.filter(pbn_uid_id=pbn_publication.pk).first()
    if rekord is None:
        return None

    przywroc_jesli_w_koszu(rekord, pbn_publication, zrodlo_importu)
    return rekord


def znajdz_lub_wskrzes_rekord(pbn_publication, model, zrodlo_importu):
    """Rekord tej publikacji, który JUŻ jest w BPP — żywy albo wyjęty z kosza.

    ``None`` znaczy „nie ma go nigdzie" — dopiero wtedy importer tworzy nowy.

    Preambuła wspólna dla trzech importerów (artykuł / książka / rozdział).
    Wydzielona, bo różnią się wyłącznie modelem i etykietą źródła, a rozjazd
    między nimi już raz kosztował: wskrzeszanie siedziało w gałęzi
    ``ret is not None``, gdzie z definicji było no-opem (``Rekord`` nie ma
    ``deleted_at``).

    ⚠️ Zwraca trzy różne rzeczy i wołający musi to znieść: ``Rekord`` (widok
    cache) dla trafienia żywego, instancję modelu konkretnego dla wskrzeszenia
    z kosza, oraz STRING ze sklejonymi tytułami, gdy po ``pbn_uid`` trafi więcej
    niż jedna publikacja (zachowanie historyczne ``rekord_w_bpp``). Admin
    rozróżnia je przez ``isinstance(..., Rekord)`` przed sięgnięciem po
    ``.original``.
    """
    ret = pbn_publication.rekord_w_bpp
    if ret is not None:
        return ret

    return wskrzes_z_kosza_po_pbn_uid(model, pbn_publication, zrodlo_importu)
