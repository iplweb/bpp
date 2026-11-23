"""Matchowanie źródeł (czasopism) po ISSN/e-ISSN, mniswId i tytule."""

import html

from django.contrib.postgres.lookups import Unaccent
from django.db.models import Q, Value
from django.db.models.functions import Lower, Trim

from bpp.models import Zrodlo
from bpp.models.zrodlo import issn_norm_expr

from ..normalization import normalize_tytul_zrodla


def _normalize_issn_value(value: str | None) -> str | None:
    """ISSN do porównań: bez myślników/spacji, wielkie litery (cyfra kontr. X)."""
    if not value or not isinstance(value, str):
        return None
    return value.replace("-", "").replace(" ", "").strip().upper() or None


def _jedyny(kandydaci: list[Zrodlo]) -> Zrodlo | None:
    return kandydaci[0] if len(kandydaci) == 1 else None


def _kandydaci_po_issn(numery: list[str]) -> list[Zrodlo]:
    """Źródła mające którykolwiek ze znormalizowanych ``numery`` w polu
    ``issn`` albo ``e_issn`` (adnotowane ``_issn_norm``/``_e_issn_norm``)."""
    return list(
        Zrodlo.objects.annotate(
            _issn_norm=issn_norm_expr("issn"),
            _e_issn_norm=issn_norm_expr("e_issn"),
        ).filter(Q(_issn_norm__in=numery) | Q(_e_issn_norm__in=numery))
    )


def _try_match_zrodlo_by_issn(issn: str | None, e_issn: str | None) -> Zrodlo | None:
    """Próbuje jednoznacznie dopasować źródło po ISSN lub e-ISSN.

    Porównanie ignoruje myślniki/spacje i wielkość liter. Kolejność:
    ISSN → pole ``issn``, e-ISSN → pole ``e_issn``, a na końcu dowolny z
    numerów → dowolne z pól (cross-field). Źródła danych bywają niespójne
    co do tego, który numer jest drukowany, a który elektroniczny (np.
    CrossRef podaje dla MDPI tylko e-ISSN, a w BPP numer siedzi w polu
    ``issn``) — FD#451. Zwraca źródło tylko przy dokładnie jednym trafieniu.

    Wydajność: jedno zapytanie pobiera wszystkich kandydatów (dowolny numer
    w dowolnym polu), a priorytety rozstrzygane są w Pythonie. Filtr używa
    tych samych wyrażeń co indeksy funkcyjne na ``Zrodlo`` (``zrodlo_issn_norm``,
    ``zrodlo_e_issn_norm``), więc to dwa index scany zamiast przeglądania
    całej tabeli — ważne przy importach list z dziesiątkami tysięcy wierszy.
    """
    issn = _normalize_issn_value(issn)
    e_issn = _normalize_issn_value(e_issn)
    numery = [n for n in (issn, e_issn) if n]
    if not numery:
        return None

    kandydaci = _kandydaci_po_issn(numery)

    if issn is not None:
        result = _jedyny([z for z in kandydaci if z._issn_norm == issn])
        if result:
            return result

    if e_issn is not None:
        result = _jedyny([z for z in kandydaci if z._e_issn_norm == e_issn])
        if result:
            return result

    return _jedyny(kandydaci)


def _try_match_zrodlo_by_mnisw_id(mnisw_id: int | str | None) -> Zrodlo | None:
    """Próbuje dopasować źródło po mniswId przez PBN Journal."""
    if mnisw_id is None:
        return None

    from pbn_api.models import Journal

    try:
        mnisw_id = int(mnisw_id) if isinstance(mnisw_id, str) else mnisw_id
    except (ValueError, TypeError):
        return None

    try:
        pbn_journal = Journal.objects.get(mniswId=mnisw_id)
        zrodlo = Zrodlo.objects.filter(pbn_uid=pbn_journal).first()
        if zrodlo:
            return zrodlo
    except Journal.DoesNotExist:
        pass
    except Journal.MultipleObjectsReturned:
        for pbn_journal in Journal.objects.filter(mniswId=mnisw_id):
            zrodlo = Zrodlo.objects.filter(pbn_uid=pbn_journal).first()
            if zrodlo:
                return zrodlo

    return None


