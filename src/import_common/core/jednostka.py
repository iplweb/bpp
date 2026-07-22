"""Matchowanie jednostek (komórki organizacyjne uczelni)."""

import re

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q
from django.db.models.functions import Greatest
from unidecode import unidecode

from bpp.models import Jednostka

from ..normalization import ROMAN_NUMERAL_PATTERN, normalize_nazwa_jednostki

# Próg podobieństwa trigramowego, powyżej którego niedopasowaną dokładnie nazwę
# jednostki uznajemy za „bardzo zbliżoną" i wybieramy automatycznie (status
# ``zgadywanie``, widoczny dla użytkownika). Strojony w jednym miejscu.
PROG_ZGADYWANIA_JEDNOSTKI = 0.7

# Fallback „po skrócie" (prefiksowe wyrównanie słów) — stałe strojone tu.
# Kalibracja TRIGRAM_FLOOR na realnej jednostce: forma z Excela ma trigram 0.629,
# agresywny pełnowymiarowy skrót 0.417 (wchodzi), 3-słowny 0.186 (odrzuca guard).
TRIGRAM_FLOOR = 0.25  # dolny próg kandydatów do prefiltru top-K (perf + odsiew)
TOP_K = 50  # ilu kandydatów materializujemy do wyrównania w Pythonie
MIN_SLOW_PLIKU = 2  # <2 słowa → za dwuznaczne na dopasowanie po skrócie
MIN_POKRYCIE = 0.6  # min. udział słów pliku w słowach NAZWY kandydata

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
    """``Q`` zawężające jednostki do dawnego wydziału podanego NAZWĄ.

    Faza C (#438): „wydział" = jednostka top-level. ``matchuj_wydzial`` zwraca
    root-Jednostkę (po nazwie lub ``poprzednie_nazwy``); zawężamy do jednostek
    POD nim (denorm ``wydzial`` → root) ORAZ do SAMEGO roota (który ma denorm
    ``wydzial=None``, więc pierwsza gałąź by go wykluczyła). Fallback na nazwę
    korzenia, gdy żaden root nie pasuje."""
    from .tytul_funkcja import matchuj_wydzial

    root = matchuj_wydzial(wydzial)
    if root is not None:
        return Q(wydzial=root) | Q(pk=root.pk)
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
    (``skupia_pracownikow=False``), jednostki o rodzaju „Wydział"
    (``rodzaj.autor_moze_afiliowac=False`` — migracja 0464) i jednostki
    ukryte. Dopasowanie DOKŁADNE (``matchuj_jednostke``) tej puli NIE używa —
    jeśli plik wprost nazywa jednostkę obcą, honorujemy to.

    Faza C (#438): marker ``jest_lustrem`` zniknął wraz z węzłami-lustrami
    (migracja 0468); wykluczenie rootów-wydziałów niesie sam ``rodzaj``."""
    return Jednostka.objects.filter(widoczna=True, skupia_pracownikow=True).filter(
        Q(rodzaj__isnull=True) | Q(rodzaj__autor_moze_afiliowac=True)
    )


_NAWIAS = re.compile(r"\([^)]*\)")
# Obcięcie brzegowej interpunkcji PO unidecode+lower (token jest już ASCII);
# zbiór musi pokrywać transliteracje unidecode (np. '«'->'<<'), nie znaki źródłowe.
_OBETNIJ_BRZEGI = re.compile(r"^[^a-z0-9]+|[^a-z0-9]+$")
_NUMERAL = re.compile(rf"(?:{ROMAN_NUMERAL_PATTERN}|[0-9]+)", re.IGNORECASE)


def _slowa(s):
    """Nazwa/skrot → lista znormalizowanych słów.

    Usuwa nawiasowe grupy (np. „(WNoZ)" — skrót wydziału z displayu), łamie na
    słowa, każde: unidecode (zdejmuje ogonki ł→l, ż→z), lower, obcięcie brzegowej
    interpunkcji. Puste tokeny pominięte.
    """
    s = _NAWIAS.sub(" ", s or "")
    out = []
    for w in s.split():
        w = _OBETNIJ_BRZEGI.sub("", unidecode(w).lower())
        if w:
            out.append(w)
    return out


def _jest_numeralem(t):
    """True gdy token to numerał rzymski (I–XX) albo liczba arabska."""
    return _NUMERAL.fullmatch(t) is not None


def _para_prefiksowa(a, b):
    """True gdy a==b albo jedno jest prefiksem drugiego (dwukierunkowo).

    Tokeny ≤2 znaki (np. „i", „ii", „im") ORAZ numerały (rzymskie/cyfry) wymagają
    RÓWNOŚCI, nie prefiksu — inaczej „i" połknęłoby „intensywnej", a „VII"
    dopasowałoby się do „VIII" (numerowane kliniki). „III" (3 znaki) obsługuje
    reguła numerałów.
    """
    if len(a) <= 2 or len(b) <= 2:
        return a == b
    if _jest_numeralem(a) or _jest_numeralem(b):
        return a == b
    return a.startswith(b) or b.startswith(a)


def _liczba_dopasowanych(slowa_pliku, slowa_pola):
    """Greedy: słowa_pliku jako uporządkowany podciąg słów_pola z relacją
    prefiksową. Zwraca liczbę dopasowanych słów (== len(slowa_pliku)) albo None,
    gdy któreś słowo pliku nie znalazło pary. Greedy earliest-match jest
    dowodliwie optymalny dla testu istnienia podciągu."""
    i = 0
    for wp in slowa_pliku:
        while i < len(slowa_pola) and not _para_prefiksowa(wp, slowa_pola[i]):
            i += 1
        if i >= len(slowa_pola):
            return None
        i += 1
    return len(slowa_pliku)


def dopasuj_po_skrocie(
    nazwa, kandydaci, *, min_slow=MIN_SLOW_PLIKU, min_pokrycie=MIN_POKRYCIE
):
    """Najlepszy kandydat wg prefiksowego wyrównania słów, albo None.

    Wyrównanie próbowane na `nazwa` LUB `skrot` kandydata (istnienie podciągu),
    ale POKRYCIE liczone ZAWSZE względem słów `nazwa` (kanoniczna długość
    jednostki) — inaczej krótki `skrot` omijałby guard. `kandydaci` — instancje
    z adnotacją `.sim` (trigram). Ranking: (pokrycie, trigram); remis → wyższy
    trigram, przy równym pierwszy napotkany (wynik i tak jest `zgadywanie`,
    weryfikowany przez użytkownika).

    Znane ograniczenia v1: (1) reguła ≤2 znaki wyklucza 2-znakowe skróty słów
    (`Kl.`, `Ch.`); (2) all-or-nothing na słowach pliku — dopisek bez pary
    (`UM`, `CM`) daje None.
    """
    slowa_pliku = _slowa(nazwa)
    if len(slowa_pliku) < min_slow:
        return None
    najlepszy = None
    najlepszy_klucz = None
    for kand in kandydaci:
        slowa_nazwa = _slowa(kand.nazwa or "")
        if not slowa_nazwa:
            continue
        dopasowany = False
        for slowa_pola in (slowa_nazwa, _slowa(kand.skrot or "")):
            if slowa_pola and _liczba_dopasowanych(slowa_pliku, slowa_pola) is not None:
                dopasowany = True
                break
        if not dopasowany:
            continue
        pokrycie = len(slowa_pliku) / len(slowa_nazwa)
        if pokrycie < min_pokrycie:
            continue
        klucz = (pokrycie, float(kand.sim or 0.0))
        if najlepszy_klucz is None or klucz > najlepszy_klucz:
            najlepszy = kand
            najlepszy_klucz = klucz
    return najlepszy


def sklasyfikuj_jednostke(nazwa, wydzial=None, *, prog=PROG_ZGADYWANIA_JEDNOSTKI):
    """Klasyfikuje nazwę jednostki z pliku BEZ rzucania wyjątków.

    Zwraca ``(jednostka|None, status, similarity|None)``:
    - dokładne dopasowanie (``matchuj_jednostke``) → ``(j, "twardy", None)``;
    - najbliższa trigramowo ≥ ``prog`` (z puli afiliacyjnej) →
      ``(best, "zgadywanie", sim)``;
    - inaczej fallback ``dopasuj_po_skrocie`` (prefiksowe wyrównanie słów do
      nazwa/skrot, np. skrócone „Zakład Piel. Anestezjol.…") →
      ``(best, "zgadywanie", sim)`` — auto-wybór do weryfikacji;
    - w przeciwnym razie (pusta nazwa, brak podobnej) → ``(None, "brak", None)``.

    ``matchuj_jednostke`` rzuca ``DoesNotExist``/``MultipleObjectsReturned`` —
    oba łapiemy i spadamy do trigramu/fallbacku, więc funkcja nigdy nie wywali
    analizy.
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

    kandydaci = list(
        _pula_afiliacyjna()
        .annotate(
            sim=Greatest(
                TrigramSimilarity("nazwa", nazwa_norm),
                TrigramSimilarity("skrot", nazwa_norm),
            )
        )
        .filter(sim__gte=min(TRIGRAM_FLOOR, prog))
        .order_by("-sim")[:TOP_K]
    )

    if kandydaci and kandydaci[0].sim is not None and kandydaci[0].sim >= prog:
        best = kandydaci[0]
        return best, STATUS_JEDNOSTKA_ZGADYWANIE, float(best.sim)

    trafienie = dopasuj_po_skrocie(nazwa_norm, kandydaci)
    if trafienie is not None:
        return (
            trafienie,
            STATUS_JEDNOSTKA_ZGADYWANIE,
            float(trafienie.sim) if trafienie.sim is not None else None,
        )
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


def sklasyfikuj_jednostke_niepelna(
    fragment, wydzial=None, *, prog=PROG_ZGADYWANIA_JEDNOSTKI
):
    """Klasyfikuje NIEPEŁNĄ nazwę jednostki (fragment, np. „Medyczny").

    Najpierw próba dokładna/trigramowa (``sklasyfikuj_jednostke``, z ``prog``) —
    jeśli ``twardy``, zwróć od razu. Inaczej ``nazwa__icontains`` w SZEROKIM
    zbiorze widocznych jednostek (CELOWO NIE ``_pula_afiliacyjna`` — wyklucza ona
    lustra wydziałów, przez co „Wydział Medyczny" nigdy by się nie znalazł);
    trafienie ``icontains`` ma ZAWSZE status ``zgadywanie`` (fragment jest
    niejednoznaczny), nigdy ``twardy``. Gdy ``icontains`` jest PUSTE, NIE zwracamy
    twardego BRAK — oddajemy wynik ``sklasyfikuj_jednostke`` (trigramowe
    ``zgadywanie`` albo ``brak``), co realizuje spec §6.1 „0 trafień → trigram
    fallback". Ograniczenie: ``icontains`` nie łapie fleksji („Medyczny" ≠
    „Medycznego"). Gałąź ``icontains`` filtruje wyłącznie ``widoczna=True`` i
    IGNORUJE parametr ``wydzial`` (świadome uproszczenie — ujednoznacznienie po
    wydziale robi tylko gałąź exact/trigram ``sklasyfikuj_jednostke``).
    """
    if not fragment:
        return None, STATUS_JEDNOSTKA_BRAK, None
    frag = normalize_nazwa_jednostki(fragment)
    if not frag:
        return None, STATUS_JEDNOSTKA_BRAK, None

    j, status, sim = sklasyfikuj_jednostke(fragment, wydzial, prog=prog)
    if status == STATUS_JEDNOSTKA_TWARDY:
        return j, status, sim

    best = (
        Jednostka.objects.filter(widoczna=True, nazwa__icontains=frag)
        .annotate(sim=TrigramSimilarity("nazwa", frag))
        .order_by("-sim")
        .first()
    )
    if best is not None:
        return (
            best,
            STATUS_JEDNOSTKA_ZGADYWANIE,
            float(best.sim) if best.sim is not None else None,
        )
    # icontains puste → NIE twardy BRAK; oddaj trigramowy wynik sklasyfikuj_jednostke.
    return j, status, sim


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
