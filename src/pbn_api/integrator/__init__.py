import csv
import json
import multiprocessing
import operator
import os
import sys
import warnings
from functools import reduce

import django
from django.db import transaction
from django.db.models import F, Func, IntegerField, Q
from django.db.models.functions import Length

from pbn_api.integrator import istarmap  # noqa

from bpp.const import PBN_MIN_ROK

try:
    django.setup()
except RuntimeError:
    pass

from import_common.core import matchuj_autora, matchuj_wydawce
from import_common.normalization import (
    normalize_doi,
    normalize_isbn,
    normalize_tytul_publikacji,
)
from pbn_api.client import PBNClient
from pbn_api.const import ACTIVE, DELETED
from pbn_api.exceptions import (
    BrakIDPracyPoStroniePBN,
    HttpException,
    NoFeeDataException,
    NoPBNUIDException,
    SameDataUploadedRecently,
    StatementDeletionError,
    WillNotExportError,
)
from pbn_api.integrator.threaded_page_getter import (
    ThreadedMongoDBSaver,
    threaded_page_getter,
)
from pbn_api.models import (
    Conference,
    Country,
    Discipline,
    DisciplineGroup,
    Institution,
    Journal,
    Language,
    OswiadczenieInstytucji,
    Publication,
    PublikacjaInstytucji,
    Publisher,
    Scientist,
    SentData,
)

from django.contrib.postgres.search import TrigramSimilarity

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Dyscyplina_Naukowa,
    Jednostka,
    Jezyk,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Rekord,
    Uczelnia,
    Wydawca,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
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
                    # warnings.warn(f"Brak jezyka po stronie BPP: {elem}")
                    continue
            else:
                # warnings.warn(f"Brak jezyka po stronie BPP: {elem}")
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


@transaction.atomic
def zapisz_mongodb(elem, klass, client=None, **extra):
    defaults = dict(
        status=elem["status"],
        verificationLevel=elem["verificationLevel"],
        verified=elem["verified"],
        versions=elem["versions"],
        **extra,
    )

    existing = klass.objects.select_for_update().filter(pk=elem["mongoId"])

    created = False
    try:
        v = existing.get()
    except klass.DoesNotExist:
        v = klass.objects.create(pk=elem["mongoId"], **defaults)
        created = True

    if not created:
        needs_saving = False

        for key in extra:
            if getattr(v, key) != extra.get(key):
                setattr(v, key, extra.get(key))
                needs_saving = True

        if elem["versions"] != v.versions:
            v.versions = elem["versions"]
            needs_saving = True

        if needs_saving:
            v.save()

    return v


def ensure_publication_exists(client, publicationId):
    try:
        publicationId = Publication.objects.get(pk=publicationId)
    except Publication.DoesNotExist:
        zapisz_mongodb(
            client.get_publication_by_id(publicationId), Publication, client=client
        )


def ensure_person_exists(client: PBNClient, personId):
    try:
        personId = Scientist.objects.get(pk=personId)
    except Scientist.DoesNotExist:
        zapisz_mongodb(client.get_person_by_id(personId), Scientist, client=client)


def ensure_institution_exists(client: PBNClient, institutionId):
    try:
        institutionId = Institution.objects.get(pk=institutionId)
    except Institution.DoesNotExist:
        zapisz_mongodb(
            client.get_publication_by_id(institutionId), Institution, client=client
        )


def zapisz_publikacje_instytucji(elem, klass, client=None, **extra):
    try:
        ensure_publication_exists(client, elem["publicationId"])
    except HttpException as e:
        if e.status_code == 500:
            print(
                f"Podczas zapisywania publikacji instytucji, dla {elem['publicationId']} serwer "
                f"PBN zwrócił bład 500. Publikacja instytucji może zostac nie zapisana poprawnie. Dump danych "
                f"publikacji: {elem}"
            )
            return

    rec, _ign = PublikacjaInstytucji.objects.get_or_create(
        institutionId_id=elem["institutionId"],
        publicationId_id=elem["publicationId"],
        insPersonId_id=elem["insPersonId"],
    )

    changed = False
    for key in (
        "publicationVersion",
        "publicationYear",
        "publicationType",
        "userType",
        "snapshot",
    ):
        current = getattr(rec, key)
        server = elem.get(key)
        if current != server:
            setattr(rec, key, server)
            changed = True
    if changed:
        rec.save()


