"""Matchowanie autorów po identyfikatorach (BPP id / ORCID / PBN UID /
system kadrowy / PBN id) oraz po imieniu+nazwisku z kontekstem
(jednostka, tytuł).
"""

from dataclasses import dataclass

from django.contrib.postgres.lookups import Unaccent
from django.db.models import Q
from django.db.models.functions import Lower

from bpp.models import Autor, Autor_Jednostka, Jednostka, Tytul
from import_common.normalization import (
    polish_english_first_name_variants,
    remove_polish_diacritics,
)


@dataclass(frozen=True)
class KandydatAutora:
    """Pojedynczy kandydat zwracany przez ``znajdz_kandydatow_autora``.

    ``pewnosc`` to wartość 0.0–1.0 odpowiadająca strategii, którą udało
    się dopasować autora; ``powod`` to human-readable etykieta strategii
    (do wyświetlenia w UI). ``publikacji`` to liczba publikacji autora
    (sygnał jakości używany do rankingu przy równej pewności).
    """

    autor: Autor
    pewnosc: float
    powod: str
    publikacji: int


# Etykiety strategii i ich pewnosc — punkt prawdy do wszystkich callsite'ów.
POWOD_IEXACT = "iexact"
POWOD_IEXACT_PIERWSZE_IMIE = "iexact_pierwsze_imie"
POWOD_POLISH_ENGLISH = "polish_english"

PEWNOSC_IEXACT = 1.0
PEWNOSC_IEXACT_PIERWSZE_IMIE = 0.95
PEWNOSC_POLISH_ENGLISH = 0.85


def _try_get_autor_by_bpp_id(bpp_id: int | None) -> Autor | None:
    """Próbuje pobrać autora po bpp_id."""
    if bpp_id is None:
        return None
    try:
        return Autor.objects.get(pk=bpp_id)
    except Autor.DoesNotExist:
        return None


def _try_get_autor_by_orcid(orcid: str | None) -> Autor | None:
    """Próbuje pobrać autora po ORCID."""
    if not orcid:
        return None
    try:
        return Autor.objects.get(orcid__iexact=orcid.strip())
    except Autor.DoesNotExist:
        return None


def _try_get_autor_by_pbn_uid_id(pbn_uid_id: str | None) -> Autor | None:
    """Próbuje pobrać autora po pbn_uid_id."""
    if pbn_uid_id is None or pbn_uid_id.strip() == "":
        return None
    return Autor.objects.filter(pbn_uid_id=pbn_uid_id).first()


def _try_get_autor_by_system_kadrowy_id(system_kadrowy_id) -> Autor | None:
    """Próbuje pobrać autora po system_kadrowy_id."""
    if system_kadrowy_id is None:
        return None
    try:
        return Autor.objects.get(system_kadrowy_id=int(system_kadrowy_id))
    except (TypeError, ValueError, Autor.DoesNotExist):
        return None


def _try_get_autor_by_pbn_id(pbn_id) -> Autor | None:
    """Próbuje pobrać autora po pbn_id."""
    if pbn_id is None:
        return None
    if isinstance(pbn_id, str):
        pbn_id = pbn_id.strip()
    try:
        return Autor.objects.get(pbn_id=int(pbn_id))
    except (TypeError, ValueError, Autor.DoesNotExist):
        return None


def _try_match_autor_by_direct_ids(
    bpp_id: int | None,
    orcid: str | None,
    pbn_uid_id: str | None,
    system_kadrowy_id: int | None,
    pbn_id: int | None,
) -> Autor | None:
    """Próbuje dopasować autora po różnych identyfikatorach."""
    return (
        _try_get_autor_by_bpp_id(bpp_id)
        or _try_get_autor_by_orcid(orcid)
        or _try_get_autor_by_pbn_uid_id(pbn_uid_id)
        or _try_get_autor_by_system_kadrowy_id(system_kadrowy_id)
        or _try_get_autor_by_pbn_id(pbn_id)
    )


def _build_autor_name_query(nazwisko: str, imiona: str) -> Q:
    """Buduje podstawowe zapytanie Q dla nazwiska i imion."""
    return Q(
        Q(nazwisko__iexact=nazwisko) | Q(poprzednie_nazwiska__icontains=nazwisko),
        imiona__iexact=imiona,
    )


def _try_match_autor_by_name(
    imiona: str,
    nazwisko: str,
    jednostka: Jednostka | None,
    tytul_str: str | None,
) -> Autor | None:
    """Próbuje dopasować autora po imieniu i nazwisku."""
    imiona = (imiona or "").strip()
    nazwisko = (nazwisko or "").strip()

    queries = [
        _build_autor_name_query(nazwisko, imiona),
        _build_autor_name_query(nazwisko, imiona.split(" ")[0]),
    ]

    if tytul_str:
        queries.extend([q & Q(tytul__skrot=tytul_str) for q in queries[:]])

    for qry in queries:
        try:
            return Autor.objects.get(qry)
        except (Autor.DoesNotExist, Autor.MultipleObjectsReturned):
            pass

        if jednostka is not None:
            try:
                return Autor.objects.get(qry & Q(aktualna_jednostka=jednostka))
            except (Autor.MultipleObjectsReturned, Autor.DoesNotExist):
                pass

    return None


