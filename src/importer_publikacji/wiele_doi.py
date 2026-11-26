"""Import wielu DOI naraz (FD#483).

Redaktor wkleja listę numerów DOI; powstaje paczka (``MultipleWorksImport``
z dostawcą CrossRef), a zadanie w tle pobiera dane kolejno dla każdego DOI
i dla każdego tworzy ZWYKŁĄ sesję importu. Rekord publikacji powstaje
dopiero, gdy redaktor przejdzie sesję w kreatorze — tu niczego nie tworzymy
automatycznie.

Moduł zawiera logikę niezależną od widoków: parsowanie listy, sprawdzenie
w BPP i w PBN oraz przygotowanie wierszy ekranu zbiorczego.
"""

import logging
from dataclasses import dataclass, field
from types import SimpleNamespace

from django.conf import settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from import_common.normalization import extract_doi_from_url

from .models import DEFAULT_STALL_TIMEOUT, ImportSession

logger = logging.getLogger(__name__)

# Dostawca, którym pobierane są dane dla paczki DOI.
DOSTAWCA_DOI = "CrossRef"

# Ile różnych DOI przyjmujemy w jednym zleceniu. Dane pobierane są kolejno,
# jedno DOI po drugim, więc limit ogranicza czas pracy jednego zadania w tle
# i obciążenie serwera CrossRef. Nadpisywalny ustawieniem
# ``IMPORTER_WIELE_DOI_LIMIT``.
DOMYSLNY_LIMIT_DOI = 50

# Ile znaków nierozpoznanej linii pokazujemy na ekranie zbiorczym.
_MAKS_DLUGOSC_LINII = 200

PBN_JEST = "jest"
PBN_BRAK = "brak"
PBN_NIE_SPRAWDZONO = "nie_sprawdzono"


def limit_doi() -> int:
    return getattr(settings, "IMPORTER_WIELE_DOI_LIMIT", DOMYSLNY_LIMIT_DOI)


@dataclass
class ListaDoi:
    """Wynik parsowania wklejonej listy."""

    # Znormalizowane, niepowtarzające się DOI w kolejności wklejenia.
    doi: list[str] = field(default_factory=list)
    # Linie, w których nie udało się rozpoznać żadnego DOI.
    nierozpoznane: list[str] = field(default_factory=list)
    # Ile powtórzeń pominięto.
    duplikaty: int = 0


def parsuj_liste_doi(tekst: str | None) -> ListaDoi:
    """Wyłuskaj numery DOI z wklejonego tekstu.

    Jedna linia to zwykle jedno DOI, ale kilka DOI w linii (oddzielonych
    spacjami lub tabulatorami) też zadziała. Przyjmujemy sam numer, adres
    ``https://doi.org/…``, zapis ``doi:10.…`` oraz adres strony zawierający
    numer DOI. Wielkość liter nie ma znaczenia; powtórzenia i puste linie
    są pomijane. Linia bez rozpoznawalnego DOI trafia do ``nierozpoznane``
    — nic nie znika po cichu.
    """
    wynik = ListaDoi()
    widziane = set()
    for linia in (tekst or "").splitlines():
        linia = linia.strip()
        if not linia:
            continue
        znalezione = [
            doi for doi in map(extract_doi_from_url, linia.split()) if doi is not None
        ]
        if not znalezione:
            wynik.nierozpoznane.append(linia[:_MAKS_DLUGOSC_LINII])
            continue
        for doi in znalezione:
            if doi in widziane:
                wynik.duplikaty += 1
                continue
            widziane.add(doi)
            wynik.doi.append(doi)
    return wynik


