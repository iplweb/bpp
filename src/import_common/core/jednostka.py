"""Matchowanie jednostek (komórki organizacyjne uczelni)."""

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q
from django.db.models.functions import Greatest

from bpp.models import Jednostka

from ..normalization import normalize_nazwa_jednostki

# Próg podobieństwa trigramowego, powyżej którego niedopasowaną dokładnie nazwę
# jednostki uznajemy za „bardzo zbliżoną" i wybieramy automatycznie (status
# ``zgadywanie``, widoczny dla użytkownika). Strojony w jednym miejscu.
PROG_ZGADYWANIA_JEDNOSTKI = 0.7

# Statusy klasyfikacji jednostki. Wartości są CELOWO identyczne z
# ``import_pracownikow.pewnosc.STATUS_*`` (wspólne słownictwo), ale definiujemy je
# lokalnie: ``import_common`` to warstwa NIŻSZA i nie może importować w górę do
# ``import_pracownikow`` (cykl importów).
STATUS_JEDNOSTKA_TWARDY = "twardy"
STATUS_JEDNOSTKA_ZGADYWANIE = "zgadywanie"
STATUS_JEDNOSTKA_BRAK = "brak"


def wytnij_skrot(jednostka):
    if jednostka.find("(") >= 0 and jednostka.find(")") >= 0:
        jednostka, skrot = jednostka.split("(", 2)
        jednostka = jednostka.strip()
        skrot = skrot[:-1].strip()
        return jednostka, skrot

    return jednostka, None


def _wydzial_filtr(wydzial):
    """``Q`` zawężające jednostki do wydziału podanego NAZWĄ (import legacy).

    Faza B (#438): „wydział" jednostki to zdenormalizowany korzeń
    (``jednostka.wydzial``), a tożsamość dawnego wydziału niesie
    ``root.legacy_wydzial_id``. Dopasowanie po ``wydzial__nazwa`` jest zawodne:
    promowany 1-jednostkowy wydział (0457) ma root == realna jednostka (jej
    własna nazwa ≠ nazwa wydziału), a syntetyczne lustro może mieć suffix
    ``[W<id>]`` na kolizji (F6). Rozwiązujemy więc nazwę → ``Wydzial`` → korzeń
    po ``legacy_wydzial_id``. Fallback na nazwę korzenia, gdy nie ma już wiersza
    ``Wydzial`` o tej nazwie (zachowanie sprzed fixu)."""
    from .tytul_funkcja import matchuj_wydzial

    w = matchuj_wydzial(wydzial)
    if w is not None:
        # Jednostki POD korzeniem (denorm wydzial → root) ORAZ sam KORZEŃ:
        # promowana jednostka-root ma denorm ``wydzial=None``, więc pierwsza
        # gałąź by ją wykluczyła — trzeba dołączyć root po legacy_wydzial_id.
        return Q(wydzial__legacy_wydzial_id=w.id) | Q(
            parent__isnull=True, legacy_wydzial_id=w.id
        )
    return Q(wydzial__nazwa__iexact=wydzial)


def matchuj_jednostke(nazwa, wydzial=None):
    if nazwa is None:
        return

    nazwa = normalize_nazwa_jednostki(nazwa)
    skrot = nazwa

    if "(" in nazwa and ")" in nazwa:
        nazwa_bez_nawiasow, skrot = wytnij_skrot(nazwa)
        try:
            return Jednostka.objects.get(skrot=skrot)
        except Jednostka.DoesNotExist:
            pass

    try:
        return Jednostka.objects.get(Q(nazwa__iexact=nazwa) | Q(skrot__iexact=nazwa))
    except Jednostka.DoesNotExist:
        if nazwa.endswith("."):
            nazwa = nazwa[:-1].strip()

        try:
            return Jednostka.objects.get(
                Q(nazwa__istartswith=nazwa) | Q(skrot__istartswith=nazwa)
            )
        except Jednostka.MultipleObjectsReturned as e:
            if wydzial is None:
                raise e

        return Jednostka.objects.get(
            Q(nazwa__istartswith=nazwa) | Q(skrot__istartswith=nazwa),
            _wydzial_filtr(wydzial),
        )

    except Jednostka.MultipleObjectsReturned as e:
        if wydzial is None:
            raise e

        return Jednostka.objects.get(
            Q(nazwa__iexact=nazwa) | Q(skrot__iexact=nazwa),
            _wydzial_filtr(wydzial),
        )