def _try_match_autor_in_jednostka(
    imiona: str,
    nazwisko: str,
    jednostka: Jednostka,
    tytul_str: str | None,
) -> Autor | None:
    """Szuka autora wśród przypisanych do jednostki."""
    imiona = (imiona or "").strip()
    nazwisko = (nazwisko or "").strip()

    base_query = Q(
        Q(autor__nazwisko__iexact=nazwisko)
        | Q(autor__poprzednie_nazwiska__icontains=nazwisko),
        autor__imiona__iexact=imiona,
    )
    queries = [base_query]
    if tytul_str:
        queries.append(base_query & Q(autor__tytul__skrot=tytul_str))

    for qry in queries:
        try:
            return jednostka.autor_jednostka_set.get(qry).autor
        except (Autor_Jednostka.MultipleObjectsReturned, Autor_Jednostka.DoesNotExist):
            pass

    return None


def _try_match_autor_by_polish_english_variants(
    imiona: str,
    nazwisko: str,
    jednostka: Jednostka | None,
) -> Autor | None:
    """Fallback dla wariantów pisowni polsko-angielskiej.

    Stosuje ``unaccent`` na nazwisku po stronie bazy (Marańda↔Maranda)
    oraz regułę ``v↔w`` na pierwszym imieniu (Eva↔Ewa, Viktor↔Wiktor).
    Wymaga ``CREATE EXTENSION unaccent`` (instalowane przez migrację
    0001_fulltext).

    Zwraca autora tylko gdy istnieje **dokładnie jeden** kandydat —
    przy ambiguity decyzja należy do użytkownika.
    """
    imiona = (imiona or "").strip()
    nazwisko = (nazwisko or "").strip()
    if not imiona or not nazwisko:
        return None

    first = imiona.split()[0]
    variants_norm = {v.lower() for v in polish_english_first_name_variants(first)}
    if not variants_norm:
        return None

    nazwisko_norm = remove_polish_diacritics(nazwisko).lower()

    imie_q = Q()
    for v in variants_norm:
        imie_q |= Q(im_n=v) | Q(im_n__startswith=v + " ")

    qs = (
        Autor.objects.annotate(
            naz_n=Lower(Unaccent("nazwisko")),
            im_n=Lower(Unaccent("imiona")),
        )
        .filter(naz_n=nazwisko_norm)
        .filter(imie_q)
    )

    if jednostka is not None:
        qs_j = qs.filter(aktualna_jednostka=jednostka)
        results = list(qs_j[:2])
        if len(results) == 1:
            return results[0]

    results = list(qs[:2])
    if len(results) == 1:
        return results[0]
    return None


def _try_match_autor_with_orcid_or_tytul(imiona: str, nazwisko: str) -> Autor | None:
    """Ostatnia próba - szuka autora z ORCIDem lub tytułem."""
    imiona = (imiona or "").strip()
    nazwisko = (nazwisko or "").strip()

    base_query = _build_autor_name_query(nazwisko, imiona)

    # Próba z ORCIDem i tytułem
    try:
        return Autor.objects.get(
            base_query, orcid__isnull=False, tytul_id__isnull=False
        )
    except (Autor.DoesNotExist, Autor.MultipleObjectsReturned):
        pass

    # Próba tylko z tytułem
    try:
        return Autor.objects.get(base_query, tytul_id__isnull=False)
    except (Autor.DoesNotExist, Autor.MultipleObjectsReturned):
        pass

    return None


def _strategia_iexact_pelne(imiona: str, nazwisko: str) -> dict[int, tuple[float, str]]:
    """Pełne ``imiona`` + nazwisko/poprzednie_nazwiska (iexact)."""
    qs = Autor.objects.filter(
        Q(nazwisko__iexact=nazwisko) | Q(poprzednie_nazwiska__icontains=nazwisko),
        imiona__iexact=imiona,
    )
    return {
        pk: (PEWNOSC_IEXACT, POWOD_IEXACT) for pk in qs.values_list("pk", flat=True)
    }


