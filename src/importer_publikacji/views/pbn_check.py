"""Sprawdzenie obecności publikacji w PBN po DOI + linkowanie pbn_uid.

Logika podzielona na małe funkcje, żeby ułatwić mockowanie w testach.
"""

import logging

from django.db import IntegrityError

from import_common.normalization import normalize_doi

logger = logging.getLogger(__name__)


def _empty_pbn_result():
    """Zwróć pusty słownik wyniku sprawdzenia PBN."""
    return {
        "pbn_mongo_id": None,
        "pbn_url": None,
        "pbn_error": None,
        "pbn_needs_auth": False,
    }


def _get_pbn_publication_by_doi(client, doi):
    """Wywołaj API PBN i zwróć (data, result) lub result przy błędzie.

    Zwraca krotkę (data, None) przy sukcesie lub
    (None, result_dict) przy błędzie wymagającym
    natychmiastowego zwrotu.
    """
    from pbn_api.exceptions import (
        AccessDeniedException,
        HttpException,
        NeedsPBNAuthorisationException,
        PraceSerwisoweException,
    )

    result = _empty_pbn_result()

    try:
        data = client.get_publication_by_doi(doi)
    except (
        AccessDeniedException,
        NeedsPBNAuthorisationException,
    ):
        result["pbn_needs_auth"] = True
        return None, result
    except PraceSerwisoweException:
        result["pbn_error"] = "PBN w trakcie prac serwisowych"
        return None, result
    except HttpException as e:
        if getattr(e, "status_code", None) == 404:
            return None, result
        result["pbn_error"] = f"Błąd komunikacji z PBN: {e}"
        return None, result
    except Exception as e:
        logger.warning("Błąd sprawdzania PBN: %s", e)
        result["pbn_error"] = f"Błąd sprawdzania PBN: {e}"
        return None, result

    return data, None


def _ensure_pbn_publication_local(data):
    """Zapisz dane z PBN API jako lokalny rekord Publication."""
    try:
        from pbn_api.models import Publication
        from pbn_integrator.utils import zapisz_mongodb

        zapisz_mongodb(data, Publication)
    except Exception as e:
        logger.warning(
            "Nie udało się zapisać rekordu PBN lokalnie: %s",
            e,
        )


def _populate_pbn_result(result, data, session):
    """Wypełnij result danymi z odpowiedzi PBN API.

    Jeśli znaleziono odpowiednik, zapisz/zaktualizuj
    lokalny rekord pbn_api.Publication.
    """
    if not (data and isinstance(data, dict)):
        return

    mongo_id = data.get("mongoId")
    if not mongo_id:
        return

    result["pbn_mongo_id"] = mongo_id
    uczelnia = session.uczelnia
    if uczelnia and uczelnia.pbn_api_root:
        from bpp.const import LINK_PBN_DO_PUBLIKACJI

        result["pbn_url"] = LINK_PBN_DO_PUBLIKACJI.format(
            pbn_api_root=uczelnia.pbn_api_root,
            pbn_uid_id=mongo_id,
        )

    # Zaciągnij/zaktualizuj lokalny rekord Publication
    _ensure_pbn_publication_local(data)

    session.matched_data["pbn_mongo_id"] = mongo_id
    session.save(update_fields=["matched_data"])


def _check_pbn_by_doi(session):
    """Sprawdź czy publikacja z danym DOI istnieje w PBN.

    Zwraca dict z kluczami pbn_mongo_id, pbn_url,
    pbn_error, pbn_needs_auth — lub None jeśli sprawdzenie
    nie dotyczy (brak DOI, provider PBN, brak konfiguracji).
    """
    if session.provider_name == "PBN":
        return None

    doi = session.normalized_data.get("doi")
    if not doi:
        return None

    normalized = normalize_doi(doi)
    if not normalized:
        return None

    try:
        from ..providers.pbn import _get_pbn_client

        client = _get_pbn_client(session.uczelnia)
    except Exception as e:
        logger.warning("Nie można utworzyć klienta PBN: %s", e)
        return None

    data, error_result = _get_pbn_publication_by_doi(client, normalized)
    if error_result is not None:
        return error_result

    result = _empty_pbn_result()
    _populate_pbn_result(result, data, session)
    return result


def _link_pbn_uid(session, record):
    """Powiąż PBN UID z rekordem publikacji, jeśli znaleziono."""
    pbn_mongo_id = session.matched_data.get("pbn_mongo_id")
    if not pbn_mongo_id:
        return

    from pbn_api.models import Publication

    try:
        pbn_pub = Publication.objects.get(
            mongoId=pbn_mongo_id,
        )
        record.pbn_uid = pbn_pub
        record.save(update_fields=["pbn_uid_id"])
    except Publication.DoesNotExist:
        logger.info(
            "Rekord PBN %s nie istnieje lokalnie — pominięto linkowanie",
            pbn_mongo_id,
        )
    except IntegrityError:
        logger.warning(
            "PBN UID %s jest już powiązany z innym rekordem BPP",
            pbn_mongo_id,
        )