def zapisz_oswiadczenie_instytucji(elem, klass, client=None, **extra):
    # {'id': '121339', 'institutionId': '5e70918b878c28a04737de51',
    # 'personId': '5e709330878c28a0473a4a0e', 'publicationId': '5ebff589ad49b31ccec25471',
    # 'addedTimestamp': '2020.05.16', 'area': '304', 'inOrcid': False, 'type': 'AUTHOR'}
    for var in "addedTimestamp", "statedTimestamp":
        if elem.get(var):
            elem[var] = elem[var].replace(".", "-")

    try:
        ensure_publication_exists(client, elem["publicationId"])
    except HttpException as e:
        if e.status_code == 500:
            print(
                f"Podczas próby pobrania danych o nie-istniejącej obecnie po naszej stronie publikacji o id"
                f" {elem['publicationId']} z PBNu, wystąpił błąd wewnętrzny serwera po ich stronie. Dane "
                f"dotyczące oświadczeń z tej publikacji nie zostały zapisane. "
            )
            return

    try:
        ensure_institution_exists(client, elem["institutionId"])
    except HttpException as e:
        if e.status_code == 500:
            print(
                f"Podczas próby pobrania danych o nie-istniejącej obecnie po naszej stronie publikacji o id"
                f" {elem['publicationId']} z PBNu, wystąpił błąd wewnętrzny serwera po ich stronie. Dane "
                f"dotyczące oświadczeń z tej publikacji nie zostały zapisane. "
            )
            return

    try:
        ensure_person_exists(client, elem["personId"])
    except HttpException as e:
        if e.status_code == 500:
            print(
                f"Podczas próby pobrania danych o nie-istniejącej obecnie po naszej stronie publikacji o id"
                f" {elem['publicationId']} z PBNu, wystąpił błąd wewnętrzny serwera po ich stronie. Dane "
                f"dotyczące oświadczeń z tej publikacji nie zostały zapisane. "
            )
            return

    for key in "institution", "person", "publication":
        elem[f"{key}Id_id"] = elem[f"{key}Id"]
        del elem[f"{key}Id"]

    OswiadczenieInstytucji.objects.update_or_create(id=elem["id"], defaults=elem)


@transaction.atomic
def pobierz_mongodb(
    elems,
    klass,
    pbar_label="pobierz_mongodb",
    fun=zapisz_mongodb,
    client=None,
    disable_progress_bar=False,
):
    if hasattr(elems, "total_elements"):
        count = elems.total_elements
    elif hasattr(elems, "__len__"):
        count = len(elems)

    for elem in pbar(
        elems, count, pbar_label, disable_progress_bar=disable_progress_bar
    ):
        fun(elem, klass, client=client)


def pobierz_instytucje(client: PBNClient):
    for status in [ACTIVE, DELETED]:
        pobierz_mongodb(
            client.get_institutions(status=status, page_size=1000), Institution
        )


def integruj_uczelnie():
    uczelnia = Uczelnia.objects.get_default()

    if uczelnia.pbn_uid_id is not None:
        return

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
            print(f"x*X Liczne dopasowania dla jednostki: {j}")
            continue

        except Institution.DoesNotExist:
            print(f"XXX Brak dopasowania dla jednostki: {j}")
            continue

        if j.pbn_uid_id != u.mongoId:
            j.pbn_uid_id = u.mongoId
            j.save()


def pobierz_konferencje(client: PBNClient):
    pobierz_mongodb(
        client.get_conferences_mnisw(page_size=1000),
        Conference,
        pbar_label="pobierz_konferencje",
    )


class ZrodlaGetter(ThreadedMongoDBSaver):
    pbn_api_klass = Journal


def pobierz_zrodla(client: PBNClient):
    for status in [DELETED, ACTIVE]:
        data = client.get_journals(status=status, page_size=500)
        threaded_page_getter(
            client, data, klass=ZrodlaGetter, label=f"poboerz_zrodla_{status}"
        )


class PublisherGetter(ThreadedMongoDBSaver):
    pbn_api_klass = Publisher


def pobierz_wydawcow_mnisw(client: PBNClient):
    data = client.get_publishers_mnisw(page_size=1000)
    threaded_page_getter(
        client, data, klass=PublisherGetter, label="poboerz_wydawcow_mnisw"
    )


def pobierz_wydawcow_wszystkich(client: PBNClient):
    data = client.get_publishers(page_size=1000)
    threaded_page_getter(
        client, data, klass=PublisherGetter, label="poboerz_wydawcow_wszystkich"
    )

    # pobierz_mongodb(
    #     client.get_publishers(page_size=1000),
    #     Publisher,
    #     pbar_label="pobierz_wydawcow_wszystkich",
    # )


def pbn_file_path(db, current_page, status):
    return f"pbn_json_data/{db}_offline_{status}_{current_page}.json"


def wait_for_results(pool, results, label="Progress..."):
    for elem in pbar(results, count=len(results), label=label):
        elem.get()
    pool.close()
    pool.join()


def _single_unit_offline(data, db, current_page, status):
    f = open(pbn_file_path(db, current_page, status), "w")
    f.write(json.dumps(data.fetch_page(current_page)))
    f.close()


