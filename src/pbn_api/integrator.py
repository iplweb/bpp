import warnings

from django.db.models import F, Func, Q

from import_common.core import matchuj_autora, matchuj_publikacje, matchuj_wydawce
from pbn_api.client import PBNClient
from pbn_api.exceptions import (
    HttpException,
    SameDataUploadedRecently,
    SciencistDoesNotExist,
)
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

from bpp.exceptions import WillNotExportError
from bpp.models import (
    Jednostka,
    Jezyk,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Zrodlo,
)
from bpp.util import pbar


def integruj_jezyki(client):
    for remote_lang in client.get_languages():

        try:
            lang = Language.objects.get(code=remote_lang["code"])
        except Language.DoesNotExist:
            lang = Language.objects.create(
                code=remote_lang["code"], language=remote_lang["language"]
            )

        if remote_lang["language"] != lang.language:
            lang.language = remote_lang["language"]
            lang.save()

    # Ustaw odpowiedniki w PBN dla jęyzków z bazy danych:
    for elem in Language.objects.all():
        try:
            qry = Q(skrot__istartswith=elem.language.get("639-2")) | Q(
                skrot__istartswith=elem.code
            )
            if elem.language.get("639-1"):
                qry |= Q(skrot__istartswith=elem.language["639-1"])

            jezyk = Jezyk.objects.get(qry)
        except Jezyk.DoesNotExist:
            if elem.language.get("pl") is not None:
                try:
                    jezyk = Jezyk.objects.get(
                        nazwa__istartswith=elem.language.get("pl")
                    )
                except Jezyk.DoesNotExist:
                    warnings.warn(f"Brak jezyka po stronie BPP: {elem}")
                    continue
            else:
                warnings.warn(f"Brak jezyka po stronie BPP: {elem}")
                continue

        if jezyk.pbn_uid_id is None:
            jezyk.pbn_uid = elem
            jezyk.save()


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


def pobierz_mongodb(elems, klass, pbar_label="pobierz_mongodb"):
    for elem in pbar(elems, elems.total_elements, pbar_label):
        zapisz_mongodb(elem, klass)


def pobierz_instytucje(client: PBNClient):
    for status in ["ACTIVE", "DELETED"]:
        pobierz_mongodb(
            client.get_institutions(status=status, page_size=200), Institution
        )


def integruj_uczelnie():
    uczelnia = Uczelnia.objects.get_default()

    try:
        u = Institution.objects.get(
            versions__contains=[{"current": True, "object": {"name": uczelnia.nazwa}}]
        )
    except Institution.DoesNotExist:
        raise Exception(f"Nie umiem dopasowac uczelni po nazwie: {uczelnia.nazwa}")

    if uczelnia.pbn_uid_id != u.mongoId:
        uczelnia.pbn_uid = u
        uczelnia.save()


def integruj_instytucje():
    uczelnia = Uczelnia.objects.get_default()
    assert uczelnia.pbn_uid_id

    for j in Jednostka.objects.filter(skupia_pracownikow=True):
        try:
            u = Institution.objects.get(
                versions__contains=[
                    {
                        "current": True,
                        "object": {"name": j.nazwa, "parentId": uczelnia.pbn_uid_id},
                    }
                ]
            )
        except Institution.MultipleObjectsReturned:
            warnings.warn(f"Liczne dopasowania dla jednostki: {j}")
            continue

        except Institution.DoesNotExist:
            warnings.warn(f"Brak dopasowania dla jednostki: {j}")
            continue

        if j.pbn_uid_id != u.mongoId:
            j.pbn_uid_id = u.mongoId
            j.save()


def pobierz_konferencje(client: PBNClient):
    for status in ["DELETED", "ACTIVE"]:
        pobierz_mongodb(
            client.get_conferences_mnisw(status=status, page_size=1000), Conference
        )


def pobierz_zrodla(client: PBNClient):
    for status in ["DELETED", "ACTIVE"]:
        pobierz_mongodb(
            client.get_journals(status=status, page_size=5000),
            Journal,
            pbar_label="pobierz_zrodla",
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


def pobierz_prace(client: PBNClient):
    for status in ["ACTIVE"]:  # "DELETED", "ACTIVE"]:
        pobierz_mongodb(
            client.get_publications(status=status, page_size=200), Publication
        )


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
    assert instutition_id is not None

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
    def fun(qry):
        try:
            u = Journal.objects.get(qry)
        except Journal.DoesNotExist:
            warnings.warn(f"Nie znaleziono dopasowania w PBN dla {zrodlo}")
            return False
        except Journal.MultipleObjectsReturned:
            warnings.warn(
                f"Znaleziono liczne dopasowania w PBN dla {zrodlo}, wybieram to z najdłuższym opisem"
            )
            u = (
                Journal.objects.filter(qry)
                .annotate(json_len=Func(F("versions"), function="pg_column_size"))
                .order_by("-json_len")
                .first()
            )

        zrodlo.pbn_uid = u
        zrodlo.save()
        return True

    for zrodlo in pbar(
        Zrodlo.objects.filter(pbn_uid_id=None), label="Integracja zrodel"
    ):
        qry = None

        if zrodlo.issn:
            qry = Q(
                versions__contains=[{"current": True, "object": {"issn": zrodlo.issn}}]
            )
            if fun(qry):
                continue

        if zrodlo.e_issn:
            qry = Q(
                versions__contains=[
                    {"current": True, "object": {"eissn": zrodlo.e_issn}}
                ]
            )
            if fun(qry):
                continue

        if qry is None:
            qry = Q(
                versions__contains=[
                    {"current": True, "object": {"title": zrodlo.nazwa}}
                ]
            )
            fun(qry)


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
                elem.value_or_none("object", "year"),
                elem.value_or_none("object", "doi"),
                elem.value_or_none("object", "publicUri"),
            )
            if p is not None:
                if p.pbn_uid_id is None or p.pbn_uid_id != elem.pk:
                    p.pbn_uid_id = elem.pk
                    p.save()
                break


def synchronizuj_publikacje(client, skip=0):
    for rec in pbar(
        Wydawnictwo_Ciagle.objects.filter(rok__gte=2017)
        .exclude(charakter_formalny__rodzaj_pbn=None)
        .exclude(Q(doi=None) & (Q(public_www=None) | Q(www=None)))
    ):
        try:
            client.sync_publication(rec)
        except SameDataUploadedRecently:
            pass
        except HttpException as e:
            if e.status_code in [400, 500]:
                warnings.warn(
                    f"{rec.pk},{rec.tytul_oryginalny},{rec.rok},PBN Error 500: {e.content}"
                )
                continue

            raise e
        except WillNotExportError as e:
            warnings.warn(
                f"{rec.pk},{rec.tytul_oryginalny},{rec.rok},nie wyeksportuje, bo: {e}"
            )