def _disambiguate_by_issn(qs, issn: str | None, e_issn: str | None) -> Zrodlo | None:
    """Zawęża niejednoznaczny zbiór źródeł po ISSN/e-ISSN (cross-field).

    JCR bywa niespójny w kolumnach ISSN/eISSN, więc numer z dowolnego pola
    pliku dopasowujemy do dowolnego pola źródła (issn ORAZ e_issn). Zwraca
    źródło tylko wtedy, gdy filtr zawęzi zbiór do dokładnie jednego — przy
    zerze lub nadal wielu kandydatach zwraca None (nie zgadujemy).
    """
    numery = [n for n in (issn, e_issn) if n]
    if not numery:
        return None
    kandydaci = list(qs.filter(Q(issn__in=numery) | Q(e_issn__in=numery))[:2])
    if len(kandydaci) == 1:
        return kandydaci[0]
    return None


def zrodla_po_tytule_bez_diakrytykow(
    tytul: str | None, pola: tuple[str, ...] = ("nazwa",)
):
    """Źródła, których któreś z ``pola`` równa się ``tytul`` bez diakrytyków.

    Porównanie ignoruje wielkość liter, znaki diakrytyczne i białe znaki na
    brzegach — „Vedelem Tudomany" (CrossRef) trafia w „Védelem Tudomány"
    (BPP), FD#460. Diakrytyki zdejmuje PostgreSQL-owe ``unaccent`` PO OBU
    stronach (ta sama funkcja co przy dopasowaniu autorów), więc folding jest
    identyczny dla wartości z bazy i wartości szukanej, także dla znaków
    spoza dekompozycji Unicode (``ł``, ``ø``). Encje HTML z CrossRef są
    dekodowane (FD#321).

    Zwraca QuerySet (pusty, z jednym lub wieloma rekordami) albo ``None``
    dla pustego tytułu.
    """
    if not tytul or not isinstance(tytul, str):
        return None
    tytul = html.unescape(tytul).strip()
    if not tytul:
        return None
    szukany = Lower(Unaccent(Value(tytul)))
    adnotacje = {f"_{pole}_fold": Lower(Unaccent(Trim(pole))) for pole in pola}
    filtr = Q()
    for nazwa_adnotacji in adnotacje:
        filtr |= Q(**{nazwa_adnotacji: szukany})
    return Zrodlo.objects.annotate(**adnotacje).filter(filtr)


def _try_match_zrodlo_by_title_single(
    elem: str,
    disable_skrot: bool,
    disable_fuzzy: bool,
    issn: str | None = None,
    e_issn: str | None = None,
) -> Zrodlo | None:
    """Próbuje dopasować pojedynczy tytuł źródła.

    Gdy tytuł pasuje do wielu źródeł, próbuje je rozróżnić po ISSN/e-ISSN
    zamiast od razu rezygnować — bez tego dwa źródła o tym samym tytule
    nigdy nie zostałyby dopasowane, mimo że ISSN jednoznacznie wskazuje jedno.
    """
    elem = normalize_tytul_zrodla(elem)
    filtr = Q(nazwa__iexact=elem)
    if not disable_skrot:
        filtr |= Q(skrot__iexact=elem)
    try:
        return Zrodlo.objects.get(filtr)
    except Zrodlo.MultipleObjectsReturned:
        return _disambiguate_by_issn(Zrodlo.objects.filter(filtr), issn, e_issn)
    except Zrodlo.DoesNotExist:
        pass

    # Tytuł różniący się tylko diakrytykami (FD#460). Tylko gdy wolno
    # dopasowywać luźniej: importy hurtowe (listy ministerialne, punktacja)
    # wołają z ``disable_fuzzy=True`` po ścisłe dopasowanie, a to zapytanie
    # robi pełny skan tabeli źródeł (``unaccent`` nie ma indeksu).
    pola = ("nazwa",) if disable_skrot else ("nazwa", "skrot")
    bez_diakrytykow = (
        None if disable_fuzzy else zrodla_po_tytule_bez_diakrytykow(elem, pola)
    )
    if bez_diakrytykow is not None:
        kandydaci = list(bez_diakrytykow[:2])
        if len(kandydaci) == 1:
            return kandydaci[0]
        if kandydaci:
            return _disambiguate_by_issn(bez_diakrytykow, issn, e_issn)

    if not disable_fuzzy and elem.endswith("."):
        fuzzy = Q(nazwa__istartswith=elem[:-1]) | Q(skrot__istartswith=elem[:-1])
        try:
            return Zrodlo.objects.get(fuzzy)
        except Zrodlo.DoesNotExist:
            pass
        except Zrodlo.MultipleObjectsReturned:
            return _disambiguate_by_issn(Zrodlo.objects.filter(fuzzy), issn, e_issn)

    return None