def _pobierz_offline(fun, db):
    _bede_uzywal_bazy_danych_z_multiprocessing_z_django()

    p = initialize_pool()

    for status in [ACTIVE, DELETED]:
        data = fun(status=status, page_size=10000)

        params = [
            (data, db, current_page, status)
            for current_page in range(0, data.total_pages)
        ]

        for _ in pbar(
            p.istarmap(_single_unit_offline, params),
            label=f"pobierz_offline_{db}_{status}",
            count=len(params),
        ):
            pass

    # wait_for_results(p, results, label=f"pobierz_offline {db}")
    p.close()
    p.join()


def pobierz_ludzi_offline(client: PBNClient):
    return _pobierz_offline(client.get_people, "people")


def pobierz_prace_offline(client: PBNClient):
    return _pobierz_offline(client.get_publications, "publications")


def _single_unit_wgraj(current_page, status, db, model):
    fn = pbn_file_path(db, current_page, status)
    if os.path.exists(fn):
        data = open(fn).read()
        if data:
            dane = json.loads(data)
            if dane:
                with transaction.atomic():
                    pobierz_mongodb(dane, model, disable_progress_bar=True)


def _bede_uzywal_bazy_danych_z_multiprocessing_z_django():
    from django.db import close_old_connections, connections

    close_old_connections()
    connections.close_all()


def _wgraj_z_offline_do_bazy(db, model):
    _bede_uzywal_bazy_danych_z_multiprocessing_z_django()

    p = initialize_pool()

    for status in [ACTIVE, DELETED]:
        params = [(current_page, status, db, model) for current_page in range(1500)]

        for _ in pbar(
            p.istarmap(_single_unit_wgraj, params),
            label=f"wgraj_offline_{db}_{status}",
            count=len(params),
        ):
            pass

    p.close()
    p.join()


def wgraj_ludzi_z_offline_do_bazy():
    return _wgraj_z_offline_do_bazy("people", Scientist)


def wgraj_prace_z_offline_do_bazy():
    return _wgraj_z_offline_do_bazy("publications", Publication)


def pobierz_prace(client: PBNClient):
    pobierz_mongodb(
        client.get_publications(status=ACTIVE, page_size=5000),
        Publication,
        pbar_label="pobierz_aktywne_prace",
    )


def pobierz_publikacje_z_instytucji(client: PBNClient):
    pobierz_mongodb(
        client.get_institution_publications(page_size=2000),
        None,
        fun=zapisz_publikacje_instytucji,
        client=client,
        pbar_label="pobierz_publikacje_instytucji",
    )


def pobierz_oswiadczenia_z_instytucji(client: PBNClient):
    pobierz_mongodb(
        client.get_institution_statements(page_size=1000),
        None,
        fun=zapisz_oswiadczenie_instytucji,
        client=client,
        pbar_label="oswiadczenia instytucji",
    )


def _pobierz_prace_po_elemencie(
    client: PBNClient, element, nd, matchuj=True, value_from_rec=None, **kw
):
    ret = []
    base_kw = {element: nd}
    base_kw.update(kw)

    for elem in client.search_publications(**base_kw):
        publication = zapisz_mongodb(
            client.get_publication_by_id(elem["mongoId"]), Publication
        )

        p = publication.matchuj_do_rekordu_bpp()
        if p is None:
            print(
                f"XXX mimo pobrania pracy po {element.upper()} {nd}, zwrotnie NIE pasuje ona do pracy w BPP "
                f"-- rok {publication.year} lub tytul {publication.title} nie daja sie dopasowac. Blad w "
                f"zapisie {element.upper()}? Niepoprawne {element.upper()}? Oryginalny obiekt: {value_from_rec}"
            )
            continue

        p = p.original

        if p in ret:
            continue

        if p.pbn_uid_id == publication.mongoId:
            # Juz zmatchowany
            continue

        # Co w sytuacji p.pbn_uid_id != publication.mongoId? Rekord zmatchowany z innym, teraz pasuje do innego?
        # Nic. Na ten moment nadpisujemy to po cichu (2.09.2021), jest to moja swiadoma decyzja (mpasternak)
        # poniewaz z tysiaca komunikatow o tej sytuacji nic nie wynikalo a zazwyczaj wychodzilo na to, ze rekordy
        # byly niepoprawnie zmatchowane.

        p.pbn_uid_id = publication.mongoId
        p.save(update_fields=["pbn_uid_id"])
        ret.append(p)

    return ret


def pobierz_prace_po_doi(client: PBNClient):
    dois = set()
    for praca in pbar(
        Rekord.objects.all()
        .exclude(doi=None)
        .exclude(doi="")
        .filter(pbn_uid_id=None)
        .filter(rok__gte=PBN_MIN_ROK),
        label="pobierz_prace_po_doi",
    ):
        nd = normalize_doi(praca.doi)
        dois.add(nd)

    _bede_uzywal_bazy_danych_z_multiprocessing_z_django()

    p = initialize_pool()

    results = []

    for doi in dois:
        results.append(
            p.apply_async(
                _pobierz_prace_po_elemencie,
                args=(
                    client,
                    "doi",
                    doi,
                ),
            )
        )

    wait_for_results(p, results)


