"""Wyszukiwanie odpowiednika publikacji w PBN dla kroku „Sprawdź w PBN".

Trzy niezależne osie wyszukiwania (każda ≤ ``MAX_RESULTS_PER_AXIS`` pozycji):

* **DOI** — serwer PBN (``search_publications(doi=…)``),
* **tytuł** — serwer PBN (``search_publications(title=…)``),
* **strona WWW** — lokalny cache ``pbn_api.Publication`` po ``publicUri``
  (PBN API nie udostępnia wyszukiwania po adresie URL publikacji).

Logika rozbita na małe funkcje, żeby ułatwić mockowanie w testach. Widok
odpytuje ``_search_pbn_equivalents`` (GET kroku) i ``_select_pbn_equivalent``
(akcja wyboru odpowiednika).

Uwaga: ``search_publications`` zwraca ``PageableResource`` — leniwy iterator,
który przy iteracji dociąga kolejne strony z sieci. Ograniczamy go przez
``itertools.islice`` (NIE ``[:10]`` — na iteratorze nie zadziała, a wynik może
mieć tysiące pozycji).
"""

import itertools
import logging

from import_common.normalization import normalize_doi

logger = logging.getLogger(__name__)

# Ile pozycji maksymalnie na jedną oś wyszukiwania.
MAX_RESULTS_PER_AXIS = 10

AXIS_DOI = "DOI"
AXIS_TITLE = "tytuł"
AXIS_WWW = "strona WWW"


def _operator_pbn_logged_in(user) -> bool:
    """Czy operator ma (prawdopodobnie) ważny osobisty token PBN.

    „Zalogowany do PBN" = konto operatora ma niepusty ``pbn_token`` i
    ``pbn_token_possibly_valid()`` (heurystyka czasowa z grace-time).
    """
    if user is None or not getattr(user, "pbn_token", ""):
        return False
    checker = getattr(user, "pbn_token_possibly_valid", None)
    if callable(checker):
        return bool(checker())
    return True


def _normalize_www(url) -> str:
    """Znormalizuj URL do dopasowania po ``publicUri``.

    Obcina protokół (``http(s)://``) i końcowy ``/`` — dopasowanie i tak jest
    ``icontains``, więc chodzi tylko o ograniczenie oczywistych rozjazdów.
    """
    if not url:
        return ""
    u = str(url).strip()
    low = u.lower()
    for prefix in ("https://", "http://"):
        if low.startswith(prefix):
            u = u[len(prefix) :]
            break
    return u.rstrip("/")


def _pbn_url(uczelnia, mongo_id):
    """Zbuduj link do rekordu w PBN (lub None gdy brak danych)."""
    if not mongo_id or not uczelnia or not getattr(uczelnia, "pbn_api_root", None):
        return None
    from bpp.const import LINK_PBN_DO_PUBLIKACJI

    return LINK_PBN_DO_PUBLIKACJI.format(
        pbn_api_root=uczelnia.pbn_api_root,
        pbn_uid_id=mongo_id,
    )


def _extract_object(elem):
    """Wyciągnij słownik ``object`` z elementu wyniku PBN.

    PBN owija dane publikacji w ``versions[].object`` (bieżąca wersja ma
    ``current=True``). Funkcja jest defensywna — jeśli element ma płaską
    strukturę, zwraca go bez zmian.
    """
    if not isinstance(elem, dict):
        return {}
    versions = elem.get("versions")
    if isinstance(versions, list) and versions:
        current = next(
            (v for v in versions if isinstance(v, dict) and v.get("current")),
            None,
        )
        if current is None and isinstance(versions[0], dict):
            current = versions[0]
        if isinstance(current, dict) and isinstance(current.get("object"), dict):
            return current["object"]
    return elem


def _result_from_search_elem(elem, axis, uczelnia):
    """Znormalizuj element z ``search_publications`` do wspólnej struktury."""
    obj = _extract_object(elem)
    mongo_id = elem.get("mongoId") if isinstance(elem, dict) else None

    def field(key):
        val = obj.get(key)
        if val in (None, "") and isinstance(elem, dict):
            val = elem.get(key)
        return val

    return {
        "mongo_id": mongo_id,
        "title": field("title") or "",
        "doi": field("doi") or "",
        "year": field("year"),
        "pbn_url": _pbn_url(uczelnia, mongo_id),
        "axis": axis,
    }


def _result_from_publication(pub, axis, uczelnia):
    """Znormalizuj lokalny rekord ``pbn_api.Publication`` do wspólnej struktury."""
    return {
        "mongo_id": pub.pk,
        "title": pub.title or "",
        "doi": pub.doi or "",
        "year": pub.year,
        "pbn_url": _pbn_url(uczelnia, pub.pk),
        "axis": axis,
    }


def _dedup_by_mongo_id(results):
    """Usuń duplikaty po ``mongo_id`` w obrębie jednej osi, zachowaj kolejność."""
    seen = set()
    out = []
    for r in results:
        mid = r.get("mongo_id")
        if not mid or mid in seen:
            continue
        seen.add(mid)
        out.append(r)
    return out


def _search_pbn_server(client, axis, key, value, uczelnia):
    """Wyszukaj na serwerze PBN po jednym parametrze (≤ MAX_RESULTS_PER_AXIS).

    NIE dodajemy parametru ``type`` — szukamy dowolnego typu publikacji
    (autocomplete wydawnictw nadrzędnych wymusza ``type="BOOK"``, my nie).
    """
    resource = client.search_publications(**{key: value})
    results = [
        _result_from_search_elem(elem, axis, uczelnia)
        for elem in itertools.islice(resource, MAX_RESULTS_PER_AXIS)
    ]
    return _dedup_by_mongo_id(results)


