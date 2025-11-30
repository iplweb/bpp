"""Global search functions for autocomplete views."""

from django.db.models.aggregates import Count

from bpp import const
from bpp.models import Jednostka
from bpp.models.autor import Autor
from bpp.models.zrodlo import Zrodlo
from pbn_api.models import Journal, Publication, Scientist

AUTOR_ONLY = (
    "pk",
    "nazwisko",
    "imiona",
    "poprzednie_nazwiska",
    "tytul__skrot",
    "aktualna_funkcja__nazwa",
    "pseudonim",
)

AUTOR_SELECT_RELATED = "tytul", "aktualna_funkcja"


def jest_czyms(s, dlugosc):
    """Check if string has exact length and no spaces."""
    if s is not None:
        if len(s) == dlugosc and s.find(" ") == -1:
            return True
    return False


def jest_orcid(s):
    """Check if string looks like an ORCID."""
    return jest_czyms(s, const.ORCID_LEN)


def jest_pbn_uid(s):
    """Check if string looks like a PBN UID."""
    return jest_czyms(s, const.PBN_UID_LEN)


def globalne_wyszukiwanie_autora(querysets, q):
    """Add author search querysets."""
    if jest_orcid(q):
        querysets.append(
            Autor.objects.filter(orcid__icontains=q)
            .only(*AUTOR_ONLY)
            .select_related(*AUTOR_SELECT_RELATED)
        )

    if jest_pbn_uid(q):
        querysets.append(
            Autor.objects.filter(pbn_uid_id=q).only(*AUTOR_ONLY).select_related("tytul")
        )

    querysets.append(
        Autor.objects.fulltext_filter(q)
        .annotate(Count("wydawnictwo_ciagle"))
        .only(*AUTOR_ONLY)
        .select_related(*AUTOR_SELECT_RELATED)
        .order_by("-search__rank", "-wydawnictwo_ciagle__count")
    )


def globalne_wyszukiwanie_jednostki(querysets, s):
    """Add unit search querysets."""

    def _fun(qry):
        return qry.only("pk", "nazwa", "wydzial__skrot").select_related("wydzial")

    querysets.append(_fun(Jednostka.objects.fulltext_filter(s)))

    if jest_pbn_uid(s):
        querysets.append(_fun(Jednostka.objects.filter(pbn_uid_id=s)))


def globalne_wyszukiwanie_zrodla(querysets, s):
    """Add source search querysets."""

    def _fun(qry):
        return qry.only("pk", "nazwa", "poprzednia_nazwa")

    rezultaty = Zrodlo.objects.fulltext_filter(s, normalization=8).order_by(
        "-search__rank", "nazwa"
    )
    querysets.append(_fun(rezultaty))

    if jest_pbn_uid(s):
        querysets.append(_fun(Zrodlo.objects.filter(pbn_uid_id=s)))


def globalne_wyszukiwanie_scientist(querysets, s):
    """Search for Scientists (people in PBN API) by PBN UID only."""
    if jest_pbn_uid(s):
        querysets.append(
            Scientist.objects.filter(pk=s).only(
                "pk", "lastName", "name", "qualifications"
            )
        )


def globalne_wyszukiwanie_journal(querysets, s):
    """Search for Journals (sources in PBN API) by PBN UID only."""
    if jest_pbn_uid(s):
        querysets.append(
            Journal.objects.filter(pk=s).only("pk", "title", "issn", "eissn")
        )


def globalne_wyszukiwanie_publication(querysets, s):
    """Search for Publications (publications in PBN API) by PBN UID only."""
    if jest_pbn_uid(s):
        querysets.append(
            Publication.objects.filter(pk=s).only("pk", "title", "doi", "isbn", "year")
        )