def pobierz_prace_po_isbn(client: PBNClient):
    isbns = set()
    for praca in pbar(
        Rekord.objects.all()
        .exclude(isbn=None)
        .exclude(isbn="")
        .filter(pbn_uid_id=None)
        .filter(rok__gte=PBN_MIN_ROK)
        .filter(wydawnictwo_nadrzedne_id=None),
        label="pobierz_prace_po_isbn",
    ):
        nd = normalize_isbn(praca.isbn)
        isbns.add(nd)

    _bede_uzywal_bazy_danych_z_multiprocessing_z_django()

    p = initialize_pool()

    results = []

    for isbn in isbns:
        results.append(
            p.apply_async(
                _pobierz_prace_po_elemencie,
                args=(
                    client,
                    "isbn",
                    isbn,
                ),
            )
        )

    wait_for_results(p, results)


def _single_unit_ludzie_z_uczelni(client, personId):
    scientist = client.get_person_by_id(personId)
    zapisz_mongodb(scientist, Scientist, from_institution_api=True)


def pobierz_ludzi_z_uczelni(client: PBNClient, instutition_id):
    """
    Ta procedura pobierze dane wszystkich osob z uczelni, mozna uruchamiac
    zamiast pobierz_ludzi
    """
    assert instutition_id is not None

    Scientist.objects.filter(from_institution_api=True).update(
        from_institution_api=False
    )

    pool = initialize_pool()
    results = []
    elementy = client.get_people_by_institution_id(instutition_id)

    _bede_uzywal_bazy_danych_z_multiprocessing_z_django()

    for person in pbar(elementy, count=len(elementy), label="pobierz ludzi z uczelni"):
        result = pool.apply_async(
            _single_unit_ludzie_z_uczelni, args=(client, person["personId"])
        )
        results.append(result)
    wait_for_results(pool, results)


def integruj_autorow_z_uczelni(client: PBNClient, instutition_id):
    """
    Ta procedure uruchamiamy dopiero po zaciągnięciu bazy osób.
    """
    for person in Scientist.objects.filter(from_institution_api=True):
        pbn_id = None
        if person.value("object", "legacyIdentifiers", return_none=True):
            pbn_id = person.value("object", "legacyIdentifiers")[0]

        autor = matchuj_autora(
            imiona=person.value("object", "name", return_none=True),
            nazwisko=person.value("object", "lastName", return_none=True),
            orcid=person.value("object", "orcid", return_none=True),
            pbn_id=pbn_id,
            pbn_uid_id=person.pk,
            tytul_str=person.value("object", "qualifications", return_none=True),
        )
        if autor is None:
            print(f"Brak dopasowania w jednostce dla autora {person}")
            continue

        if autor.pbn_uid_id is None:
            autor.pbn_uid_id = person.mongoId
            autor.save()

        if autor.pbn_uid_id != person.pk:
            print(
                f"UWAGA Zmieniam powiązanie PBN UID dla autora {autor} z {autor.pbn_uid_id} na {person.pk}"
            )
            autor.pbn_uid = person
            autor.save()


def weryfikuj_orcidy(client: PBNClient, instutition_id):
    # Sprawdź dla każdego autora który ma ORCID ale nie ma PBN UID
    # czy ten ORCID występuje w bazie PBNu, odpowiednio ustawiając
    # flagę rekordu Autor:

    qry = Autor.objects.exclude(orcid=None).filter(pbn_uid_id=None)

    for autor in pbar(qry):
        res = client.get_person_by_orcid(autor.orcid)
        if not res:
            autor.orcid_w_pbn = False
            autor.save()
            continue

        sciencist = zapisz_mongodb(res[0], Scientist)
        autor.pbn_uid = sciencist
        autor.save()
        print(
            f"Dla autora {autor} utworzono powiazanie z rekordem PBN {sciencist} po ORCID"
        )