def znajdz_w_bpp(doi, session=None) -> list[dict]:
    """Rekordy BPP, które wyglądają na tę samą pracę.

    Ten sam mechanizm, co ostrzeżenie „Potencjalne duplikaty w BPP” w kroku
    weryfikacji kreatora: po DOI, a gdy dane zostały pobrane — także po
    tytule. Bez pobranych danych (np. CrossRef nie zna DOI) szukamy po
    samym DOI z listy.
    """
    from .views.steps import _find_duplicates

    if session is None or not session.normalized_data:
        session = SimpleNamespace(normalized_data={"doi": doi})

    return [
        {
            "model": rekord._meta.model_name,
            "pk": rekord.pk,
            "tytul": str(rekord.tytul_oryginalny or "")[:300],
            "metoda": metoda,
        }
        for rekord, metoda in _find_duplicates(session)
    ]


def klient_pbn(uczelnia):
    """Klient PBN do sprawdzania DOI albo ``None``, gdy uczelnia nie ma
    skonfigurowanego dostępu do PBN."""
    from .providers.pbn import _get_pbn_client

    try:
        return _get_pbn_client(uczelnia)
    except ValueError:
        # _get_pbn_client zgłasza ValueError wyłącznie przy braku
        # konfiguracji PBN w uczelni — to nie błąd, tylko „nie sprawdzamy”.
        return None


def sprawdz_w_pbn(client, uczelnia, doi) -> dict:
    """Sprawdź, czy praca o tym DOI jest w PBN.

    Korzysta z tego samego zapytania o DOI, co pojedynczy import. Błąd PBN
    nie przerywa pobierania paczki — wynik to „nie sprawdzono” z opisem.
    """
    from .views.pbn_check import _get_pbn_publication_by_doi
    from .views.pbn_search import _pbn_url

    if client is None:
        return {
            "stan": PBN_NIE_SPRAWDZONO,
            "komunikat": "Dostęp do PBN nie jest skonfigurowany.",
        }

    dane, blad = _get_pbn_publication_by_doi(client, doi)
    if blad is not None:
        if blad["pbn_needs_auth"]:
            return {
                "stan": PBN_NIE_SPRAWDZONO,
                "komunikat": "PBN odmówił dostępu.",
            }
        if blad["pbn_error"]:
            return {"stan": PBN_NIE_SPRAWDZONO, "komunikat": blad["pbn_error"][:300]}
        return {"stan": PBN_BRAK}

    mongo_id = dane.get("mongoId") if isinstance(dane, dict) else None
    if not mongo_id:
        return {"stan": PBN_BRAK}
    return {
        "stan": PBN_JEST,
        "mongo_id": mongo_id,
        "url": _pbn_url(uczelnia, mongo_id) or "",
    }


def _url_redagowania(pozycja):
    try:
        return reverse(f"admin:bpp_{pozycja['model']}_change", args=[pozycja["pk"]])
    except NoReverseMatch:
        return None  # model bez strony w module redagowania — sam tytuł


# Stan wiersza dla sesji w statusie niewymagającym dodatkowych warunków:
# status sesji → (kod, etykieta, klasa etykiety).
_STANY_SESJI = {
    ImportSession.Status.FETCHING: ("pobieranie", "Trwa pobieranie", "warning"),
    ImportSession.Status.CANCELLED: ("anulowano", "Anulowano", "secondary"),
    ImportSession.Status.CREATING: (
        "tworzenie",
        "Trwa tworzenie rekordu",
        "warning",
    ),
    ImportSession.Status.COMPLETED: ("zakonczono", "Utworzono rekord", "success"),
    ImportSession.Status.FETCHED: ("pobrano", "Pobrano", "primary"),
}


def _stan_sesji(session):
    if session.status in _STANY_SESJI:
        return _STANY_SESJI[session.status]
    if session.status == ImportSession.Status.IMPORT_FAILED:
        if session.last_failed_stage == "create":
            return "blad", "Błąd tworzenia rekordu", "alert"
        return "blad", "Błąd pobierania", "alert"
    # Pozostałe statusy to kolejne kroki kreatora.
    return "w_kreatorze", f"Pobrano — {session.get_status_display()}", "primary"


