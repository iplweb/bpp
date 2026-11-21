"""Import z PBN a rekordy w koszu: POMIŃ i ZGŁOŚ (nie wskrzeszaj).

Decyzja właściciela (listopad 2026): rekord usunięty w BPP został usunięty
świadomie. Gdy import z PBN trafia na publikację, której odpowiednik w BPP
jest w koszu, NIE przywraca jej — pomija ją i raportuje jawnie: wpis
``RekordWKoszuPominietyPrzezImport`` (admin), ostrzeżenie w logu i — gdy
import ma sesję (``pbn_import``) — nieścisłość ``record_in_trash`` w raporcie
sesji.

Zajrzenie do kosza jest tu konieczne: dopasowanie (``rekord_w_bpp``) idzie
po ``Rekord``, który kosza nie widzi, a ``pbn_uid`` jest unikalne
bezwarunkowo — bez tego import tworzyłby duplikat albo wywracał się
``IntegrityError``-em.
"""

import logging

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.db.models import F, Q

from pbn_integrator.models import RekordWKoszuPominietyPrzezImport

logger = logging.getLogger(__name__)

#: Typ nieścisłości w raporcie sesji importu (``pbn_import``).
NIESCISLOSC_REKORD_W_KOSZU = "record_in_trash"


def _modele_z_pbn_uid():
    from bpp.models import (
        Patent,
        Praca_Doktorska,
        Praca_Habilitacyjna,
        Wydawnictwo_Ciagle,
        Wydawnictwo_Zwarte,
    )

    modele = []
    for model in (
        Wydawnictwo_Ciagle,
        Wydawnictwo_Zwarte,
        Praca_Doktorska,
        Praca_Habilitacyjna,
        Patent,
    ):
        try:
            model._meta.get_field("pbn_uid")
        except FieldDoesNotExist:
            continue  # model bez pola pbn_uid (np. patent) — nie dopasujemy
        modele.append(model)
    return modele


def rekord_w_koszu_po_pbn_uid(pbn_uid_id):
    """Rekord BPP z kosza powiązany z ``pbn_uid_id`` albo ``None``."""
    if not pbn_uid_id:
        return None
    for model in _modele_z_pbn_uid():
        rekord = model.deleted_objects.filter(pbn_uid_id=pbn_uid_id).first()
        if rekord is not None:
            return rekord
    return None


def zglos_rekord_w_koszu(
    rekord,
    pbn_publication,
    zrodlo_importu,
    inconsistency_callback=None,
    dopisek="",
    skad="PBN",
):
    """Raportuje pominięcie rekordu z kosza. Zwraca ``None`` (wynik importu).

    ``pbn_publication`` — publikacja PBN albo (dla nie-publikacji) sam
    identyfikator do komunikatu; ``skad`` — źródło danych w komunikacie.
    """
    pbn_uid_id = getattr(pbn_publication, "pk", pbn_publication)
    komunikat = (
        f"W {skad} jest rekord {pbn_uid_id}, ale u nas jest usunięty (w koszu): "
        f"„{rekord}” ({rekord._meta.verbose_name}, id={rekord.pk}). "
        f"{dopisek}Import go pominął — rekordów z kosza nie przywracamy "
        f"automatycznie. Jeśli ma wrócić, przywróć go z kosza w adminie."
    )
    logger.warning(komunikat)

    ct = ContentType.objects.get_for_model(type(rekord))
    from pbn_api.models import Publication

    pbn_fk = pbn_uid_id if isinstance(pbn_publication, Publication) else None
    zaktualizowano = RekordWKoszuPominietyPrzezImport.objects.filter(
        content_type=ct, object_id=rekord.pk, zrodlo_importu=zrodlo_importu
    ).update(ile_razy=F("ile_razy") + 1, komunikat=komunikat)
    if zaktualizowano:
        # ``auto_now`` nie działa przy ``update()`` — dotykamy datę zapisem.
        RekordWKoszuPominietyPrzezImport.objects.get(
            content_type=ct, object_id=rekord.pk, zrodlo_importu=zrodlo_importu
        ).save(update_fields=["pominieto"])
    else:
        RekordWKoszuPominietyPrzezImport.objects.create(
            content_type=ct,
            object_id=rekord.pk,
            zrodlo_importu=zrodlo_importu,
            pbn_uid_id=pbn_fk,
            komunikat=komunikat,
        )

    if inconsistency_callback is not None:
        inconsistency_callback(
            inconsistency_type=NIESCISLOSC_REKORD_W_KOSZU,
            pbn_publication=pbn_publication if pbn_fk else None,
            bpp_publication=rekord,
            message=komunikat,
            action_taken="Pominięto (rekord w koszu nie jest przywracany).",
        )
    return None


def pomin_jesli_w_koszu(pbn_publication, zrodlo_importu, inconsistency_callback=None):
    """``True`` (i raport), gdy publikacja PBN ma odpowiednik w koszu BPP."""
    rekord = rekord_w_koszu_po_pbn_uid(getattr(pbn_publication, "pk", None))
    if rekord is None:
        return False
    zglos_rekord_w_koszu(
        rekord, pbn_publication, zrodlo_importu, inconsistency_callback
    )
    return True


def rekord_z_kosza_kolidujacy(model, **wartosci):
    """Rekord ``model`` z kosza, który trzyma którąś z UNIKALNYCH wartości.

    ``wartosci`` — nazwy pól i wartości, którymi import chce utworzyć nowy
    rekord. Pod uwagę idą pola ``unique=True`` z wartością różną od
    ``None``. Utworzenie nowego wiersza z taką wartością wywróciłoby się
    ``IntegrityError``-em (rekord w koszu nadal ją trzyma), a wskrzeszanie
    jest wykluczone — wołający pomija i zgłasza (``pomin_jesli_koliduje``).
    """
    if not hasattr(model, "deleted_objects"):
        return None
    warunek = Q()
    for nazwa, wartosc in wartosci.items():
        if wartosc is None or not model._meta.get_field(nazwa).unique:
            continue
        warunek |= Q(**{nazwa: wartosc})
    if not warunek:
        return None
    return model.deleted_objects.filter(warunek).first()


def pomin_jesli_koliduje(model, zrodlo_importu, opis, skad="PBN", **wartosci):
    """Import nie-publikacji (autor, wydawca, …): gdy unikalna wartość
    należy do rekordu z kosza — zgłoś i zwróć ten rekord (wołający POMIJA
    tworzenie); inaczej ``None``. Nigdy nie tworzymy duplikatu i nigdy nie
    wskrzeszamy."""
    rekord = rekord_z_kosza_kolidujacy(model, **wartosci)
    if rekord is not None:
        zglos_rekord_w_koszu(rekord, opis, zrodlo_importu, skad=skad)
    return rekord