def matchuj_autora_po_stronie_pbn(imiona, nazwisko, orcid):
    if orcid is not None:
        # Szukamy w rekordach zaimportowanych przez API instytucji

        qry = Q(versions__contains=[{"current": True, "object": {"orcid": orcid}}]) & Q(
            from_institution_api=True
        )
        try:
            res = Scientist.objects.get(qry)
            return res
        except Scientist.DoesNotExist:
            pass
        except Scientist.MultipleObjectsReturned:
            print(
                f"XXX ORCID istnieje wiele razy w bazie PBN w rekordach importowanych przez API instytucji {orcid}"
            )
            for elem in Scientist.objects.filter(qry):
                print(
                    "\t * ",
                    elem.pk,
                    elem.name,
                    elem.lastName,
                )

        # Szukamy w rekordach wszystkich przez API instytucji

        qry = Q(versions__contains=[{"current": True, "object": {"orcid": orcid}}])
        try:
            res = Scientist.objects.exclude(from_institution_api=True).get(qry)
            return res
        except Scientist.DoesNotExist:
            print(
                f"*** ORCID nie istnieje w rekordach ani z API instytucji, ani we wszystkich {orcid}"
            )
        except Scientist.MultipleObjectsReturned:
            print(
                f"XXX ORCID istnieje wiele razy w bazie PBN w rekordach importowanych nie-przez API instytucji {orcid}"
            )
            for elem in Scientist.objects.filter(qry):
                print(
                    "\t * ",
                    elem.pk,
                    elem.name,
                    elem.lastName,
                )

    qry = Q(
        versions__contains=[
            {
                "current": True,
                "object": {"lastName": nazwisko.strip(), "name": imiona.strip()},
            }
        ]
    )
    try:
        res = Scientist.objects.filter(from_institution_api=True).get(qry)
        return res
    except Scientist.DoesNotExist:
        print(
            f"*** BRAK AUTORA w PBN z API instytucji, istnieje w BPP (im/naz): {nazwisko} {imiona}"
        )
    except Scientist.MultipleObjectsReturned:
        print(
            f"XXX AUTOR istnieje wiele razy w bazie PBN z API INSTYTUCJI (im/naz) {nazwisko} {imiona}"
        )

    # Autorzy nie-z-API instytucji

    try:
        res = Scientist.objects.exclude(from_institution_api=True).get(qry)
        return res
    except Scientist.DoesNotExist:
        print(
            f"*** BRAK AUTORA w PBN z danych spoza API instytucji, istnieje w BPP: {nazwisko} {imiona}"
        )
    except Scientist.MultipleObjectsReturned:
        print(
            f"XXX AUTOR istnieje wiele razy w bazie PBN z danych "
            f"spoza API INSTYTUCJI {nazwisko} {imiona}, "
            f"próba dobrania najlepszego"
        )

        can_be_set = False
        rated_elems = []
        for elem in Scientist.objects.exclude(from_institution_api=True).filter(qry):
            cur_elem_points = 0
            for attr in [
                "currentEmployments",
                "externalIdentifiers",
                "legacyIdentifiers",
                "qualifications",
            ]:
                if elem.value_or_none("object", attr):
                    cur_elem_points += 1

            currentEmployments = elem.value_or_none("object", "currentEmployments")
            if currentEmployments is not None:
                for pos in currentEmployments:
                    if pos.get("institutionId") == Uczelnia.objects.default.pbn_uid_id:
                        can_be_set = True

            rated_elems.append((cur_elem_points, elem.pk))

        rated_elems.sort(reverse=True)
        if can_be_set:
            print(f"--> Sposrod elementow {rated_elems} wybieram pierwszy")
            return Scientist.objects.get(pk=rated_elems[0][1])
        else:
            print(
                f"XXX Sposrod elementow {rated_elems} NIE WYBIERAM NIC, bo autor nie pracuje w jednostce"
            )


def integruj_wszystkich_niezintegrowanych_autorow():
    autorzy_z_dyscyplina_ids = Autor_Dyscyplina.objects.values("autor_id").distinct()

    for autor in Autor.objects.filter(pk__in=autorzy_z_dyscyplina_ids, pbn_uid_id=None):
        sciencist = matchuj_autora_po_stronie_pbn(
            autor.imiona, autor.nazwisko, autor.orcid
        )
        if sciencist:
            print(f"==> integracja wszystkich: ustawiam {autor} na {sciencist.pk}")
            autor.pbn_uid = sciencist
            autor.save()


def integruj_zrodla(disable_progress_bar):
    def fun(qry):
        found = False
        try:
            u = Journal.objects.get(qry)
            found = True
        except Journal.DoesNotExist:
            return False
        except Journal.MultipleObjectsReturned:
            # warnings.warn(
            #     f"Znaleziono liczne dopasowania w PBN dla {zrodlo}, szukam czy jakies ma mniswId"
            # )
            for u in Journal.objects.filter(qry):
                if u.mniswId is not None:
                    found = True
                    break

            if not found:
                print(
                    f"Znaleziono liczne dopasowania w PBN dla {zrodlo}, żadnie nie ma mniswId, wybieram to z "
                    f"najdłuższym opisem"
                )
                u = (
                    Journal.objects.filter(qry)
                    .annotate(
                        json_len=Func(
                            F("versions"),
                            function="pg_column_size",
                            output_field=IntegerField(),
                        )
                    )
                    .order_by("-json_len")
                    .first()
                )

        zrodlo.pbn_uid = u
        zrodlo.save()
        return True

    for zrodlo in pbar(
        Zrodlo.objects.filter(pbn_uid_id=None),
        label="Integracja zrodel",
        disable_progress_bar=disable_progress_bar,
    ):
        queries = []

        if zrodlo.issn:
            queries.append(Q(issn=zrodlo.issn) | Q(eissn=zrodlo.issn))

        if zrodlo.e_issn:
            queries.append(Q(eissn=zrodlo.e_issn) | Q(issn=zrodlo.e_issn))

        queries.append(Q(title__iexact=zrodlo.nazwa))

        if fun(reduce(operator.or_, queries)):
            print(f"\nZNALEZIONO dopasowania w PBN dla {zrodlo} -> {zrodlo.pbn_uid}")
            continue

        print(f"\nNie znaleziono dopasowania w PBN dla {zrodlo}")


