"""Scientist/author operations for PBN integrator."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from django.db.models import Q

from bpp.models import Autor, Autor_Dyscyplina, Tytul, Uczelnia
from bpp.util import pbar
from pbn_api.models import Scientist
from pbn_integrator.utils.constants import CPU_COUNT
from pbn_integrator.utils.django_imports import _ensure_django_imports
from pbn_integrator.utils.mongodb_ops import zapisz_mongodb

if TYPE_CHECKING:
    from pbn_api.client import PBNClient


def pbn_json_wez_pbn_id_stare(person):
    """Extract legacy PBN ID from person JSON data.

    Args:
        person: Scientist object.

    Returns:
        Legacy PBN ID or None.
    """
    pbn_id = None
    if person.value("object", "legacyIdentifiers", return_none=True):
        pbn_id = person.value("object", "legacyIdentifiers")[0]
    return pbn_id


def pobierz_i_zapisz_dane_jednej_osoby(
    client_or_token, personId, from_institution_api
) -> Scientist:
    """Fetch and save data for a single person.

    Args:
        client_or_token: PBN client or token string.
        personId: Person ID.
        from_institution_api: Whether data is from institution API.

    Returns:
        The Scientist object.
    """
    client = client_or_token
    if isinstance(client_or_token, str):
        # Create PBN client
        client = Uczelnia.objects.get_default().pbn_client(client_or_token)

    scientist = client.get_person_by_id(personId)
    return zapisz_mongodb(
        scientist, Scientist, from_institution_api=from_institution_api
    )


def pobierz_ludzi_z_uczelni(client_or_token: PBNClient, instutition_id, callback=None):
    """Fetch all people from a university.

    This procedure fetches data for all people from the university,
    can be run instead of pobierz_ludzi.

    Args:
        client_or_token: PBN client or token string.
        instutition_id: Institution ID.
        callback: Optional progress callback.
    """
    assert instutition_id is not None

    client = client_or_token
    if isinstance(client_or_token, str):
        # Create PBN client
        client = Uczelnia.objects.get_default().pbn_client(client_or_token)

    elementy = client.get_people_by_institution_id(instutition_id)

    # Determine number of threads (similar to initialize_pool logic)
    if CPU_COUNT == "auto":
        max_workers = os.cpu_count() * 3 // 4
        if max_workers < 1:
            max_workers = 1
    elif CPU_COUNT == "single":
        max_workers = 1
    else:
        max_workers = 4  # Default fallback

    # Use ThreadPoolExecutor instead of multiprocessing
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for person in pbar(
            elementy,
            count=len(elementy),
            label="Pobieranie autorów z uczelni",
            callback=callback,
        ):
            future = executor.submit(
                pobierz_i_zapisz_dane_jednej_osoby,
                client_or_token=client_or_token,
                personId=person["personId"],
                from_institution_api=True,
            )
            futures.append(future)

        # Wait for all futures to complete
        for future in pbar(
            as_completed(futures),
            count=len(futures),
            label="Oczekiwanie na wyniki",
            callback=callback,
        ):
            try:
                future.result()
            except Exception as e:
                print(f"Error processing person: {e}")

    from pbn_api.models.institution import Institution
    from pbn_api.models.osoba_z_instytucji import OsobaZInstytucji

    for person in elementy:
        if not Institution.objects.filter(pk=person["institutionId"]).exists():
            print(
                f"Pobieram extra instytucję {person.get('institutionName', '[brak nazwy]')}"
            )
            zapisz_mongodb(
                client_or_token.get_institution_by_id(person["institutionId"]),
                Institution,
                client_or_token,
            )

        OsobaZInstytucji.objects.update_or_create(
            personId=Scientist.objects.get(pk=person["personId"]),
            defaults={
                "firstName": person.get("firstName", ""),
                "lastName": person.get("lastName", ""),
                "institutionId": Institution.objects.get(pk=person["institutionId"]),
                "institutionName": person.get("institutionName", ""),
                "title": person.get("title") or "",
                "polonUuid": person.get("polonUuid"),
                "phdStudent": person.get("phdStudent", False),
                "_from": person.get("from"),
                "_to": person.get("to"),
            },
        )


def utworz_wpis_dla_jednego_autora(person):
    """Create a BPP author entry for a PBN person.

    Args:
        person: Scientist object.

    Returns:
        The created Autor object.
    """
    # Brak autora po stronie BPP, utwórz nowy rekord
    bpp_tytul = None
    cv = person.current_version
    pbn_tytul = cv["object"].pop("qualifications", None)
    if pbn_tytul:
        # jeżeli po stronie PBN podany jest tytuł, to jest on w skrótowej formie (np
        # mgr. inż.). Jeżeli po stronie BPP jest taki tytuł to OK, jeżeli nie, to
        # utwórzmy go, z taką samą nazwą:
        bpp_tytul = Tytul.objects.get_or_create(
            skrot=pbn_tytul, defaults={"nazwa": pbn_tytul}
        )[0]

    orcid = cv["object"].pop("orcid", None)
    if not orcid:
        orcid = None

    autor = Autor.objects.create(
        imiona=cv["object"].pop("name", "[brak danych]"),
        nazwisko=cv["object"].pop("lastName", "[brak danych]"),
        orcid=orcid,
        pbn_id=pbn_json_wez_pbn_id_stare(person),
        pbn_uid_id=person.pk,
        tytul=bpp_tytul,
    )

    cv["object"].pop("legacyIdentifiers", None)

    # Ignorujemy poprzednie miejsca pracy + zewnetrzne identyfiaktory + obecne
    # miesjca pracy...
    for ignoredKey in [
        "verifiedOrcid",
        "currentEmployments",
        "externalIdentifiers",
        "archivalEmployments",
    ]:
        cv["object"].pop(ignoredKey, None)

    from pbn_integrator.importer import assert_dictionary_empty

    assert_dictionary_empty(cv["object"])
    return autor


def integruj_autorow_z_uczelni(
    client: PBNClient, instutition_id, import_unexistent=False, callback=None
):
    """Integrate authors from a university.

    This procedure should be run after fetching the people database.

    Args:
        client: PBN client.
        instutition_id: Institution ID.
        import_unexistent: Whether to create missing authors in BPP.
        callback: Optional progress callback.
    """
    _ensure_django_imports()
    from import_common.core import matchuj_autora

    scientists = Scientist.objects.filter(from_institution_api=True)
    total = scientists.count()

    for person in pbar(scientists, total, "Integrowanie autorów", callback=callback):
        autor = matchuj_autora(
            imiona=person.value("object", "name", return_none=True),
            nazwisko=person.value("object", "lastName", return_none=True),
            orcid=person.value("object", "orcid", return_none=True),
            pbn_id=pbn_json_wez_pbn_id_stare(person),
            pbn_uid_id=person.pk,
            tytul_str=person.value("object", "qualifications", return_none=True),
        )

        if autor is not None:
            if autor.pbn_uid_id is None:
                autor.pbn_uid_id = person.mongoId
                autor.save()
            else:
                if autor.pbn_uid_id != person.pk:
                    print(
                        f"UWAGA: autor {autor} zmatchował się z PBN UID {person.pk} czyli {person}, "
                        f"sprawdź czy przypadkiem nie masz zdublowanych wpisów po stronie PBN!"
                    )

        else:
            # autor is None:
            if not import_unexistent:
                # Brak autora po stronie BPP, nie chcemy tworzyć nowych rekordów
                print(f"Brak dopasowania w jednostce dla autora {person}")
                continue

            utworz_wpis_dla_jednego_autora(person)


def weryfikuj_orcidy(client: PBNClient, instutition_id):
    """Verify ORCIDs for authors.

    Check for each author with ORCID but without PBN UID
    whether that ORCID exists in the PBN database.

    Args:
        client: PBN client.
        instutition_id: Institution ID.
    """
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


def matchuj_autora_po_stronie_pbn(imiona, nazwisko, orcid):  # noqa: C901
    """Match an author on the PBN side.

    Args:
        imiona: First names.
        nazwisko: Last name.
        orcid: ORCID identifier.

    Returns:
        Scientist object or None.
    """
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
    """Integrate all authors that don't have PBN UID."""
    autorzy_z_dyscyplina_ids = Autor_Dyscyplina.objects.values("autor_id").distinct()

    for autor in Autor.objects.filter(pk__in=autorzy_z_dyscyplina_ids, pbn_uid_id=None):
        sciencist = matchuj_autora_po_stronie_pbn(
            autor.imiona, autor.nazwisko, autor.orcid
        )
        if sciencist:
            print(f"==> integracja wszystkich: ustawiam {autor} na {sciencist.pk}")
            autor.pbn_uid = sciencist
            autor.save()
