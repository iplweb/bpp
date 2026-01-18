"""Publisher handling for PBN importer."""

import logging

from django.core.management import call_command
from django.db import transaction

from bpp import const
from bpp.models import Wydawca
from bpp.models.wydawca import Poziom_Wydawcy
from pbn_api.models import Publisher
from pbn_integrator.utils import zapisz_mongodb

logger = logging.getLogger("pbn_import")


def _utworz_nowego_wydawce(publisher, points_to_poziom_map, verbosity):
    """Create a new publisher in BPP from PBN data."""
    nowy_wydawca = Wydawca.objects.create(
        nazwa=publisher.publisherName, pbn_uid=publisher
    )
    if verbosity > 1:
        print(f"1 Tworze nowego wydawce z MNISWID, {publisher.publisherName}")

    # Bulk create all Poziom_Wydawcy records at once instead of one-by-one
    poziomy_to_create = []
    for rok in const.PBN_LATA:
        points = publisher.points.get(str(rok))

        if not points:
            # Brak punktów w PBNie za dany rok
            continue

        if not points["accepted"]:
            raise NotImplementedError(
                f"Accepted = False dla {publisher} {rok}, co dalej?"
            )

        poziom = points_to_poziom_map.get(points["points"])
        assert poziom, f"Brak odpowiednika dla {points['points']}"

        poziomy_to_create.append(
            Poziom_Wydawcy(wydawca=nowy_wydawca, rok=rok, poziom=poziom)
        )

    if poziomy_to_create:
        Poziom_Wydawcy.objects.bulk_create(poziomy_to_create)


def _aktualizuj_poziomy_wydawcy(
    wydawca,
    publisher,
    rok,
    pbn_side,
    wydawca_side,
    get_poziom_bpp,
    poziom_to_points_map,
    verbosity,
):
    """Update publisher levels for a given year."""
    needs_recalc = set()

    if pbn_side is not None:
        if not pbn_side["accepted"]:
            raise NotImplementedError(
                f"Accepted = False dla {publisher} {rok}, co dalej?"
            )

        if wydawca_side is None:
            # Nie ma poziomu po naszej stronie dla tego rkou ,dodamy go:
            poziom_bpp = get_poziom_bpp(pbn_side)

            if verbosity > 1:
                print(f"2 Wydawca {wydawca}: dodaje poziom {poziom_bpp} za {rok} ")

            wydawca.poziom_wydawcy_set.create(rok=rok, poziom=poziom_bpp)
            needs_recalc.add((wydawca, rok))
        else:
            # Są obydwa poziomy: Publisher (PBN) i Wydawca (BPP)
            # porównaj, czy są ok:

            wydawca_side_poziom_translated = poziom_to_points_map.get(
                wydawca_side.poziom
            )

            if pbn_side["points"] != wydawca_side_poziom_translated:
                if verbosity > 1:
                    print(
                        f"5 Poziomy sie roznia dla {publisher} {rok}, "
                        f"ustawiam poziom z PBNu?"
                    )
                    wydawca_side.poziom = get_poziom_bpp(pbn_side)
                    needs_recalc.add((wydawca, rok))
                    wydawca_side.save()

    else:
        # pbn_side is None
        if wydawca_side is not None:
            print(f"4 PBN nie ma poziomu a wydawca ma, co robic? {publisher} {rok}")

    return needs_recalc


def importuj_jednego_wydawce(publisher, verbosity=1):
    poziom_to_points_map = {2: 200, 1: 80}
    points_to_poziom_map = {200: 2, 80: 1}

    def get_poziom_bpp(pbn_side):
        poziom_bpp = points_to_poziom_map.get(pbn_side["points"])
        if not poziom_bpp:
            raise NotImplementedError(
                f"Brak odpowiednika poziomu {pbn_side['points']} w mappingu"
            )
        return poziom_bpp

    # Single exists() check instead of duplicate calls
    has_wydawca = publisher.wydawca_set.exists()

    if not has_wydawca:
        # Nie ma takiego wydawcy w bazie BPP, spróbuj go zmatchować:
        nw = publisher.matchuj_wydawce()
        if nw is not None:
            if publisher.publisherName != nw.nazwa:
                print(
                    f"0 ZWERYFIKUJ FONETYCZNE DOPASOWANIE: "
                    f"{publisher.publisherName} do {nw.nazwa}"
                )
            nw.pbn_uid = publisher
            nw.save()
            has_wydawca = True

    if not has_wydawca:
        # Nie ma takiego wydawcy w bazie, utwórz go:
        _utworz_nowego_wydawce(publisher, points_to_poziom_map, verbosity)
        return True

    # Jest już taki wydawca i ma ustawiony match z PBN. Sprawdzimy mu jego poziomy:
    for wydawca in publisher.wydawca_set.all():
        # Nie pracujemy na aliasach
        wydawca = wydawca.get_toplevel()

        # Batch fetch all Poziom_Wydawcy records at once (single query)
        # instead of querying for each year separately (~10 queries)
        poziomy_dict = {pz.rok: pz for pz in wydawca.poziom_wydawcy_set.all()}

        for rok in const.PBN_LATA:
            pbn_side = publisher.points.get(str(rok))
            wydawca_side = poziomy_dict.get(rok)

            _aktualizuj_poziomy_wydawcy(
                wydawca,
                publisher,
                rok,
                pbn_side,
                wydawca_side,
                get_poziom_bpp,
                poziom_to_points_map,
                verbosity,
            )


def importuj_wydawcow(verbosity=1, callback=None):
    needs_mapping = False
    publishers = list(Publisher.objects.official())
    total = len(publishers)
    imported = 0
    logger.info(f"Importowanie wydawców: {total} wydawców do przetworzenia")

    with transaction.atomic():
        for i, publisher in enumerate(publishers, 1):
            if importuj_jednego_wydawce(publisher):
                needs_mapping = True
                imported += 1

            if callback:
                callback.update(i, total, f"Zaimportowano: {imported}")

    # To uruchamiamy poza transakcją - jeżeli były zmiany
    if needs_mapping:
        logger.info("Importowanie wydawców: uruchamiam mapowanie do publikacji...")
        call_command("zamapuj_wydawcow")
        logger.info("Importowanie wydawców: mapowanie zakończone")


def sciagnij_i_zapisz_wydawce(pbn_wydawca_id, client):
    res = client.get_publisher_by_id(pbn_wydawca_id)
    publisher = zapisz_mongodb(res, Publisher)
    importuj_jednego_wydawce(publisher)
    return Wydawca.objects.get(pbn_uid_id=pbn_wydawca_id)
