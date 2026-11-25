"""Dwuliterowe kody języków (ISO 639-1) dla słownika języków (FD#513).

CrossRef opisuje język publikacji kodem dwuliterowym („uk”, „cs”). Języki
zakładane w BPP z PBN mają skrót i kod trzyliterowy (ISO 639-2: „ukr”,
„ces”), więc bez uzupełnienia nie dają się dopasować. ``zaproponuj_kody``
wylicza, co wpisać w „Skrót nazwy języka wg API CrossRef” i „Kod języka wg
BCP 47”; korzysta z niej akcja „Uzupełnij kody CrossRef z PBN” w adminie
języków. Migracja ``0533`` ma zamrożoną kopię tej samej logiki (migracje
nie importują kodu aplikacji).

Źródło kodu: język PBN powiązany z językiem BPP (klucz „639-1”), zapasowo
polska nazwa języka (``KOD_WG_NAZWY`` — tylko nazwy jednoznaczne).
"""

import re
from collections import defaultdict
from dataclasses import dataclass

KOD_WG_NAZWY = {
    "angielski": "en",
    "polski": "pl",
    "niemiecki": "de",
    "francuski": "fr",
    "hiszpański": "es",
    "włoski": "it",
    "rosyjski": "ru",
    "ukraiński": "uk",
    "białoruski": "be",
    "czeski": "cs",
    "słowacki": "sk",
    "słoweński": "sl",
    "chorwacki": "hr",
    "serbski": "sr",
    "bośniacki": "bs",
    "macedoński": "mk",
    "bułgarski": "bg",
    "litewski": "lt",
    "łotewski": "lv",
    "estoński": "et",
    "węgierski": "hu",
    "rumuński": "ro",
    "portugalski": "pt",
    "kataloński": "ca",
    "niderlandzki": "nl",
    "holenderski": "nl",
    "duński": "da",
    "szwedzki": "sv",
    "norweski": "no",
    "fiński": "fi",
    "islandzki": "is",
    "grecki": "el",
    "nowogrecki": "el",
    "turecki": "tr",
    "łaciński": "la",
    "łacina": "la",
    "hebrajski": "he",
    "arabski": "ar",
    "perski": "fa",
    "chiński": "zh",
    "japoński": "ja",
    "koreański": "ko",
    "wietnamski": "vi",
    "hindi": "hi",
    "esperanto": "eo",
    "albański": "sq",
    "gruziński": "ka",
    "ormiański": "hy",
    "kazachski": "kk",
    "irlandzki": "ga",
    "walijski": "cy",
    "baskijski": "eu",
    "galicyjski": "gl",
    "maltański": "mt",
    "afrikaans": "af",
    "indonezyjski": "id",
    "malajski": "ms",
    "tajski": "th",
    "mongolski": "mn",
    "azerski": "az",
    "uzbecki": "uz",
    "jidysz": "yi",
}

# Kod języka w rozumieniu CrossRef: podstawowy podtag (2–3 małe litery),
# opcjonalnie z dalszymi podtagami BCP 47 (np. „en-GB”, „zh-Hant”).
WZORZEC_KODU = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


def kod_dla_nazwy(nazwa):
    """Kod ISO 639-1 dla polskiej nazwy języka albo ``None``.

    Toleruje wielkość liter, białe znaki i dopisek „język” („Język
    angielski”, „angielski język”)."""
    if not nazwa:
        return None
    slowa = [s for s in str(nazwa).strip().lower().split() if s != "język"]
    return KOD_WG_NAZWY.get(" ".join(slowa))


def podtag_podstawowy(kod):
    """„en-GB” → „en”; pusty/niepoprawny → ``""``."""
    return str(kod or "").split("-")[0].strip().lower()


_KOD_639_1 = re.compile(r"^[a-z]{2}$")


@dataclass
class PropozycjaKodow:
    """Co zmienić w jednym języku. ``None`` w polu = bez zmiany."""

    pk: int
    kod: str
    kod_bcp47: str | None = None
    skrot_crossref: str | None = None
    #: Skrótu CrossRef nie da się nadać: ten sam kod pasuje do kilku
    #: języków i żaden nie jest oczywistym wyborem (albo kod jest zajęty).
    kolizja: bool = False

    @property
    def zmienia(self):
        return self.kod_bcp47 is not None or self.skrot_crossref is not None