def _strategia_iexact_pierwsze_imie(
    imiona: str, nazwisko: str
) -> dict[int, tuple[float, str]]:
    """Tylko pierwsze imię (iexact) — gdy w bazie jest "Jan Adam" a w
    danych "Jan" (lub odwrotnie)."""
    parts = imiona.split()
    if not parts:
        return {}
    pierwsze = parts[0]
    # Dwa kierunki: w danych może być więcej imion niż w bazie (qs), albo
    # w bazie więcej niż w danych (qs2). Dedup z _strategia_iexact_pelne
    # wybierze potem pewnosc=1.0 dla pełnego matchu.
    qs = Autor.objects.filter(
        Q(nazwisko__iexact=nazwisko) | Q(poprzednie_nazwiska__icontains=nazwisko),
        imiona__iexact=pierwsze,
    )
    qs2 = Autor.objects.filter(
        Q(nazwisko__iexact=nazwisko) | Q(poprzednie_nazwiska__icontains=nazwisko),
        imiona__istartswith=pierwsze + " ",
    )
    pks = set(qs.values_list("pk", flat=True)) | set(qs2.values_list("pk", flat=True))
    return {
        pk: (PEWNOSC_IEXACT_PIERWSZE_IMIE, POWOD_IEXACT_PIERWSZE_IMIE) for pk in pks
    }


def _strategia_polish_english(
    imiona: str, nazwisko: str
) -> dict[int, tuple[float, str]]:
    """PL↔EN: Unaccent(nazwisko) + warianty v↔w / klastry na pierwszym imieniu."""
    pierwsze = imiona.split()[0] if imiona.split() else ""
    if not pierwsze:
        return {}
    variants_norm = {v.lower() for v in polish_english_first_name_variants(pierwsze)}
    if not variants_norm:
        return {}

    nazwisko_norm = remove_polish_diacritics(nazwisko).lower()

    imie_q = Q()
    for v in variants_norm:
        imie_q |= Q(im_n=v) | Q(im_n__startswith=v + " ")

    qs = (
        Autor.objects.annotate(
            naz_n=Lower(Unaccent("nazwisko")),
            im_n=Lower(Unaccent("imiona")),
        )
        .filter(naz_n=nazwisko_norm)
        .filter(imie_q)
    )
    return {
        pk: (PEWNOSC_POLISH_ENGLISH, POWOD_POLISH_ENGLISH)
        for pk in qs.values_list("pk", flat=True)
    }


def _publikacji_counts_bulk(pks: list[int]) -> dict[int, int]:
    """Zwraca {autor_pk: liczba_publikacji} dla podanych pk autorów.

    Trzy osobne agregacje (po jednej na typ publikacji) zamiast jednej
    z wieloma JOINami — przy próbie zliczania ``Count("ciagle") +
    Count("zwarte") + Count("patent")`` w jednym querysecie Django robi
    cross-JOIN i kardynalności się mnożą. Tu mamy 3 round-tripy na cały
    request, niezależnie od liczby kandydatów.
    """
    from collections import defaultdict

    from django.db.models import Count

    totals: dict[int, int] = defaultdict(int)
    for relation in (
        "wydawnictwo_ciagle_autor",
        "wydawnictwo_zwarte_autor",
        "patent_autor",
    ):
        rows = (
            Autor.objects.filter(pk__in=pks)
            .annotate(_n=Count(relation))
            .values_list("pk", "_n")
        )
        for pk, n in rows:
            totals[pk] += n
    return dict(totals)


def znajdz_kandydatow_autora(
    imiona: str | None,
    nazwisko: str | None,
    *,
    max_wyniki: int = 10,
) -> list[KandydatAutora]:
    """Zwraca posortowaną listę kandydatów (najlepszy pierwszy).

    Stosuje strategie kolejno; każda kolejna ma niższą pewnosc. Brak
    strategii "tylko nazwisko" — żeby nie zwracać listy 100 Kowalskich
    z różnymi imionami. Musi się zgadzać przynajmniej imię w jakiejś
    formie (iexact, pierwsze imię iexact, albo wariant PL↔EN).

    Strategie:

    - 1.00 — exact iexact pełne imiona + nazwisko
    - 0.95 — exact iexact pierwsze imię + nazwisko
    - 0.85 — PL↔EN: warianty v↔w + klastry imion + Unaccent nazwiska

    Autor wpadający w kilka strategii zwracany jest **raz**, z najwyższą
    pewnością. Sortowanie DESC po: (pewnosc, ma ORCID, ma tytuł, liczba
    publikacji, pk) — ORCID/tytuł/publikacje to sygnały jakości używane
    przy równej pewności; pk jako stabilny tiebreaker.

    Discovery jest świadomie niezależne od kontekstu (jednostka/tytuł
    autora) — te sygnały służą jako tie-breakery w ``matchuj_autora``,
    nie jako twarde filtry. Inaczej wycielibyśmy autorów, którzy
    nie mają ``aktualna_jednostka`` ustawionej.
    """
    imiona = (imiona or "").strip()
    nazwisko = (nazwisko or "").strip()
    if not imiona or not nazwisko:
        return []

    # Akumulator {pk: (pewnosc, powod)} — wyższa pewność wygrywa przy
    # nakładaniu się strategii (dedup po pk).
    scores: dict[int, tuple[float, str]] = {}
    for strategia in (
        _strategia_iexact_pelne(imiona, nazwisko),
        _strategia_iexact_pierwsze_imie(imiona, nazwisko),
        _strategia_polish_english(imiona, nazwisko),
    ):
        for pk, (pewnosc, powod) in strategia.items():
            existing = scores.get(pk)
            if existing is None or pewnosc > existing[0]:
                scores[pk] = (pewnosc, powod)

    if not scores:
        return []

    pks = list(scores.keys())
    publikacji_counts = _publikacji_counts_bulk(pks)
    autorzy_by_pk = Autor.objects.filter(pk__in=pks).in_bulk()

    kandydaci = [
        KandydatAutora(
            autor=autor,
            pewnosc=scores[pk][0],
            powod=scores[pk][1],
            publikacji=publikacji_counts.get(pk, 0),
        )
        for pk, autor in autorzy_by_pk.items()
    ]
    kandydaci.sort(
        key=lambda k: (
            k.pewnosc,
            1 if k.autor.orcid else 0,
            1 if k.autor.tytul_id else 0,
            k.publikacji,
            k.autor.pk,
        ),
        reverse=True,
    )
    return kandydaci[:max_wyniki]