def matchuj_zrodlo(
    s: str | None,
    issn: str | None = None,
    e_issn: str | None = None,
    mnisw_id: int | str | None = None,
    alt_nazwa=None,
    disable_fuzzy=False,
    disable_skrot=False,
    disable_title_matching=False,
) -> None | Zrodlo:
    if s is None or str(s) == "":
        return None

    result = _try_match_zrodlo_by_issn(issn, e_issn)
    if result:
        return result

    result = _try_match_zrodlo_by_mnisw_id(mnisw_id)
    if result:
        return result

    if not disable_title_matching:
        for elem in (s, alt_nazwa):
            if elem is None:
                continue
            result = _try_match_zrodlo_by_title_single(
                elem, disable_skrot, disable_fuzzy, issn=issn, e_issn=e_issn
            )
            if result:
                return result

    return None


#: Ile najwyżej kandydatów zwraca ``kandydaci_zrodla`` — lista jest pokazywana
#: człowiekowi do wyboru, więc dłuższa i tak nie ma sensu.
MAX_KANDYDATOW_ZRODLA = 20


def kandydaci_zrodla(
    tytul: str | None, issn: str | None = None, e_issn: str | None = None
) -> tuple[list[Zrodlo], str]:
    """WSZYSTKIE źródła pasujące do wiersza importu — do pokazania człowiekowi.

    ``matchuj_zrodlo`` przy kilku trafieniach zwraca ``None`` (nie zgaduje),
    przez co wołający nie odróżni „brak źródła” od „kilka pasujących”. Ta
    funkcja używa tych samych reguł, ale oddaje listę kandydatów:

    1. ISSN/e-ISSN (jak ``_try_match_zrodlo_by_issn``): jednoznaczne trafienie
       → jedno źródło; kilka źródeł z tym numerem → wszystkie.
    2. Dopiero gdy numer nic nie dał — tytuł, dokładnie (bez dopasowania
       rozmytego), ignorując wielkość liter i znaki diakrytyczne, w polach
       ``nazwa`` i ``skrot`` (``zrodla_po_tytule_bez_diakrytykow``).

    Zwraca ``(kandydaci, sposob)``; ``sposob`` to ``"ISSN"``, ``"tytuł"``
    albo ``""`` przy braku trafień.
    """
    jedyne = _try_match_zrodlo_by_issn(issn, e_issn)
    if jedyne is not None:
        return [jedyne], "ISSN"

    numery = [
        n for n in (_normalize_issn_value(issn), _normalize_issn_value(e_issn)) if n
    ]
    if numery:
        po_issn = _kandydaci_po_issn(numery)[:MAX_KANDYDATOW_ZRODLA]
        if po_issn:
            return po_issn, "ISSN"

    if not tytul or not isinstance(tytul, str):
        return [], ""
    po_tytule = zrodla_po_tytule_bez_diakrytykow(
        normalize_tytul_zrodla(tytul), ("nazwa", "skrot")
    )
    if po_tytule is None:
        return [], ""
    kandydaci = list(po_tytule.order_by("nazwa", "pk")[:MAX_KANDYDATOW_ZRODLA])
    return kandydaci, "tytuł" if kandydaci else ""