def _kod_639_1(wiersz):
    pbn = wiersz.get("pbn_jezyk")
    kod = pbn.get("639-1") if isinstance(pbn, dict) else None
    if isinstance(kod, str) and _KOD_639_1.match(kod.strip().lower()):
        return kod.strip().lower()
    return kod_dla_nazwy(wiersz.get("nazwa"))


def _kod_bcp47_z_automatu(wiersz):
    """Czy „Kod BCP 47” jest pusty albo trzyliterowy i taki sam jak skrót
    języka / kod PBN — czyli wpisał go automat, nie redaktor."""
    obecny = (wiersz.get("kod_bcp47") or "").strip().lower()
    if not obecny:
        return True
    if len(obecny) != 3:
        return False
    pbn = wiersz.get("pbn_jezyk")
    automatyczne = {
        (wiersz.get("skrot") or "").strip().lower(),
        (wiersz.get("pbn_kod") or "").strip().lower(),
        (pbn.get("639-2") or "").strip().lower() if isinstance(pbn, dict) else "",
    }
    return obecny in automatyczne


def _jedyny_faworyt(kandydaci, uzywane_pk):
    """Jeden język z grupy o tym samym kodzie albo ``None`` (nie zgadujemy).

    Pierwszeństwo: używany w publikacjach, potem widoczny."""
    if len(kandydaci) == 1:
        return kandydaci[0]
    uzywane = [w for w in kandydaci if w["pk"] in uzywane_pk]
    if len(uzywane) == 1:
        return uzywane[0]
    widoczne = [w for w in (uzywane or kandydaci) if w.get("widoczny")]
    if len(widoczne) == 1:
        return widoczne[0]
    return None


def zaproponuj_kody(wiersze, uzywane_pk=frozenset()):
    """Propozycje kodów dla języków.

    ``wiersze`` — WSZYSTKIE języki słownika jako słowniki z kluczami ``pk``,
    ``nazwa``, ``skrot``, ``kod_bcp47``, ``skrot_crossref``, ``widoczny``,
    ``pbn_kod``, ``pbn_jezyk`` (JSON języka PBN albo ``None``).
    ``uzywane_pk`` — języki używane w publikacjach.

    Zasady:

    * „Kod BCP 47” jest podmieniany tylko, gdy wpisał go automat (pusty albo
      trzyliterowy i równy skrótowi / kodowi PBN);
    * „Skrót CrossRef” jest unikalny: wypełniamy tylko pusty; gdy ten sam kod
      pasuje do kilku języków, dostaje go jedyny używany w publikacjach,
      a w razie remisu jedyny widoczny — inaczej nikt (``kolizja``).

    Zwraca listę ``PropozycjaKodow`` — tylko dla języków, dla których znany
    jest kod dwuliterowy i jest coś do zmiany albo kolizja.
    """
    wiersze = list(wiersze)
    zajete = {
        (w.get("skrot_crossref") or "").strip().lower()
        for w in wiersze
        if (w.get("skrot_crossref") or "").strip()
    }
    kody = {w["pk"]: _kod_639_1(w) for w in wiersze}

    grupy = defaultdict(list)
    for w in wiersze:
        kod = kody[w["pk"]]
        if kod and not (w.get("skrot_crossref") or "").strip():
            grupy[kod].append(w)

    wyniki = []
    for w in wiersze:
        kod = kody[w["pk"]]
        if not kod:
            continue
        propozycja = PropozycjaKodow(pk=w["pk"], kod=kod)
        obecny_bcp = (w.get("kod_bcp47") or "").strip()
        if _kod_bcp47_z_automatu(w) and obecny_bcp != kod:
            propozycja.kod_bcp47 = kod
        if not (w.get("skrot_crossref") or "").strip():
            faworyt = None if kod in zajete else _jedyny_faworyt(grupy[kod], uzywane_pk)
            if faworyt is w:
                propozycja.skrot_crossref = kod
            elif kod not in zajete and faworyt is None:
                propozycja.kolizja = True
        if propozycja.zmienia or propozycja.kolizja:
            wyniki.append(propozycja)
    return wyniki