def _stan_wiersza(entry, pobieranie_w_tle):
    """Zwróć (kod, etykieta, klasa etykiety) stanu pobierania wpisu."""
    session = entry.session
    if entry.parse_error:
        return "niepoprawny", "Nie rozpoznano DOI", "alert"
    zakonczona = (
        session is not None and session.status == ImportSession.Status.COMPLETED
    )
    if entry.skipped and not zakonczona:
        return "pominiety", "Pominięto", "secondary"
    if session is not None:
        return _stan_sesji(session)
    if pobieranie_w_tle:
        return "w_kolejce", "W kolejce", "secondary"
    return "nie_pobrano", "Nie pobrano", "warning"


def pobieranie_przerwane(batch, entries, *, now=None) -> bool:
    """Czy zadanie w tle przestało pracować, choć zostały wpisy do pobrania.

    Zadanie po każdym DOI odświeża ``batch.modified``; brak postępu dłużej
    niż próg watchdoga sesji (``IMPORTER_STALL_TIMEOUT``) oznacza, że worker
    zginął albo zadanie nigdy nie wystartowało.
    """
    if not any(_czeka_na_pobranie(e) for e in entries):
        return False
    timeout = getattr(settings, "IMPORTER_STALL_TIMEOUT", DEFAULT_STALL_TIMEOUT)
    now = now or timezone.now()
    return (now - batch.modified).total_seconds() > timeout


def _czeka_na_pobranie(entry) -> bool:
    return entry.session_id is None and not entry.skipped and not entry.parse_error


def kontekst_paczki_doi(batch, entries) -> dict:
    """Kontekst ekranu zbiorczego paczki DOI."""
    przerwane = pobieranie_przerwane(batch, entries)
    czekajace = sum(1 for e in entries if _czeka_na_pobranie(e))
    pobieranie_w_tle = bool(czekajace) and not przerwane

    wiersze = []
    liczniki = {"pobrano": 0, "bledy": 0, "w_bpp": 0, "w_pbn": 0, "utworzono": 0}
    trwa = pobieranie_w_tle
    for entry in entries:
        kod, etykieta, klasa = _stan_wiersza(entry, pobieranie_w_tle)
        session = entry.session
        sprawdzenie = entry.sprawdzenie or {}
        # Po utworzeniu rekordu „duplikatem” byłby on sam — nie pokazujemy.
        w_bpp = [] if kod == "zakonczono" else sprawdzenie.get("bpp") or []
        pbn = sprawdzenie.get("pbn") or {}

        if kod in ("pobrano", "w_kreatorze", "tworzenie", "zakonczono"):
            liczniki["pobrano"] += 1
        if kod in ("blad", "niepoprawny"):
            liczniki["bledy"] += 1
        if kod == "zakonczono":
            liczniki["utworzono"] += 1
        if w_bpp:
            liczniki["w_bpp"] += 1
        if pbn.get("stan") == PBN_JEST:
            liczniki["w_pbn"] += 1
        if kod in ("pobieranie", "tworzenie"):
            trwa = True

        wiersze.append(
            {
                "entry": entry,
                "session": session,
                "kod": kod,
                "etykieta": etykieta,
                "klasa": klasa,
                "tytul": (session.normalized_data or {}).get("title", "")
                if session is not None
                else "",
                "komunikat_bledu": session.last_error_message
                if session is not None and kod == "blad"
                else "",
                "w_bpp": [
                    {**pozycja, "url": _url_redagowania(pozycja)} for pozycja in w_bpp
                ],
                "pbn": pbn,
            }
        )

    return {
        "batch": batch,
        "wiersze": wiersze,
        "liczniki": liczniki,
        "progress": batch.progress,
        "lacznie": len(entries),
        "czekajace": czekajace,
        "przerwane": przerwane,
        "odswiezaj": trwa,
    }