@transaction.atomic
def integruj_wydawcow():
    # Najpierw dopasuj wydawcow z MNISWId
    for elem in pbar(
        Publisher.objects.filter(versions__contains=[{"current": True}]).filter(
            versions__0__object__has_key="mniswId"
        ),
        label="match wyd mnisw",
    ):
        w = matchuj_wydawce(elem.value("object", "publisherName"))
        if w is not None:
            if w.pbn_uid_id is None and w.pbn_uid_id != elem.pk:
                print(f"Przypisuje Wydawca PBN {elem} -> wydawca BPP {w}")
                w.pbn_uid_id = elem.pk
                w.save()

    # Dopasuj wszystkich
    for elem in pbar(
        Publisher.objects.filter(versions__contains=[{"current": True}]),
        label="match wyd wszyscy",
    ):
        w = matchuj_wydawce(elem.value("object", "publisherName"))
        if w is not None:
            if w.pbn_uid_id is None and w.pbn_uid_id != elem.pk:
                print(f"Przypisuje Wydawca PBN {elem} -> wydawca BPP {w}")
                w.pbn_uid_id = elem.pk
                w.save()


def zweryfikuj_lub_stworz_match(elem, bpp_rekord):
    if bpp_rekord is not None:
        if bpp_rekord.pbn_uid_id is not None and bpp_rekord.pbn_uid_id != elem.pk:
            print(
                f"\r\n*** Rekord BPP {bpp_rekord} ma już PBN UID {bpp_rekord.pbn_uid_id}, "
                f"pasuje też do {elem} PBN UID {elem.pk}"
            )
            return

        if bpp_rekord.pbn_uid_id is None:
            p = bpp_rekord.original
            p.pbn_uid_id = elem.pk
            p.save(update_fields=["pbn_uid_id"])


def _integruj_single_part(ids):
    for _id in ids:
        try:
            elem = Publication.objects.get(pk=_id)
        except Publication.DoesNotExist as e:
            print(f"Brak publikacji o ID {_id}")
            raise e
        p = elem.matchuj_do_rekordu_bpp()
        zweryfikuj_lub_stworz_match(elem, p)


def split_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


CPU_COUNT = "auto"

DEFAULT_CONTEXT = "spawn"


def _init():
    import django

    django.setup()


def initialize_pool(multipler=1):
    global CPU_COUNT

    if CPU_COUNT == "auto":
        cpu_count = os.cpu_count() * 3 // 4
        if cpu_count < 1:
            cpu_count = 1

        cpu_count = cpu_count * multipler
        if cpu_count < 1:
            cpu_count = 1

    elif CPU_COUNT == "single":
        cpu_count = 1
    else:
        raise NotImplementedError(f"CPU_COUNT = {CPU_COUNT}")

    return multiprocessing.get_context(DEFAULT_CONTEXT).Pool(
        cpu_count, initializer=_init
    )


def _integruj_publikacje(
    pubs, disable_multiprocessing=False, skip_pages=0, label="_integruj_publikacje"
):
    _bede_uzywal_bazy_danych_z_multiprocessing_z_django()
    pool = initialize_pool()

    BATCH_SIZE = 128
    results = []
    for no, elem in enumerate(split_list(pubs, BATCH_SIZE)):
        if no < skip_pages:
            continue

        if disable_multiprocessing:
            _integruj_single_part(elem)
            print(f"{label} {no} of {len(pubs)//BATCH_SIZE}...", end="\r")
            sys.stdout.flush()
        else:
            result = pool.apply_async(_integruj_single_part, args=(elem,))
            results.append(result)

    wait_for_results(pool, results, label=label)


def integruj_wszystkie_publikacje(
    disable_multiprocessing=False, ignore_already_matched=False, skip_pages=0
):
    pubs = Publication.objects.all()

    if ignore_already_matched:
        pubs = pubs.exclude(
            pk__in=Rekord.objects.exclude(pbn_uid_id=None)
            .values_list("pbn_uid_id", flat=True)
            .distinct()
        )

    pubs = pubs.order_by("-pk")
    pubs = list(pubs.values_list("pk", flat=True).distinct())

    return _integruj_publikacje(
        pubs, disable_multiprocessing=disable_multiprocessing, skip_pages=skip_pages
    )


