"""Publication synchronization operations for PBN integrator."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

from django.db.models import Q

from bpp.const import PBN_MIN_ROK
from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from bpp.util import pbar
from pbn_api.exceptions import (
    HttpException,
    NoFeeDataException,
    NoPBNUIDException,
    SameDataUploadedRecently,
    WillNotExportError,
)
from pbn_api.models import SentData
from pbn_integrator.utils.constants import (
    PBN_KOMUNIKAT_DOI_ISTNIEJE,
    PBN_KOMUNIKAT_ISBN_ISTNIEJE,
)
from pbn_integrator.utils.django_imports import normalize_doi, normalize_isbn
from pbn_integrator.utils.publications import _pobierz_prace_po_elemencie

if TYPE_CHECKING:
    from pbn_api.client import PBNClient


def wydawnictwa_zwarte_do_synchronizacji():
    """Get queryset of Wydawnictwo_Zwarte ready for synchronization.

    Returns:
        QuerySet of Wydawnictwo_Zwarte.
    """
    return (
        Wydawnictwo_Zwarte.objects.filter(rok__gte=PBN_MIN_ROK)
        .exclude(charakter_formalny__rodzaj_pbn=None)
        .exclude(Q(isbn=None) | Q(isbn=""), Q(e_isbn=None) | Q(e_isbn=""))
        .exclude(jezyk__pbn_uid_id=None)
        .exclude(
            (Q(doi=None) | Q(doi=""))
            & Q(public_www="")
            & Q(www="")
            & (
                Q(wydawnictwo_nadrzedne__isnull=True)
                | (
                    Q(wydawnictwo_nadrzedne__www="")
                    & Q(wydawnictwo_nadrzedne__public_www="")
                )
            )
        )
        # rekordy bez WWW wysylamy gdy jest okreslone nadrzedne + nadrzende ma WWW
    )


def wydawnictwa_ciagle_do_synchronizacji():
    """Get queryset of Wydawnictwo_Ciagle ready for synchronization.

    Returns:
        QuerySet of Wydawnictwo_Ciagle.
    """
    return (
        Wydawnictwo_Ciagle.objects.filter(rok__gte=PBN_MIN_ROK)
        .exclude(jezyk__pbn_uid_id=None)
        .exclude(charakter_formalny__rodzaj_pbn=None)
        .exclude((Q(doi=None) | Q(doi="")) & Q(public_www="") & Q(www=""))
    )


def _synchronizuj_pojedyncza_publikacje(  # noqa: C901
    client,
    rec,
    force_upload=False,
    export_pk_zero=None,
    delete_statements_before_upload=False,
):
    """Synchronize a single publication to PBN.

    Args:
        client: PBN client.
        rec: BPP record.
        force_upload: Whether to force upload.
        export_pk_zero: Export pk zero setting.
        delete_statements_before_upload: Whether to delete statements before upload.
    """
    try:
        client.sync_publication(
            rec,
            force_upload=force_upload,
            export_pk_zero=export_pk_zero,
            delete_statements_before_upload=delete_statements_before_upload,
        )
    except SameDataUploadedRecently:
        pass
    except HttpException as e:
        if e.status_code == 400:
            if rec.pbn_uid_id is not None and (
                PBN_KOMUNIKAT_ISBN_ISTNIEJE in e.content
                or PBN_KOMUNIKAT_DOI_ISTNIEJE in e.content
            ):
                warnings.warn(
                    f"UWAGA: rekord z BPP {rec} mimo posiadania PBN UID {rec.pbn_uid_id} dostał"
                    f"przy synchronizacji komunkat: {e.content} !! Sprawa DO SPRAWDZENIA RECZNIE",
                    stacklevel=2,
                )
                return

            ret = None

            if PBN_KOMUNIKAT_ISBN_ISTNIEJE in e.content:
                if (
                    hasattr(rec, "isbn")
                    and hasattr(rec, "e_isbn")
                    and (rec.isbn is not None or rec.e_isbn is not None)
                    and (normalize_isbn(rec.isbn) or normalize_isbn(rec.e_isbn))
                ):
                    isbn_value = normalize_isbn(rec.isbn or rec.e_isbn)
                    ret = _pobierz_prace_po_elemencie(
                        client, "isbn", isbn_value, value_from_rec=rec
                    )

            elif PBN_KOMUNIKAT_DOI_ISTNIEJE in e.content:
                if (
                    hasattr(rec, "doi")
                    and rec.doi is not None
                    and normalize_doi(rec.doi)
                ):
                    doi_value = normalize_doi(rec.doi)
                    ret = _pobierz_prace_po_elemencie(
                        client, "doi", doi_value, value_from_rec=rec
                    )

            else:
                warnings.warn(
                    f"{rec.pk},{rec.tytul_oryginalny},{rec.rok},PBN Server Error: {e.content}",
                    stacklevel=2,
                )
                return

            if ret is None or rec not in ret:
                # Jeżeli rekordu synchronizowanego nie ma wśród rekordów pobranych - zmatchowanych
                # przez funkcję _pobierz_prace_po_elemencie, to wyjdź teraz:
                return

            # Rekord znalazł się na liście zmatchowanych przez funkcję _pobierz_po_elemencie,
            # nadano mu pbn_uid_id. Odśwież to ID z bazy, uruchom jeszcze raz synchronizację
            # rekordu:
            rec.refresh_from_db()
            assert rec.pbn_uid_id is not None
            return _synchronizuj_pojedyncza_publikacje(client, rec)

        if e.status_code == 500:
            warnings.warn(
                f"{rec.pk},{rec.tytul_oryginalny},{rec.rok},PBN Server Error: {e.content}",
                stacklevel=2,
            )

        if e.status_code == 403:
            # Jezeli przytrafi się wyjątek taki, jak poniżej:
            #
            # pbn_api.exceptions.HttpException: (403, '/api/v1/publications', '{"code":403,"message":"Forbidden",
            # "description":"W celu poprawnej autentykacji należy podać poprawny token użytkownika aplikacji.
            # Podany token użytkownika X w ramach aplikacji Y nie istnieje lub został unieważniony!"}')
            #
            # to go podnieś. Jeżeli autoryzacja nie została przeprowadzona poprawnie, to nie chcemy kontynuować
            # dalszego procesu synchronizacji prac.
            raise e

    except WillNotExportError as e:
        warnings.warn(
            f"{rec.pk},{rec.tytul_oryginalny},{rec.rok},nie wyeksportuje, bo: {e}",
            stacklevel=2,
        )


def synchronizuj_publikacje(
    client,
    force_upload=False,
    only_bad=False,
    only_new=False,
    skip=0,
    export_pk_zero=None,
    delete_statements_before_upload=False,
):
    """Synchronize publications to PBN.

    This command exports all publications in the system, starting from books,
    through chapters, to serial publications.

    Args:
        client: PBN client.
        force_upload: Force re-upload regardless of SentData status.
        only_bad: Export only records that have a failed export entry in SentData.
        only_new: Export only records that don't have an entry in SentData.
        skip: Number of records to skip.
        export_pk_zero: Export pk zero setting.
        delete_statements_before_upload: Whether to delete statements before upload.
    """
    assert not (only_bad and only_new), "Te parametry wykluczają się wzajemnie"
    #
    # Wydawnictwa zwarte
    #
    zwarte_baza = wydawnictwa_zwarte_do_synchronizacji()

    if only_bad:
        zwarte_baza = zwarte_baza.filter(
            pk__in=SentData.objects.bad_uploads(Wydawnictwo_Zwarte)
        )

    if only_new:
        # Nie synchronizuj prac ktore juz sa w SentData
        zwarte_baza = zwarte_baza.exclude(
            pk__in=SentData.objects.ids_for_model(Wydawnictwo_Zwarte)
            .values_list("pk", flat=True)
            .distinct()
        )

    for rec in pbar(
        zwarte_baza.filter(wydawnictwo_nadrzedne_id=None),
        label="sync_zwarte_ksiazki",
    ):
        _synchronizuj_pojedyncza_publikacje(
            client,
            rec,
            force_upload=force_upload,
            delete_statements_before_upload=delete_statements_before_upload,
            export_pk_zero=export_pk_zero,
        )

    for rec in pbar(
        zwarte_baza.exclude(wydawnictwo_nadrzedne_id=None),
        label="sync_zwarte_rozdzialy",
    ):
        _synchronizuj_pojedyncza_publikacje(
            client,
            rec,
            force_upload=force_upload,
            delete_statements_before_upload=delete_statements_before_upload,
            export_pk_zero=export_pk_zero,
        )

    #
    # Wydawnicwa ciagle
    #
    ciagle_baza = wydawnictwa_ciagle_do_synchronizacji()

    if only_bad:
        ciagle_baza = ciagle_baza.filter(
            pk__in=SentData.objects.bad_uploads(Wydawnictwo_Ciagle)
        )

    if only_new:
        # Nie synchronizuj prac ktore juz sa w SentData
        ciagle_baza = ciagle_baza.exclude(
            pk__in=SentData.objects.ids_for_model(Wydawnictwo_Ciagle)
            .values_list("pk", flat=True)
            .distinct()
        )

    for rec in pbar(
        ciagle_baza,
        label="sync_ciagle",
    ):
        _synchronizuj_pojedyncza_publikacje(
            client,
            rec,
            force_upload=force_upload,
            delete_statements_before_upload=delete_statements_before_upload,
            export_pk_zero=export_pk_zero,
        )


def wyslij_informacje_o_platnosciach(client: PBNClient, rok=None):
    """Send payment information for publications to PBN.

    Args:
        client: PBN client.
        rok: Optional year filter.
    """
    for model in Wydawnictwo_Ciagle, Wydawnictwo_Zwarte:
        qset = model.objects.rekordy_z_oplata()
        if rok:
            qset = qset.filter(rok=rok)

        for elem in pbar(qset):
            try:
                client.upload_publication_fee(elem)
            except NoPBNUIDException:
                try:
                    client.upload_publication(elem)
                except Exception as e:
                    print(
                        f"Podczas aktualizacji pracy {elem.tytul_oryginalny, elem.pk} wystąpił błąd: {e}. Wczytaj "
                        f"dane tej pracy ręcznie. "
                    )
            except NoFeeDataException:
                pass
            except HttpException as exc:
                if (
                    exc.status_code == 400
                    and exc.content.find("Validation failed") >= 0
                    and exc.content.find("no.institution.profile.publication") >= 0
                ):
                    print(
                        f"Publikacja {elem.tytul_oryginalny} nie wystepuje na profilu instytucji!"
                    )
