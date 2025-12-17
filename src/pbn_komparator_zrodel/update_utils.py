import logging
import sys
from decimal import Decimal

import rollbar
from django.db import transaction

from bpp.models import Dyscyplina_Naukowa, Punktacja_Zrodla
from import_common.normalization import normalize_kod_dyscypliny

from .models import LogAktualizacjiZrodla, RozbieznoscZrodlaPBN

logger = logging.getLogger(__name__)


def _aktualizuj_punkty(zrodlo, rok, journal, wartosc_przed, wartosc_po, typ_zmiany):
    """Pomocnicza funkcja do aktualizacji punktów źródła."""
    points_data = journal.value("object", "points", return_none=True) or {}
    rok_str = str(rok)
    if rok_str not in points_data:
        return

    pbn_punkty = points_data[rok_str].get("points")
    if pbn_punkty is not None:
        pbn_punkty = Decimal(str(pbn_punkty))

    try:
        punktacja = zrodlo.punktacja_zrodla_set.get(rok=rok)
        stare_punkty = punktacja.punkty_kbn
        if stare_punkty != pbn_punkty:
            wartosc_przed.append(f"punkty={stare_punkty}")
            punktacja.punkty_kbn = pbn_punkty
            punktacja.save()
            wartosc_po.append(f"punkty={pbn_punkty}")
            typ_zmiany.append("punkty")
            logger.info(
                f"Zaktualizowano punkty dla {zrodlo.nazwa} ({rok}): "
                f"{stare_punkty} -> {pbn_punkty}"
            )
    except Punktacja_Zrodla.DoesNotExist:
        zrodlo.punktacja_zrodla_set.create(rok=rok, punkty_kbn=pbn_punkty)
        wartosc_przed.append("punkty=brak")
        wartosc_po.append(f"punkty={pbn_punkty}")
        typ_zmiany.append("punkty")
        logger.info(f"Utworzono punktację dla {zrodlo.nazwa} ({rok}): {pbn_punkty}")


def _aktualizuj_dyscypliny(
    zrodlo, rok, journal, dyscypliny_cache, wartosc_przed, wartosc_po, typ_zmiany
):
    """Pomocnicza funkcja do aktualizacji dyscyplin źródła."""
    # PBN stores disciplines as list of dicts with 'code' and 'name' keys
    pbn_disciplines = journal.value("object", "disciplines", return_none=True) or []

    # Pobierz aktualne dyscypliny
    stare_dyscypliny = set(
        zrodlo.dyscyplina_zrodla_set.filter(rok=rok).values_list(
            "dyscyplina__kod", flat=True
        )
    )
    wartosc_przed.append(f"dyscypliny={','.join(sorted(stare_dyscypliny))}")

    # Usuń stare dyscypliny dla tego roku
    zrodlo.dyscyplina_zrodla_set.filter(rok=rok).delete()

    # Dodaj nowe dyscypliny
    nowe_dyscypliny = set()
    for disc_dict in pbn_disciplines:
        # Extract code from dict (PBN format) or use directly if string
        code = disc_dict.get("code") if isinstance(disc_dict, dict) else disc_dict
        if not code:
            continue
        kod_bpp = normalize_kod_dyscypliny(str(code))
        if not kod_bpp:
            logger.warning(f"Nieprawidłowy kod dyscypliny: {code}")
            continue
        if kod_bpp in dyscypliny_cache:
            zrodlo.dyscyplina_zrodla_set.get_or_create(
                dyscyplina=dyscypliny_cache[kod_bpp],
                rok=rok,
            )
            nowe_dyscypliny.add(kod_bpp)
        else:
            logger.warning(f"Kod dyscypliny {kod_bpp} nie istnieje w BPP")

    if stare_dyscypliny != nowe_dyscypliny:
        wartosc_po.append(f"dyscypliny={','.join(sorted(nowe_dyscypliny))}")
        typ_zmiany.append("dyscypliny")
        logger.info(
            f"Zaktualizowano dyscypliny dla {zrodlo.nazwa} ({rok}): "
            f"{stare_dyscypliny} -> {nowe_dyscypliny}"
        )


