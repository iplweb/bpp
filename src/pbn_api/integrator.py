import json
import multiprocessing
import os
import warnings

from django.db import transaction
from django.db.models import F, Func, Q

from import_common.core import matchuj_autora, matchuj_publikacje, matchuj_wydawce
from pbn_api.client import PBNClient
from pbn_api.exceptions import HttpException, SameDataUploadedRecently
from pbn_api.models import (
    Conference,
    Country,
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
from .adapters.wydawnictwo import normalize_isbn
from .exceptions import WillNotExportError

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Jednostka,
    Jezyk,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Rekord,
    Uczelnia,
    Wydawca,
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


def zapisz_mongodb(elem, klass, client=None, **extra):
    defaults = dict(
        status=elem["status"],
        verificationLevel=elem["verificationLevel"],
        verified=elem["verified"],
        versions=elem["versions"],
        **extra,
    )

    v, _ign = klass.objects.update_or_create(pk=elem["mongoId"], defaults=defaults)

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


def zapisz_publikacje_instytucji(elem, klass, client=None, **extra):
    ensure_publication_exists(client, elem["publicationId"])

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
    if elem["addedTimestamp"]:
        elem["addedTimestamp"] = elem["addedTimestamp"].replace(".", "-")

    ensure_publication_exists(client, elem["publicationId"])

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
    for status in ["ACTIVE", "DELETED"]:
        pobierz_mongodb(
            client.get_institutions(status=status, page_size=1000), Institution
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


def pobierz_zrodla(client: PBNClient):
    for status in ["DELETED", "ACTIVE"]:
        pobierz_mongodb(
            client.get_journals(status=status, page_size=10000),
            Journal,
            pbar_label=f"pobierz_zrodla_{status}",
        )


def pobierz_wydawcow_mnisw(client: PBNClient):
    pobierz_mongodb(
        client.get_publishers_mnisw(page_size=1000),
        Publisher,
        pbar_label="pobierz_wydawcow_mnisw",
    )


def pobierz_wydawcow_wszystkich(client: PBNClient):
    pobierz_mongodb(
        client.get_publishers(page_size=1000),
        Publisher,
        pbar_label="pobierz_wydawcow_wszystkich",
    )


def pbn_file_path(db, current_page, status):
    return f"pbn_json_data/{db}_offline_{status}_{current_page}.json"


def wait_for_results(pool, results, label="Progress..."):
    for elem in pbar(results, count=len(results), label=label):
        elem.wait()
    pool.close()
    pool.join()


def _single_unit_offline(db, data, current_page, status):
    f = open(pbn_file_path(db, current_page, status), "w")
    f.write(json.dumps(data.fetch_page(current_page)))
    f.close()


def _pobierz_offline(fun, db):
    _bede_uzywal_bazy_danych_z_multiprocessing_z_django()

    results = []
    p = multiprocessing.Pool()

    for status in ["ACTIVE", "DELETED"]:
        res = fun(status=status, page_size=5000)

        for current_page in range(res.total_pages):
            result = p.apply_async(
                _single_unit_offline, (db, res, current_page, status)
            )
            results.append(result)

    wait_for_results(p, results, label=f"pobierz_offline {db}")


def pobierz_ludzi_offline(client: PBNClient):
    return _pobierz_offline(client.get_people, "people")


def pobierz_prace_offline(client: PBNClient):
    return _pobierz_offline(client.get_publications, "publications")


def _single_unit_wgraj(current_page, status, db, model):
    fn = pbn_file_path(db, current_page, status)
    if os.path.exists(fn):
        data = open(fn, "r").read()
        if data:
            dane = json.loads(data)
            if dane:
                with transaction.atomic():
                    pobierz_mongodb(dane, model, disable_progress_bar=True)


def _bede_uzywal_bazy_danych_z_multiprocessing_z_django():
    from django.db import close_old_connections

    close_old_connections()


def _wgraj_z_offline_do_bazy(db, model):
    _bede_uzywal_bazy_danych_z_multiprocessing_z_django()

    p = multiprocessing.Pool()

    def _(exc):
        print("XXX", exc)

    results = []
    for status in ["ACTIVE", "DELETED"]:
        for current_page in range(1500):
            fn = pbn_file_path(db, current_page, status)
            if os.path.exists(fn):
                result = p.apply_async(
                    _single_unit_wgraj,
                    (current_page, status, db, model),
                    error_callback=_,
                )
                results.append(result)

    wait_for_results(p, results, label=f"wgraj_z_offline_do_bazy {db}")


def wgraj_ludzi_z_offline_do_bazy():
    return _wgraj_z_offline_do_bazy("people", Scientist)


def wgraj_prace_z_offline_do_bazy():
    return _wgraj_z_offline_do_bazy("publications", Publication)


def normalize_doi(s):
    return s.strip()


def pobierz_prace(client: PBNClient):
    for status in ["ACTIVE"]:  # "DELETED", "ACTIVE"]:
        pobierz_mongodb(
            client.get_publications(status=status, page_size=5000),
            Publication,
            pbar_label="pobierz_prace",
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


def pobierz_prace_po_doi(client: PBNClient):
    for klass in (Wydawnictwo_Ciagle,):  # , Wydawnictwo_Zwarte:
        for praca in pbar(
            klass.objects.all().exclude(doi=None).filter(pbn_uid_id=None),
            label="pobierz_prace_po_doi",
        ):
            try:
                elem = client.get_publication_by_doi(normalize_doi(praca.doi))
            except HttpException as e:
                if e.status_code == 422:
                    # Publication with DOI 10.1136/annrheumdis-2018-eular.5236 was not exists!
                    print(
                        f"\r\nBrak pracy z DOI {praca.doi} w PBNie -- w BPP to {praca}"
                    )
                    continue
                elif e.status_code == 500:
                    if (
                        b"Publication with DOI" in e.content
                        and b"was not exists" in e.content
                    ):
                        print(
                            f"\r\nBrak pracy z DOI {praca.doi} w PBNie -- w BPP to {praca}"
                        )
                        continue

                raise e

            publication = zapisz_mongodb(elem, Publication)

            if praca.pbn_uid_id is None:
                praca.pbn_uid = publication
                praca.save()


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

    pool = multiprocessing.Pool(os.cpu_count() * 3)
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
                    elem.name(),
                    elem.lastName(),
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
                    elem.name(),
                    elem.lastName(),
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
                if u.mniswId() is not None:
                    found = True
                    break

            if not found:
                print(
                    f"Znaleziono liczne dopasowania w PBN dla {zrodlo}, żadnie nie ma mniswId, wybieram to z "
                    f"najdłuższym opisem"
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
        Zrodlo.objects.filter(pbn_uid_id=None),
        label="Integracja zrodel",
        disable_progress_bar=disable_progress_bar,
    ):
        qry = None

        if zrodlo.issn:
            found = False
            for current in True, False:
                qry = Q(
                    versions__contains=[
                        {"current": current, "object": {"issn": zrodlo.issn}}
                    ]
                )
                if fun(qry):
                    found = True
                    break

                qry = Q(
                    versions__contains=[
                        {"current": current, "object": {"eissn": zrodlo.issn}}
                    ]
                )
                if fun(qry):
                    found = True
                    break

            if found:
                continue

        if zrodlo.e_issn:
            found = False
            for current in True, False:
                qry = Q(
                    versions__contains=[
                        {"current": current, "object": {"eissn": zrodlo.e_issn}}
                    ]
                )
                if fun(qry):
                    found = True
                    break

                qry = Q(
                    versions__contains=[
                        {"current": current, "object": {"issn": zrodlo.e_issn}}
                    ]
                )
                if fun(qry):
                    found = True
                    break

            if found:
                continue

        if qry is None:
            for current in True, False:
                qry = Q(
                    versions__contains=[
                        {"current": current, "object": {"title": zrodlo.nazwa}}
                    ]
                )
                if fun(qry):
                    found = True
                    break

                qry = Q(
                    versions__contains=[
                        {"current": current, "object": {"title": zrodlo.nazwa.upper()}}
                    ]
                )
                if fun(qry):
                    found = True
                    break

            if found:
                continue

            print(f"Nie znaleziono dopasowania w PBN dla {zrodlo}")


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
                w.pbn_uid_id = elem.pk
                w.save()


def _integruj_single_part(ids):
    for _id in ids:
        elem = Publication.objects.get(pk=_id)

        zrodlo = None
        zrodlo_pbn_uid_id = elem.value_or_none("object", "journal", "id")
        if zrodlo_pbn_uid_id is not None:
            try:
                zrodlo = Zrodlo.objects.get(pbn_uid_id=zrodlo_pbn_uid_id)
            except Zrodlo.DoesNotExist:
                pass
            except Zrodlo.MultipleObjectsReturned:
                print(
                    f"XXX wiele zrodel po stronie BPP ma odpowiednik w PBN UID "
                    f"{zrodlo_pbn_uid_id}, wybieram pierwsze"
                )
                zrodlo = Zrodlo.objects.filter(pbn_uid_id=zrodlo_pbn_uid_id).first()

        p = matchuj_publikacje(
            Rekord,
            title=elem.value("object", "title"),
            year=elem.value_or_none("object", "year"),
            doi=elem.value_or_none("object", "doi"),
            public_uri=elem.value_or_none("object", "publicUri"),
            isbn=normalize_isbn(elem.value_or_none("object", "isbn")),
            zrodlo=zrodlo,
        )

        if p is not None:
            p = p.original

            if p.pbn_uid_id is not None and p.pbn_uid_id != elem.pk:
                print(
                    f"*** UWAGA Publikacja w BPP {p} ma już PBN UID {p.pbn_uid_id}, a wg procedury matchującej "
                    f"należałoby go zmienić na {elem.pk} -- rekord {elem}"
                )
                continue

            if p.pbn_uid_id is None:
                p.pbn_uid_id = elem.pk
                p.save()
            break


def split_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def integruj_publikacje():
    ids = list(Publication.objects.all().values_list("pk", flat=True))
    _bede_uzywal_bazy_danych_z_multiprocessing_z_django()
    pool = multiprocessing.Pool(os.cpu_count())

    results = []
    for elem in split_list(ids, 512):
        result = pool.apply_async(_integruj_single_part, args=(elem,))
        # _integruj_single_part(elem)
        results.append(result)

    wait_for_results(pool, results)


def _synchronizuj_pojedyncza_publikacje(client, rec):
    try:
        client.sync_publication(rec)
    except SameDataUploadedRecently:
        pass
    except HttpException as e:
        if e.status_code in [400, 500]:
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


def synchronizuj_publikacje(client, skip=0):
    #
    # Wydawnictwa zwarte
    #
    zwarte_baza = (
        Wydawnictwo_Zwarte.objects.filter(rok__gte=2017)
        .exclude(charakter_formalny__rodzaj_pbn=None)
        .exclude(isbn=None)
        .exclude(Q(doi=None) & (Q(public_www=None) | Q(www=None)))
    )

    for rec in pbar(
        zwarte_baza.filter(wydawnictwo_nadrzedne_id=None),
        label="sync_zwarte_ksiazki",
    ):
        _synchronizuj_pojedyncza_publikacje(client, rec)

    for rec in pbar(
        zwarte_baza.exclude(wydawnictwo_nadrzedne_id=None),
        label="sync_zwarte_rozdzialy",
    ):
        _synchronizuj_pojedyncza_publikacje(client, rec)

    #
    # Wydawnicwa ciagle
    #
    for rec in pbar(
        Wydawnictwo_Ciagle.objects.filter(rok__gte=2017)
        .exclude(charakter_formalny__rodzaj_pbn=None)
        .exclude(Q(doi=None) & (Q(public_www=None) | Q(www=None))),
        label="sync_ciagle",
    ):
        _synchronizuj_pojedyncza_publikacje(client, rec)


@transaction.atomic
def clear_all():
    for model in (
        Autor,
        Wydawnictwo_Zwarte,
        Wydawnictwo_Ciagle,
        Praca_Doktorska,
        Praca_Habilitacyjna,
        Jednostka,
        Wydawca,
        Jezyk,
        Uczelnia,
        Zrodlo,
    ):
        print(f"Setting pbn_uid_ids of {model} to null...")
        model.objects.exclude(pbn_uid_id=None).update(pbn_uid_id=None)

    for model in (
        Language,
        Country,
        Institution,
        Conference,
        Journal,
        Publisher,
        Scientist,
        Publication,
        SentData,
        PublikacjaInstytucji,
        OswiadczenieInstytucji,
    ):
        print(f"Deleting all {model}")
        model.objects.all()._raw_delete(model.objects.db)