def integruj_publikacje_instytucji(
    disable_multiprocessing=False, ignore_already_matched=False, skip_pages=0
):
    """
    :param ignore_already_matched: jeżeli True, to publikacje, które już mają swój match
    po stronie BPP nie będa analizowane.

    """

    pubs = (
        OswiadczenieInstytucji.objects.all()
        .values_list("publicationId_id", flat=True)
        .order_by("-pk")
        .distinct()
    )
    return _integruj_publikacje(
        pubs, disable_multiprocessing=disable_multiprocessing, skip_pages=skip_pages
    )


MODELE_Z_PBN_UID = (
    Wydawnictwo_Zwarte,
    Wydawnictwo_Ciagle,
    Praca_Doktorska,
    Praca_Habilitacyjna,
)


#
# Poniżej wersja iterująca po rekordach w BPP, szukająca matchy w pbn_api.Publication
#
# def integruj_publikacje(
#     disable_multiprocessing=False, ignore_already_matched=False, skip_pages=0
# ):
#     """
#     :param ignore_already_matched: jeżeli True, to publikacje, które już mają swój match
#     po stronie BPP nie będa analizowane.
#
#     """
#     for klass in MODELE_Z_PBN_UID:
#         for elem in pbar(klass.objects.all()):
#             zrodlo = None
#             if hasattr(elem, "zrodlo"):
#                 zrodlo = elem.zrodlo
#
#             isbn = None
#             if hasattr(elem, "isbn"):
#                 isbn = elem.isbn
#
#             res = matchuj_pbn_api_publication(
#                 elem.tytul_oryginalny,
#                 elem.rok,
#                 elem.doi,
#                 elem.public_www or elem.www,
#                 isbn,
#                 zrodlo,
#             )
#
#             if res is not None:
#                 if elem.pbn_uid_id is not None:
#                     if elem.pbn_uid_id != res.pk:
#                         print(
#                             f"XXX Publikacja {elem} ma juz PBN UID {elem.pbn_uid_id} {elem.pbn_uid} ale "
#                             f"matchowanie chce ją przypisać do {res.pk} {res}"
#                         )
#                 else:
#                     # elem.pbn_uid_id is None
#                     elem.pbn_uid_id = res.pk
#                     elem.save(update_fields=["pbn_uid_id"])
#             else:
#                 # print(f"XXX Brak matchu w PBN: {elem}")
#                 pass
#

PBN_KOMUNIKAT_ISBN_ISTNIEJE = "Publikacja o identycznym ISBN lub ISMN już istnieje"
PBN_KOMUNIKAT_DOI_ISTNIEJE = "Publikacja o identycznym DOI i typie już istnieje"


def _synchronizuj_pojedyncza_publikacje(
    client,
    rec,
    force_upload=False,
    export_pk_zero=None,
    delete_statements_before_upload=False,
):
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
                    f"przy synchronizacji komunkat: {e.content} !! Sprawa DO SPRAWDZENIA RECZNIE"
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
                    f"{rec.pk},{rec.tytul_oryginalny},{rec.rok},PBN Server Error: {e.content}"
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
                f"{rec.pk},{rec.tytul_oryginalny},{rec.rok},PBN Server Error: {e.content}"
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
            f"{rec.pk},{rec.tytul_oryginalny},{rec.rok},nie wyeksportuje, bo: {e}"
        )


def wydawnictwa_zwarte_do_synchronizacji():
    return (
        Wydawnictwo_Zwarte.objects.filter(rok__gte=PBN_MIN_ROK)
        .exclude(charakter_formalny__rodzaj_pbn=None)
        .exclude(isbn=None, e_isbn=None)
        .exclude(jezyk__pbn_uid_id=None)
        .exclude(
            doi=None,
            public_www=None,
            www=None,
            wydawnictwo_nadrzedne__www=None,
            wydawnictwo_nadrzedne__public_www=None,
        )
        # rekordy bez WWW wysylamy gdy jest okreslone nadrzedne + nadrzende ma WWW
    )


