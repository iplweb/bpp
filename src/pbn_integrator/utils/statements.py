"""Statement operations for PBN integrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.postgres.search import TrigramSimilarity
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.functions import Length
from tqdm import tqdm

from bpp.models import (
    Autor_Dyscyplina,
    Rekord,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)
from bpp.util import pbar
from pbn_api.exceptions import StatementDeletionError
from pbn_api.models import OswiadczenieInstytucji, Publication
from pbn_integrator.utils.django_imports import normalize_tytul_publikacji
from pbn_integrator.utils.integration import zweryfikuj_lub_stworz_match

if TYPE_CHECKING:
    pass


def integruj_oswiadczenia_z_instytucji_pojedyncza_praca(  # noqa: C901
    elem,
    noted_pub,
    noted_aut,
    missing_publication_callback=None,
    inconsistency_callback=None,
    default_jednostka=None,
):
    """Integrate statements for a single publication.

    Args:
        elem: OswiadczenieInstytucji object.
        noted_pub: Set of noted publication IDs.
        noted_aut: Set of noted author IDs.
        missing_publication_callback: Optional callback for missing publications.
        inconsistency_callback: Optional callback for reporting inconsistencies.
            Signature: inconsistency_callback(
                inconsistency_type: str,
                pbn_publication=None,
                pbn_author=None,
                bpp_publication=None,
                bpp_author=None,
                discipline=None,
                message: str = "",
                action_taken: str = "",
            )
        default_jednostka: Optional default unit to assign when updating
            from "Obca jednostka" to a proper unit during discipline assignment.
    """
    pub = elem.get_bpp_publication()
    if pub is None:
        if missing_publication_callback:
            pub = missing_publication_callback(elem.publicationId_id)
            assert pub is not None
        else:
            pub = elem.publicationId.matchuj_do_rekordu_bpp()

            if pub is None:
                if elem.publicationId_id not in noted_pub:
                    msg = (
                        f"Brak odpowiednika publikacji w BPP dla pracy "
                        f"{elem.publicationId}, parametr inOrcid oraz dyscypliny "
                        f"dla tej pracy nie zostanie zaimportowany!"
                    )
                    print(f"\r\nPPP {msg}")
                    if inconsistency_callback:
                        inconsistency_callback(
                            inconsistency_type="publication_not_found",
                            pbn_publication=elem.publicationId,
                            message=msg,
                        )
                    noted_pub.add(elem.publicationId_id)
                return
            else:
                zweryfikuj_lub_stworz_match(elem.publicationId, pub)

    if isinstance(pub, Rekord):
        pub = pub.original

    aut = elem.get_bpp_autor()
    if aut is None:
        if elem.personId_id not in noted_aut:
            msg = (
                f"Brak odpowiednika autora w BPP dla autora {elem.personId}, "
                f"parametr inOrcid dla tego autora nie zostanie zaimportowany!"
            )
            print(f"\r\nAAA {msg}")
            if inconsistency_callback:
                inconsistency_callback(
                    inconsistency_type="author_not_in_bpp",
                    pbn_publication=elem.publicationId,
                    pbn_author=elem.personId,
                    bpp_publication=pub,
                    message=msg,
                )
            noted_aut.add(elem.publicationId_id)
        return

    try:
        rec: Wydawnictwo_Zwarte_Autor = pub.autorzy_set.get(
            autor=aut, typ_odpowiedzialnosci=elem.get_typ_odpowiedzialnosci()
        )
    except pub.autorzy_set.model.DoesNotExist:
        msg = (
            f"Po stronie PBN: {elem.publicationId}, "
            f"po stronie BPP: {pub}, {aut} -- nie ma ta praca takiego autora!"
        )
        print(f"===========================================================\nXXX {msg}")
        if inconsistency_callback:
            inconsistency_callback(
                inconsistency_type="author_not_found",
                pbn_publication=elem.publicationId,
                pbn_author=elem.personId,
                bpp_publication=pub,
                bpp_author=aut,
                discipline=elem.get_bpp_discipline() if elem.disciplines else None,
                message=msg,
            )

        try:
            rec = pub.autorzy_set.get(
                autor__nazwisko__iexact=aut.nazwisko,
                autor__imiona__iexact=aut.imiona,
                typ_odpowiedzialnosci=elem.get_typ_odpowiedzialnosci(),
            )
        except pub.autorzy_set.model.DoesNotExist:
            try:
                rec = pub.autorzy_set.get(
                    autor__nazwisko__iexact=aut.imiona,
                    autor__imiona__iexact=aut.nazwisko,
                    typ_odpowiedzialnosci=elem.get_typ_odpowiedzialnosci(),
                )
            except pub.autorzy_set.model.DoesNotExist:
                msg = "Nie mogę naprawić tego automatycznie - sprawdź ręcznie"
                print(
                    f"XXX {msg}\n"
                    "==========================================================="
                )
                if inconsistency_callback:
                    inconsistency_callback(
                        inconsistency_type="author_needs_manual_fix",
                        pbn_publication=elem.publicationId,
                        pbn_author=elem.personId,
                        bpp_publication=pub,
                        bpp_author=aut,
                        discipline=(
                            elem.get_bpp_discipline() if elem.disciplines else None
                        ),
                        message=msg,
                        action_taken="Rekord wymaga ręcznej korekty",
                    )
                return

        if elem.disciplines:
            discipline = elem.get_bpp_discipline()
            msg = (
                f"Nadpisuję w tej pracy autora {rec.autor} autorem {aut}, "
                f"wyślij tę pracę do PBN ponownie! (dyscyplina: {discipline})"
            )
            print(
                f"XXX {msg}\n"
                f"==========================================================="
            )
            if inconsistency_callback:
                inconsistency_callback(
                    inconsistency_type="author_auto_fixed",
                    pbn_publication=elem.publicationId,
                    pbn_author=elem.personId,
                    bpp_publication=pub,
                    bpp_author=aut,
                    discipline=discipline,
                    message=msg,
                    action_taken=f"Autor zmieniony z {rec.autor} na {aut}",
                )
            rec.autor = aut
        else:
            msg = (
                f"Nie nadpisuję w tej pracy autora {rec.autor} autorem {aut}, "
                f"bo nie ma dyscyplin - sprawdź rekord ręcznie"
            )
            print(
                f"XXX {msg}\n"
                f"==========================================================="
            )
            if inconsistency_callback:
                inconsistency_callback(
                    inconsistency_type="no_override_without_disciplines",
                    pbn_publication=elem.publicationId,
                    pbn_author=elem.personId,
                    bpp_publication=pub,
                    bpp_author=aut,
                    message=msg,
                    action_taken="Brak działania - brak dyscyplin",
                )

    if elem.disciplines:
        if elem.get_bpp_discipline().pk != rec.dyscyplina_naukowa_id:
            rec.dyscyplina_naukowa_id = elem.get_bpp_discipline().pk
            try:
                rec.clean()
            except ValidationError:
                try:
                    Autor_Dyscyplina.objects.get(rok=rec.rekord.rok, autor=rec.autor)
                    raise Exception(
                        f"Nie ma przypsiania do {elem.get_bpp_discipline()}, ale jakeis inne jest..."
                    )
                except Autor_Dyscyplina.DoesNotExist:
                    rec.autor.autor_dyscyplina_set.update_or_create(
                        rok=rec.rekord.rok,
                        defaults={"dyscyplina_naukowa": elem.get_bpp_discipline()},
                    )

        # Jeśli dyscyplina jest ustawiana i jednostka to "Obca jednostka",
        # zaktualizuj jednostkę na domyślną i ustaw flagi afiliacji
        if (
            default_jednostka is not None
            and rec.jednostka_id is not None
            and not rec.jednostka.skupia_pracownikow
        ):
            rec.jednostka = default_jednostka
            rec.afiliuje = True
            rec.zatrudniony = True

    rec.profil_orcid = elem.inOrcid
    rec.save()


def integruj_oswiadczenia_z_instytucji(
    missing_publication_callback=None,
    callback=None,
    inconsistency_callback=None,
    default_jednostka=None,
):
    """Integrate all institution statements.

    Args:
        missing_publication_callback: Optional callback for missing publications.
        callback: Optional progress callback.
        inconsistency_callback: Optional callback for reporting inconsistencies.
        default_jednostka: Optional default unit to assign when updating
            from "Obca jednostka" to a proper unit during discipline assignment.
    """
    noted_pub = set()
    noted_aut = set()
    for elem in pbar(
        OswiadczenieInstytucji.objects.all(),
        label="integruj_oswiadczenia_z_instytucji",
        callback=callback,
    ):
        integruj_oswiadczenia_z_instytucji_pojedyncza_praca(
            elem,
            noted_pub,
            noted_aut,
            missing_publication_callback,
            inconsistency_callback,
            default_jednostka,
        )


def integruj_oswiadczenia_pbn_first_import(  # noqa: C901
    client=None,
    default_jednostka=None,
    dopisuj_zwrotnie_dyscypliny_autorom=True,
    koryguj_afiliacje=True,
):
    """Integrate statements for first PBN import.

    Args:
        client: PBN client.
        default_jednostka: Default unit for new records.
        dopisuj_zwrotnie_dyscypliny_autorom: Whether to add disciplines back to authors.
        koryguj_afiliacje: Whether to correct affiliations.
    """
    first = True
    for oswiadczenie in tqdm(OswiadczenieInstytucji.objects.all()):
        bpp_pub = oswiadczenie.get_bpp_publication()

        if bpp_pub is None:
            if client is not None:
                from pbn_integrator.importer import importuj_publikacje_instytucji

                bpp_pub = importuj_publikacje_instytucji(
                    client, default_jednostka, oswiadczenie.publicationId_id
                )

                if isinstance(bpp_pub, Rekord):
                    bpp_pub = bpp_pub.original

            if bpp_pub is None:
                print(
                    f"Brak odpowiednika publikacji po stronie BPP dla pracy w PBN {oswiadczenie.publicationId}, "
                    f"moze zaimportuj baze raz jeszcze"
                )
                continue

        bpp_aut = oswiadczenie.get_bpp_autor()
        bpp_dyscyplina = oswiadczenie.get_bpp_discipline()
        bpp_typ_odpowiedzialnosci = oswiadczenie.get_typ_odpowiedzialnosci()

        try:
            rekord_aut = bpp_pub.autorzy_set.get(
                autor=bpp_aut, typ_odpowiedzialnosci=bpp_typ_odpowiedzialnosci
            )
        except (
            Wydawnictwo_Zwarte_Autor.DoesNotExist,
            Wydawnictwo_Ciagle_Autor.DoesNotExist,
        ):
            if first:
                print(
                    "Tytuł;Rok;mongoId;Autor przypisany;UID autora przypisanego;"
                    "Autor oświadczony;UID autora z oświadczeń"
                )
                first = False

            try:
                przypisany = bpp_pub.autorzy_set.get(
                    autor__nazwisko=bpp_aut.nazwisko, autor__imiona=bpp_aut.imiona
                ).autor
            except (
                Wydawnictwo_Zwarte_Autor.DoesNotExist,
                Wydawnictwo_Ciagle_Autor.DoesNotExist,
            ):

                class Przypisany:
                    pbn_uid_id = "NIE UMIEM ZLOKALIZOWAC"

                    def __str__(self):
                        return "NIE UMIEM ZLOKALIZOWAC"

                przypisany = Przypisany()

            print(
                f"{bpp_pub.tytul_oryginalny};{bpp_pub.rok};{bpp_pub.pbn_uid_id};{przypisany};{przypisany.pbn_uid_id};"
                f"{oswiadczenie.personId.lastName} {oswiadczenie.personId.name};{oswiadczenie.personId_id}"
            )
            continue

        if (
            rekord_aut.dyscyplina_naukowa is not None
            and rekord_aut.dyscyplina_naukowa != bpp_dyscyplina
        ):
            raise NotImplementedError(
                f"dyscyplina juz jest w bazie i sie rozni {bpp_pub}"
            )

        rekord_aut.dyscyplina_naukowa = bpp_dyscyplina

        if bpp_dyscyplina is not None and dopisuj_zwrotnie_dyscypliny_autorom:
            # Spróbujmy zwrotnie przypisać autorowi dyscyplinę za dany rok:
            try:
                ad = bpp_aut.autor_dyscyplina_set.get(rok=bpp_pub.rok)
            except Autor_Dyscyplina.DoesNotExist:
                # Nie ma przypisania za dany rok -- tworzomy nowy wpis
                bpp_aut.autor_dyscyplina_set.create(
                    rok=bpp_pub.rok, dyscyplina_naukowa=bpp_dyscyplina
                )
            else:
                # JEst przypisanie. Czy występuje w nim dyscuyplina?
                if (
                    ad.dyscyplina_naukowa == bpp_dyscyplina
                    or ad.subdyscyplina_naukowa == bpp_dyscyplina
                ):
                    # Tak, występuje, zostawiamy.
                    pass
                elif (
                    ad.dyscyplina_naukowa != bpp_dyscyplina
                    and ad.subdyscyplina_naukowa is None
                ):
                    # Nie, nie wystepuję, ale można wpisać do pustej sub-dyscypliny
                    ad.subdyscyplina_naukowa = bpp_dyscyplina
                    ad.save()
                else:
                    # Nie, nie występuje i nie można wpisać
                    raise NotImplementedError(
                        f"Autor miałby mieć 3 przypisania dyscyplin za {bpp_pub.rok}, sprawdź kod"
                    )

        if koryguj_afiliacje:
            if rekord_aut.jednostka.skupia_pracownikow and not rekord_aut.afiliuje:
                rekord_aut.afiliuje = True

            if not rekord_aut.jednostka.skupia_pracownikow and rekord_aut.afiliuje:
                rekord_aut.afiliuje = False

        rekord_aut.save()

        # Przelicz punktację
        bpp_pub.save()


def usun_wszystkie_oswiadczenia(client):
    """Delete all statements from PBN.

    Args:
        client: PBN client.
    """
    for elem in pbar(
        OswiadczenieInstytucji.objects.all(), label="usun_wszystkie_oswiadczenia"
    ):
        with transaction.atomic():
            try:
                elem.sprobuj_skasowac_z_pbn(pbn_client=client)
            except StatementDeletionError as e:
                if e.status_code == 400 and (
                    "Nie istnieją oświadczenia" in e.content
                    or "Nie istnieje oświadczenie" in e.content
                ):
                    pass
                else:
                    raise e

            elem.delete()


def usun_zerowe_oswiadczenia(client):
    """Delete zero-point statements from PBN.

    Args:
        client: PBN client.
    """
    for klass in Wydawnictwo_Ciagle, Wydawnictwo_Zwarte:
        zerowe = klass.objects.exclude(pbn_uid=None).filter(punkty_kbn=0)

        for elem in pbar(
            OswiadczenieInstytucji.objects.filter(
                publicationId_id__in=zerowe.values_list("pbn_uid_id", flat=True)
            ),
            label=f"usun_zerowe dla {klass}",
        ):
            with transaction.atomic():
                try:
                    elem.sprobuj_skasowac_z_pbn(pbn_client=client)
                except StatementDeletionError as e:
                    if e.status_code == 400 and (
                        "Nie istnieją oświadczenia" in e.content
                        or "Nie istnieje oświadczenie" in e.content
                    ):
                        pass
                    else:
                        raise e

                elem.delete()


def wyswietl_niezmatchowane_ze_zblizonymi_tytulami():
    """Display unmatched publications with similar titles."""
    for model, klass in [
        (Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor),
        (Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor),
    ]:
        for rekord in (
            model.objects.filter(
                pk__in=klass.objects.exclude(dyscyplina_naukowa=None)
                .filter(rekord__pbn_uid_id=None)
                .values("rekord")
                .distinct()
            )
            .annotate(tytul_oryginalny_length=Length("tytul_oryginalny"))
            .filter(tytul_oryginalny_length__gte=10)
        ):
            print(
                f"\r\nRekord z dyscyplinami, bez dopasowania w PBN: {rekord.rok} {rekord}"
            )

            nt = normalize_tytul_publikacji(rekord.tytul_oryginalny)

            res = (
                Publication.objects.annotate(
                    similarity=TrigramSimilarity("title", nt),
                )
                .filter(year=rekord.rok)
                .filter(similarity__gt=0.5)
                .order_by("-similarity")
            )

            for elem in res[:5]:
                print("- MOZE: ", elem.mongoId, elem.title, elem.similarity)


def sprawdz_ilosc_autorow_przy_zmatchowaniu():
    """Check author count differences between matched publications."""
    import csv

    res = csv.writer(open("rozne-ilosci-autorow.csv", "w"))
    res.writerow(
        [
            "Komunikat",
            "Praca w BPP",
            "Praca w PBN",
            "Rok",
            "Autorzy w BPP",
            "Autorzy w PBN",
            "Nazwiska w BPP",
            "Nazwiska w PBN",
        ]
    )
    for praca in Rekord.objects.exclude(pbn_uid_id=None).order_by(
        "rok", "tytul_oryginalny"
    ):
        ca = praca.autorzy_set.all().count()
        pa = praca.pbn_uid.policz_autorow()
        if ca != pa:
            res.writerow(
                [
                    "Rozna ilosc autorow",
                    str(praca),
                    str(praca.pbn_uid),
                    str(praca.rok),
                    str(ca),
                    str(pa),
                    str(praca.opis_bibliograficzny_zapisani_autorzy_cache),
                    str(praca.pbn_uid.autorzy),
                ]
            )
