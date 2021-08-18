from django.db.models import Q

from import_common.normalization import (
    normalize_doi,
    normalize_isbn,
    normalize_public_uri,
    normalize_tytul_publikacji,
)
from pbn_api.models import Publication


def matchuj_pbn_api_publication(title, year, doi, public_uri, isbn, zrodlo):

    title = normalize_tytul_publikacji(title)
    query = Q(title__istartswith=title, year=year)

    doi = normalize_doi(doi)
    if doi:
        query |= Q(doi=doi, year=year)

    public_uri = normalize_public_uri(public_uri)
    if public_uri:
        query |= Q(publicUri=public_uri, year=year)

    isbn = normalize_isbn(isbn)
    if isbn:
        query |= Q(isbn=isbn, year=year)

    res = Publication.objects.filter(query)
    if res.count() == 1:
        return res.first()
    else:
        if zrodlo is not None and zrodlo.pbn_uid_id is not None:
            print(f"Szukam po zrodle, {res.count()}")
            for elem in res:
                if elem.journal and elem.journal["id"] == zrodlo.pbn_uid_id:
                    return elem