def _okresl_typ_zmiany(typ_zmiany):
    """Określa typ zmiany na podstawie listy zmian."""
    if "punkty" in typ_zmiany and "dyscypliny" in typ_zmiany:
        return "oba"
    elif "punkty" in typ_zmiany:
        return "punkty"
    return "dyscypliny"


@transaction.atomic
def aktualizuj_zrodlo_z_pbn(
    zrodlo,
    rok,
    aktualizuj_punkty=True,
    aktualizuj_dyscypliny=True,
    user=None,
):
    """
    Aktualizuje punkty i/lub dyscypliny źródła na podstawie danych z PBN.
    Logika analogiczna do pbn_importuj_dyscypliny_i_punkty_zrodel.

    Args:
        zrodlo: Obiekt Zrodlo do aktualizacji
        rok: Rok dla którego aktualizujemy dane
        aktualizuj_punkty: Czy aktualizować punkty
        aktualizuj_dyscypliny: Czy aktualizować dyscypliny
        user: Użytkownik wykonujący aktualizację (do logowania)

    Returns:
        bool: True jeśli dokonano jakichkolwiek zmian, False w przeciwnym wypadku
    """
    if not zrodlo.pbn_uid:
        raise ValueError(f"Źródło {zrodlo} nie ma przypisanego pbn_uid")

    journal = zrodlo.pbn_uid
    dyscypliny_cache = {d.kod: d for d in Dyscyplina_Naukowa.objects.all()}

    wartosc_przed = []
    wartosc_po = []
    typ_zmiany = []

    if aktualizuj_punkty:
        _aktualizuj_punkty(zrodlo, rok, journal, wartosc_przed, wartosc_po, typ_zmiany)

    if aktualizuj_dyscypliny:
        _aktualizuj_dyscypliny(
            zrodlo,
            rok,
            journal,
            dyscypliny_cache,
            wartosc_przed,
            wartosc_po,
            typ_zmiany,
        )

    # Zapisz log jeśli były zmiany
    if typ_zmiany:
        LogAktualizacjiZrodla.objects.create(
            zrodlo=zrodlo,
            rok=rok,
            typ_zmiany=_okresl_typ_zmiany(typ_zmiany),
            wartosc_przed="; ".join(wartosc_przed),
            wartosc_po="; ".join(wartosc_po),
            user=user,
        )

    # Usuń rozbieżność jeśli już nie istnieje
    RozbieznoscZrodlaPBN.objects.filter(zrodlo=zrodlo, rok=rok).delete()

    return len(typ_zmiany) > 0


def aktualizuj_wiele_zrodel(pks, typ="oba", user=None):
    """
    Aktualizuje wiele źródeł na podstawie listy PK rozbieżności.

    Args:
        pks: Lista PK obiektów RozbieznoscZrodlaPBN
        typ: Typ aktualizacji ('punkty', 'dyscypliny', 'oba')
        user: Użytkownik wykonujący aktualizację

    Returns:
        dict: Słownik ze statystykami (updated, errors, total)
    """
    aktualizuj_punkty = typ in ["punkty", "oba"]
    aktualizuj_dyscypliny = typ in ["dyscypliny", "oba"]

    updated = 0
    errors = 0

    for pk in pks:
        try:
            rozbieznosc = RozbieznoscZrodlaPBN.objects.select_related("zrodlo").get(
                pk=pk
            )
            zmieniono = aktualizuj_zrodlo_z_pbn(
                rozbieznosc.zrodlo,
                rozbieznosc.rok,
                aktualizuj_punkty=aktualizuj_punkty,
                aktualizuj_dyscypliny=aktualizuj_dyscypliny,
                user=user,
            )
            if zmieniono:
                updated += 1
        except RozbieznoscZrodlaPBN.DoesNotExist:
            logger.warning(f"Rozbieżność o pk={pk} nie istnieje")
            errors += 1
        except Exception as e:
            logger.exception(f"Błąd aktualizacji pk={pk}")
            rollbar.report_exc_info(sys.exc_info())
            # Store error in Meta object
            from .models import KomparatorZrodelMeta

            meta = KomparatorZrodelMeta.get_instance()
            meta.ostatni_blad = f"pk={pk}: {e}"
            meta.save(update_fields=["ostatni_blad"])
            errors += 1

    return {
        "updated": updated,
        "errors": errors,
        "total": len(pks),
    }
