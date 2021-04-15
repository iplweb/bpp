import warnings

from import_common.core import (
    matchuj_autora,
    matchuj_publikacje,
    matchuj_wydawce,
    matchuj_zrodlo,
)
from pbn_api.client import PBNClient
from pbn_api.exceptions import HttpException, SciencistDoesNotExist
from pbn_api.models import (
    Conference,
    Country,
    Institution,
    Journal,
    Language,
    Publication,
    Publisher,
    Scientist,
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
        return klass.objects.create(
            pk=elem["mongoId"],
            status=elem["status"],
            verificationLevel=elem["verificationLevel"],
            verified=elem["verified"],
            versions=elem["versions"],
        )

    if elem["versions"] != v.versions:
        v.versions = elem["versions"]
        v.save()

    return v


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
            client.get_conferences_mnisw(status=status, page_size=1000), Conference
        )


def pobierz_zrodla(client: PBNClient):
    for status in ["DELETED", "ACTIVE"]:
        pobierz_mongodb(
            client.get_journals_mnisw(status=status, page_size=500), Journal
        )


def pobierz_wydawcow(client: PBNClient):
    for status in ["ACTIVE", "DELETED"]:
        pobierz_mongodb(
            client.get_publishers_mnisw(status=status, page_size=500), Publisher
        )


def pobierz_ludzi(client: PBNClient):
    for status in ["ACTIVE", "DELETED"]:
        pobierz_mongodb(client.get_people(status=status, page_size=20000), Scientist)


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


def pobierz_ludzi_z_uczelni(client: PBNClient, instutition_id):
    """
    Ta procedura pobierze dane wszystkich osob z uczelni, mozna uruchamiac
    zamiast pobierz_ludzi
    """
    for person in client.get_people_by_institution_id(instutition_id):
        autor = matchuj_autora(
            imiona=person.get("firstName"),
            nazwisko=person.get("lastName"),
            orcid=person.get("orcid"),
            pbn_uid_id=person.get("personId"),
            tytul_str=person.get("title"),
        )
        if autor is None:
            warnings.warn(f"Brak dopasowania w jednostce dla autora {person}")
            continue

        scientist = client.get_person_by_id(person["personId"])
        scientist = zapisz_mongodb(scientist, Scientist)

        if autor.pbn_uid_id is None or autor.pbn_uid_id != scientist.pk:
            autor.pbn_uid = scientist
            autor.save()


def integruj_autorow_z_uczelni(client: PBNClient, instutition_id):
    """
    Ta procedure uruchamiamy dopiero po zaciągnięciu bazy osób.
    """
    for person in client.get_people_by_institution_id(instutition_id):
        autor = matchuj_autora(
            imiona=person.get("firstName"),
            nazwisko=person.get("lastName"),
            orcid=person.get("orcid"),
            pbn_uid_id=person.get("personId"),
            tytul_str=person.get("title"),
        )
        if autor is None:
            warnings.warn(f"Brak dopasowania w jednostce dla autora {person}")
            continue

        if autor.pbn_uid_id is None or autor.pbn_uid_id != person.get("personId"):
            try:
                autor.pbn_uid = Scientist.objects.get(pk=person["personId"])
            except Scientist.DoesNotExist:
                raise SciencistDoesNotExist(
                    "Brak odwzorowania dla naukowca w tabeli pbn_api_scientist, "
                    "zaciągnij najpierw listę autorów z PBNu"
                )
            autor.save()


def integruj_zrodla():
    for elem in Journal.objects.all():
        z = matchuj_zrodlo(
            elem.value("object", "title"),
            elem.value_or_none("object", "issn"),
            elem.value_or_none("object", "eissn"),
        )

        if z is not None:
            if z.pbn_uid_id is None:
                z.pbn_uid_id = elem
                z.save()


def integruj_wydawcow():
    for elem in Publisher.objects.all():
        w = matchuj_wydawce(elem.value("object", "publisherName"))
        if w is not None:
            if w.pbn_uid_id is None and w.pbn_uid_id != elem.pk:
                w.pbn_uid_id = elem.pk
                w.save()


def integruj_publikacje():
    for elem in Publication.objects.all():
        for klass in Wydawnictwo_Ciagle, Wydawnictwo_Zwarte:
            p = matchuj_publikacje(
                klass,
                elem.value("object", "title"),
                elem.value("object", "year"),
                elem.value_or_none("object", "doi"),
                elem.value_or_none("object", "publicUri"),
            )
            if p is not None:
                if p.pbn_uid_id is None or p.pbn_uid_id != elem.pk:
                    p.pbn_uid_id = elem.pk
                    p.save()
                break