def _pula_afiliacyjna():
    """Queryset jednostek dopuszczalnych jako AUTO-dopasowanie (``zgadywanie``):
    tylko przyjmujące afiliacje i widoczne. Odzwierciedla warunki
    ``Jednostka.przyjmuje_afiliacje()`` — wyklucza jednostki obce
    (``skupia_pracownikow=False``), węzły-lustra „Wydział" (``jest_lustrem`` /
    ``rodzaj.autor_moze_afiliowac=False``) i jednostki ukryte. Dopasowanie
    DOKŁADNE (``matchuj_jednostke``) tej puli NIE używa — jeśli plik wprost
    nazywa jednostkę obcą, honorujemy to."""
    return (
        Jednostka.objects.filter(widoczna=True, skupia_pracownikow=True)
        .filter(Q(rodzaj__isnull=True) | Q(rodzaj__autor_moze_afiliowac=True))
        .exclude(jest_lustrem=True)
    )


def sklasyfikuj_jednostke(nazwa, wydzial=None, *, prog=PROG_ZGADYWANIA_JEDNOSTKI):
    """Klasyfikuje nazwę jednostki z pliku BEZ rzucania wyjątków.

    Zwraca ``(jednostka|None, status, similarity|None)``:
    - dokładne dopasowanie (``matchuj_jednostke``) → ``(j, "twardy", None)``;
    - brak/remis, ale najbliższa trigramowo ≥ ``prog`` (z puli afiliacyjnej) →
      ``(best, "zgadywanie", sim)`` — auto-wybór do weryfikacji;
    - w przeciwnym razie (w tym pusta nazwa, remis prefiksowy, brak podobnej) →
      ``(None, "brak", None)``.

    ``matchuj_jednostke`` rzuca ``DoesNotExist``/``MultipleObjectsReturned`` —
    oba łapiemy i spadamy do trigramu, więc funkcja nigdy nie wywali analizy.
    """
    if not nazwa:
        return None, STATUS_JEDNOSTKA_BRAK, None
    nazwa_norm = normalize_nazwa_jednostki(nazwa)
    if not nazwa_norm:
        return None, STATUS_JEDNOSTKA_BRAK, None

    try:
        j = matchuj_jednostke(nazwa, wydzial=wydzial)
        if j is not None:
            return j, STATUS_JEDNOSTKA_TWARDY, None
    except (Jednostka.DoesNotExist, Jednostka.MultipleObjectsReturned):
        pass

    best = (
        _pula_afiliacyjna()
        .annotate(
            sim=Greatest(
                TrigramSimilarity("nazwa", nazwa_norm),
                TrigramSimilarity("skrot", nazwa_norm),
            )
        )
        .order_by("-sim")
        .first()
    )
    if best is not None and best.sim is not None and best.sim >= prog:
        return best, STATUS_JEDNOSTKA_ZGADYWANIE, float(best.sim)
    return None, STATUS_JEDNOSTKA_BRAK, None


def zaproponuj_skrot(nazwa):
    """Czysta propozycja skrótu jednostki (BEZ sprawdzania unikalności — to robi
    ``unikalny_skrot`` w integracji). Akronim z pierwszych liter słów pisanych
    wielką literą (``Zakład Transfuzjologii`` → ``ZT``; spójniki małą literą
    pomijane). Gdy akronim < 2 znaki (jeden znaczący wyraz) — fallback: przycięta
    nazwa (≤128). Pusta nazwa → ``""``."""
    nazwa = (nazwa or "").strip()
    if not nazwa:
        return ""
    akronim = "".join(w[0].upper() for w in nazwa.split() if w[:1].isupper())
    if len(akronim) >= 2:
        return akronim[:128]
    return nazwa[:128]


def unikalny_skrot(base, zajete=None):
    """Zwraca skrót unikalny w bazie ORAZ względem ``zajete`` (skróty utworzone
    wcześniej w TYM SAMYM runie integracji — obrona przed kolizją in-batch, gdy
    dwie różne nazwy dają ten sam akronim). Kolizja → sufiks numeryczny
    (``ZT``, ``ZT2``, ``ZT3``…), całość przycięta do 128 znaków."""
    zajete = set(zajete or ())
    base = (base or "").strip()[:128] or "JED"

    def wolny(s):
        return s not in zajete and not Jednostka.objects.filter(skrot=s).exists()

    if wolny(base):
        return base
    i = 2
    while True:
        suf = str(i)
        kand = base[: 128 - len(suf)] + suf
        if wolny(kand):
            return kand
        i += 1