def _search_pbn_local_www(url, uczelnia):
    """Dopasuj po stronie WWW w lokalnym cache ``pbn_api.Publication``."""
    norm = _normalize_www(url)
    if not norm:
        return []
    from pbn_api.models import Publication

    qs = Publication.objects.filter(publicUri__icontains=norm)[:MAX_RESULTS_PER_AXIS]
    return _dedup_by_mongo_id(
        [_result_from_publication(pub, AXIS_WWW, uczelnia) for pub in qs]
    )


def _search_pbn_equivalents(session, user) -> dict:
    """Wyszukaj odpowiedniki pracy w PBN po DOI / tytule / stronie WWW.

    Zwraca dict:
    ``{"by_doi", "by_title", "by_www", "total_unique", "error", "needs_auth"}``.
    Osie serwerowe (DOI, tytuł) wymagają klienta PBN; oś WWW działa zawsze
    (lokalny cache). Błędy PBN degradują do komunikatu / needs_auth — bez
    wywalania kroku.
    """
    from pbn_api.exceptions import (
        AccessDeniedException,
        NeedsPBNAuthorisationException,
        PraceSerwisoweException,
        WillNotExportError,
    )

    result = {
        "by_doi": [],
        "by_title": [],
        "by_www": [],
        "total_unique": 0,
        "error": None,
        "needs_auth": False,
    }

    uczelnia = session.uczelnia
    nd = session.normalized_data or {}
    doi = nd.get("doi")
    title = nd.get("title")
    url = nd.get("url")

    # Oś WWW — lokalny cache, bez sieci, robimy zawsze.
    try:
        result["by_www"] = _search_pbn_local_www(url, uczelnia)
    except Exception as e:
        logger.warning("Błąd wyszukiwania PBN po WWW: %s", e)

    # Osie serwerowe — wymagają klienta PBN z tokenem operatora.
    client = None
    try:
        client = uczelnia.pbn_client(user.pbn_token) if uczelnia else None
    except Exception as e:
        logger.warning("Nie można utworzyć klienta PBN: %s", e)
        client = None

    if client is not None:
        normalized_doi = normalize_doi(doi) if doi else None
        axes = [
            (AXIS_DOI, "doi", normalized_doi, "by_doi"),
            (AXIS_TITLE, "title", title, "by_title"),
        ]
        for axis, key, value, bucket in axes:
            if not value:
                continue
            try:
                result[bucket] = _search_pbn_server(client, axis, key, value, uczelnia)
            except (
                NeedsPBNAuthorisationException,
                AccessDeniedException,
                WillNotExportError,
            ):
                result["needs_auth"] = True
            except PraceSerwisoweException:
                result["error"] = "PBN w trakcie prac serwisowych"
            except Exception as e:
                logger.warning("Błąd wyszukiwania PBN (%s): %s", axis, e)
                result["error"] = f"Błąd wyszukiwania w PBN: {e}"

    unique_ids = {
        r["mongo_id"]
        for bucket in ("by_doi", "by_title", "by_www")
        for r in result[bucket]
        if r.get("mongo_id")
    }
    result["total_unique"] = len(unique_ids)
    return result


def _select_pbn_equivalent(session, user, mongo_id):
    """Ustaw wskazany rekord PBN jako odpowiednik importowanej pracy.

    Pobiera rekord lokalnie (``get_publication_by_id`` + ``zapisz_mongodb``),
    żeby ``_link_pbn_uid`` mógł go powiązać przy tworzeniu, po czym zapisuje
    ``matched_data["pbn_mongo_id"]``. Zwraca ``True`` gdy wybór ustawiono.
    """
    if not mongo_id:
        return False

    uczelnia = session.uczelnia
    if uczelnia is None:
        logger.warning("Brak uczelni w sesji — nie można pobrać rekordu PBN")
        return False

    try:
        client = uczelnia.pbn_client(user.pbn_token)
        data = client.get_publication_by_id(mongo_id)
    except Exception as e:
        logger.warning("Nie udało się pobrać rekordu PBN %s: %s", mongo_id, e)
        # Rekord mógł już istnieć lokalnie (np. z osi WWW) — spróbuj mimo to.
        from pbn_api.models import Publication

        if not Publication.objects.filter(pk=mongo_id).exists():
            return False
        session.matched_data["pbn_mongo_id"] = mongo_id
        session.save(update_fields=["matched_data"])
        return True

    from pbn_api.models import Publication
    from pbn_integrator.utils import zapisz_mongodb

    try:
        zapisz_mongodb(data, Publication)
    except Exception as e:
        logger.warning("Nie udało się zapisać rekordu PBN %s lokalnie: %s", mongo_id, e)

    session.matched_data["pbn_mongo_id"] = mongo_id
    session.save(update_fields=["matched_data"])
    return True


def _clear_pbn_equivalent(session):
    """Usuń wybrany odpowiednik PBN z sesji."""
    if "pbn_mongo_id" in session.matched_data:
        del session.matched_data["pbn_mongo_id"]
        session.save(update_fields=["matched_data"])


def _selected_pbn_publication(session):
    """Zwróć lokalny ``pbn_api.Publication`` wybrany jako odpowiednik (lub None)."""
    mongo_id = (session.matched_data or {}).get("pbn_mongo_id")
    if not mongo_id:
        return None
    from pbn_api.models import Publication

    return Publication.objects.filter(pk=mongo_id).first()