def _disambiguate_kandydatow(
    kandydaci: list[KandydatAutora],
    jednostka: Jednostka | None,
    tytul_str: str | None,
) -> Autor | None:
    """Spróbuj rozstrzygnąć ambiguity gdy ≥2 kandydatów ma identyczną pewność.

    Stosuje tie-breakery kolejno (każdy wymaga **dokładnie jednego**
    wyniku, żeby uznać za jednoznaczny):

    1. ``aktualna_jednostka == jednostka`` — autor pracuje w żądanej
       jednostce.
    2. ``tytul.skrot == tytul_str`` — autor ma żądany tytuł.

    Pominięcie obu sygnałów oznacza prawdziwą ambiguity — caller dostaje
    None i fallback do historycznej jednostki / ORCID-tytułu.
    """
    top_pewnosc = kandydaci[0].pewnosc
    top = [k for k in kandydaci if k.pewnosc == top_pewnosc]

    if jednostka is not None:
        w_jednostce = [k for k in top if k.autor.aktualna_jednostka_id == jednostka.pk]
        if len(w_jednostce) == 1:
            return w_jednostce[0].autor

    if tytul_str:
        z_tytulem = [
            k for k in top if k.autor.tytul_id and k.autor.tytul.skrot == tytul_str
        ]
        if len(z_tytulem) == 1:
            return z_tytulem[0].autor

    return None


def matchuj_autora(
    imiona: str | None,
    nazwisko: str | None,
    jednostka: Jednostka | None = None,
    bpp_id: int | None = None,
    pbn_uid_id: str | None = None,
    system_kadrowy_id: int | None = None,
    pbn_id: int | None = None,
    orcid: str | None = None,
    tytul_str: Tytul | None = None,
):
    """Zwraca jednoznacznego autora albo None.

    Thin wrapper nad ``znajdz_kandydatow_autora`` z disambiguatorami
    dla ambiguity (jednostka, tytuł) oraz fallbackami do historycznej
    jednostki i wyboru po ORCID/tytule.
    """
    # 1. Po identyfikatorach — najpewniejsza ścieżka
    result = _try_match_autor_by_direct_ids(
        bpp_id, orcid, pbn_uid_id, system_kadrowy_id, pbn_id
    )
    if result:
        return result

    # 2. Discovery
    kandydaci = znajdz_kandydatow_autora(imiona, nazwisko, max_wyniki=10)
    if len(kandydaci) == 1:
        return kandydaci[0].autor
    if len(kandydaci) >= 2:
        # Najlepszy z wyższą pewnością niż reszta wygrywa bez disambiguacji
        if kandydaci[0].pewnosc > kandydaci[1].pewnosc:
            return kandydaci[0].autor
        # Inaczej spróbuj kontekstem (jednostka/tytuł)
        result = _disambiguate_kandydatow(kandydaci, jednostka, tytul_str)
        if result:
            return result

    # 3. Historyczna jednostka — autor był kiedyś w tej jednostce
    if jednostka:
        result = _try_match_autor_in_jednostka(imiona, nazwisko, jednostka, tytul_str)
        if result:
            return result

    # 4. Tie-breaker dla ambiguity bez jednostki: preferuj autora z ORCID/tytułem
    return _try_match_autor_with_orcid_or_tytul(imiona, nazwisko)
