from pbn_api.client import PBNClient
from pbn_api.exceptions import HttpException
from pbn_api.models import (
    Conference,
    Country,
    Institution,
    Journal,
    Language,
    Publication,
    Publisher,
    Sciencist,
)

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from bpp.util import pbar


def integruj_jezyki(client):
    for remote_lang in client.get_languages():

        try:
            lang = Language.objects.get(code=remote_lang["code"])
        except Language.DoesNotExist:
            lang = Language.objects.create(
                code=remote_lang["code"], language=remote_lang["language"]
            )
            continue

        if remote_lang["language"] != lang.language:
            lang.language = remote_lang["language"]
            lang.save()


def integruj_kraje(client):
    for remote_country in client.get_countries():

        try:
            c = Country.objects.get(code=remote_country["code"])
        except Country.DoesNotExist:
            c = Country.objects.create(
                code=remote_country["code"], description=remote_country["description"]
            )
            continue

        if remote_country["description"] != c.description:
            c.description = remote_country["description"]
            c.save()


def zapisz_mongodb(elem, klass):
    try:
        v = klass.objects.get(pk=elem["mongoId"])
    except klass.DoesNotExist:
        klass.objects.create(
            pk=elem["mongoId"],
            status=elem["status"],
            verificationLevel=elem["verificationLevel"],
            verified=elem["verified"],
            versions=elem["versions"],
        )
        return

    if elem["versions"] != v.versions:
        v.versions = elem["versions"]
        v.save()


def pobierz_mongodb(elems, klass):
    for elem in pbar(elems, elems.total_elements):
        zapisz_mongodb(elem, klass)


def pobierz_instytucje(client: PBNClient):
    for status in ["ACTIVE", "DELETED"]:
        pobierz_mongodb(
            client.get_institutions(status=status, page_size=200), Institution
        )


def pobierz_konferencje(client: PBNClient):
    for status in ["DELETED", "ACTIVE"]:
        pobierz_mongodb(
            client.get_conferences(status=status, page_size=1000), Conference
        )


def pobierz_zrodla(client: PBNClient):
    for status in ["DELETED", "ACTIVE"]:
        pobierz_mongodb(client.get_journals(status=status, page_size=500), Journal)


def pobierz_wydawcow(client: PBNClient):
    for status in ["ACTIVE", "DELETED"]:
        pobierz_mongodb(client.get_publishers(status=status, page_size=500), Publisher)


def pobierz_ludzi(client: PBNClient):
    for status in ["ACTIVE", "DELETED"]:
        pobierz_mongodb(client.get_people(status=status, page_size=20000), Sciencist)


def normalize_doi(s):
    return s.strip()


def pobierz_prace_po_doi(client: PBNClient):
    for klass in Wydawnictwo_Ciagle, Wydawnictwo_Zwarte:
        for doi in pbar(
            klass.objects.all()
            .exclude(doi=None)
            .values_list("doi", flat=True)
            .distinct()
        ):
            try:
                elem = client.get_publication_by_doi(normalize_doi(doi))
            except HttpException as e:
                if e.status_code == 422:
                    # Publication with DOI 10.1136/annrheumdis-2018-eular.5236 was not exists!
                    print(f"\r\nBrak pracy z DOI {doi} w PBNie")
                    continue
                raise e

            zapisz_mongodb(elem, Publication)