def wydawnictwa_ciagle_do_synchronizacji():
    return (
        Wydawnictwo_Ciagle.objects.filter(rok__gte=PBN_MIN_ROK)
        .exclude(jezyk__pbn_uid_id=None)
        .exclude(charakter_formalny__rodzaj_pbn=None)
        .exclude(doi=None, public_www=None, www=None)
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
    """
    Komenda eksportująca wszystkie publikacje w systmeie, zaczynając od książek,
    przez rozdziały, po wydawnictwa ciągłe.


    :param only_bad: eksportuj jedynie rekordy, które mają wpis w tabeli SentData, ze ich eksport
    nie powiódł się wcześniej.

    :param only_new: eksportuj jedynie rekordy, które nie mają wpisu w tabeli SentData,

    :param force_upload: wymuszaj ponowne wysłanie, niezależnie od sytuacji w tabeli SentData
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


def clear_match_publications():
    for model in MODELE_Z_PBN_UID:
        print(f"Setting pbn_uid_ids of {model} to null...")
        model.objects.exclude(pbn_uid_id=None).update(pbn_uid_id=None)


def clear_publications():
    clear_match_publications()
    for model in [OswiadczenieInstytucji, PublikacjaInstytucji, Publication, SentData]:
        model.objects.all()._raw_delete(MODELE_Z_PBN_UID[0].objects.db)


def clear_all():
    for model in (
        Autor,
        Jednostka,
        Wydawca,
        Jezyk,
        Uczelnia,
        Zrodlo,
        Dyscyplina_Naukowa,
    ):
        print(f"Setting pbn_uid_ids of {model} to null...")
        model.objects.exclude(pbn_uid_id=None).update(pbn_uid_id=None)

    clear_publications()

    for model in (
        Language,
        Country,
        Institution,
        Conference,
        SentData,
        Journal,
        Publisher,
        Scientist,
        Discipline,
        DisciplineGroup,
    ):
        print(f"Deleting all {model}")
        model.objects.all()._raw_delete(model.objects.db)


def integruj_oswiadczenia_z_instytucji():
    noted_pub = set()
    noted_aut = set()
    for elem in pbar(
        OswiadczenieInstytucji.objects.filter(inOrcid=True),
        label="integruj_oswiadczenia_z_instytucji",
    ):
        pub = elem.get_bpp_publication()
        if pub is None:
            pub = elem.publicationId.matchuj_do_rekordu_bpp()

            if pub is None:
                if elem.publicationId_id not in noted_pub:
                    print(
                        f"\r\nPPP Brak odpowiednika publikacji w BPP dla pracy {elem.publicationId}, "
                        f"parametr inOrcid dla tej pracy nie zostanie zaimportowany!"
                    )
                    noted_pub.add(elem.publicationId_id)
                continue
            else:
                zweryfikuj_lub_stworz_match(elem.publicationId, pub)

        aut = elem.get_bpp_autor()
        if aut is None:
            if elem.personId_id not in noted_aut:
                print(
                    f"\r\nAAA Brak odpowiednika autora w BPP dla autora {elem.personId}, "
                    f"parametr inOrcid dla tego autora nie zostanie zaimportowany!"
                )
                noted_aut.add(elem.publicationId_id)
            continue

        try:
            rec = pub.autorzy_set.get(autor=aut)
        except pub.autorzy_set.model.DoesNotExist:
            print(
                f"XXX Po stronie PBN: {elem.publicationId}, \n"
                f"XXX po stronie BPP: {pub}, {aut} -- nie ma ta praca takiego autora!"
            )

        if not rec.profil_orcid:
            rec.profil_orcid = True
            rec.save(update_fields=["profil_orcid"])


def wyswietl_niezmatchowane_ze_zblizonymi_tytulami():
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


def _pobierz_pojedyncza_prace(client, publicationId):
    try:
        data = client.get_publication_by_id(publicationId)
    except HttpException as e:
        if (
            e.status_code == 422
            and f"Publication with ID {publicationId} was not exists!" in e.content
            # "was not exists" to oryginalna pisownia błędu z PBNu.
        ):
            raise BrakIDPracyPoStroniePBN(e)

        if e.status_code == 500 and "Internal server error" in e.content:
            print(
                f"\r\nSerwer PBN zwrocil blad 500 dla PBN UID {publicationId} --> {e.content}"
            )
            return
        raise e
    zapisz_mongodb(data, Publication, client)


def pobierz_rekordy_publikacji_instytucji(client: PBNClient):
    seen = set()
    for elem in pbar(
        client.get_institution_publications(page_size=1000),
        label="scan pobierz_rekordy_publikacji_instytucji",
    ):
        publicationId = elem["publicationId"]
        seen.add(publicationId)

    _bede_uzywal_bazy_danych_z_multiprocessing_z_django()
    pool = initialize_pool(multipler=2)

    args = [(client, _id) for _id in seen]
    for _ in pbar(
        pool.istarmap(_pobierz_pojedyncza_prace, args),
        label="pobierz_rekordy_publikacj_instytucji",
        count=len(args),
    ):
        pass

    pool.close()
    pool.join()


def usun_wszystkie_oswiadczenia(client):
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


def wyslij_informacje_o_platnosciach(client: PBNClient):
    for model in Wydawnictwo_Ciagle, Wydawnictwo_Zwarte:
        for elem in pbar(model.objects.rekordy_z_oplata()):
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
