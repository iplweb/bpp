"""Porównanie listy autorów ze źródła z autorami rekordu (tylko podgląd).

Dopasowanie po kolei: identyfikator osoby w PBN → ORCID → nazwisko i imię.
Sprzeczne identyfikatory (różne ORCID albo identyfikatory PBN) i dwa różne
pełne imiona wykluczają dopasowanie po nazwisku; gdy kilku autorów rekordu
pasuje równie dobrze, osoba jest „do sprawdzenia”, nie „zgodna”. Autorów nie przenosimy: dodanie autora wymaga wskazania
jednostki i dyscypliny, a to robi się w formularzu rekordu.
"""

from dataclasses import dataclass, field

from import_common.normalization import (
    normalize_nazwisko_do_porownania,
    normalize_orcid,
    polish_english_first_name_variants,
)

ZGODNY = "zgodny"
INNA_KOLEJNOSC = "inna kolejność"
BRAK_W_BPP = "brak w BPP"
TYLKO_W_BPP = "tylko w BPP"
#: Kilku autorów rekordu pasuje równie dobrze (to samo nazwisko i inicjał).
DO_SPRAWDZENIA = "do sprawdzenia"

#: Powyżej tylu osób pokazujemy same różnice (prace z setkami autorów).
LIMIT_PELNEJ_LISTY = 60


@dataclass
class WierszAutora:
    status: str
    zrodlo: str = ""
    nr_zrodlo: int | None = None
    bpp: str = ""
    nr_bpp: int | None = None
    sposob: str = ""
    #: Osoba ze źródła (słownik dostawcy) — dla brakujących w BPP.
    osoba: dict | None = field(default=None, repr=False)


@dataclass
class PorownanieAutorow:
    wiersze: list[WierszAutora] = field(default_factory=list)
    w_zrodle: int = 0
    w_bpp: int = 0

    def _ile(self, status):
        return sum(1 for w in self.wiersze if w.status == status)

    @property
    def osoby_brakujace(self):
        """Osoby ze źródła, których nie ma w rekordzie (w kolejności źródła)."""
        return [w.osoba for w in self.wiersze if w.status == BRAK_W_BPP]

    @property
    def brakujacy(self):
        return self._ile(BRAK_W_BPP)

    @property
    def nadmiarowi(self):
        return self._ile(TYLKO_W_BPP)

    @property
    def inna_kolejnosc(self):
        return self._ile(INNA_KOLEJNOSC)

    @property
    def do_sprawdzenia(self):
        return self._ile(DO_SPRAWDZENIA)

    @property
    def zgodni(self):
        return self._ile(ZGODNY)

    @property
    def sa_roznice(self):
        return bool(
            self.brakujacy
            or self.nadmiarowi
            or self.inna_kolejnosc
            or self.do_sprawdzenia
        )

    @property
    def widoczne(self):
        """Wiersze do tabeli: przy długich listach — same różnice."""
        if len(self.wiersze) <= LIMIT_PELNEJ_LISTY:
            return self.wiersze
        return [w for w in self.wiersze if w.status != ZGODNY]

    @property
    def ukryci_zgodni(self):
        return len(self.wiersze) - len(self.widoczne)


def _nazwisko(wartosc):
    return normalize_nazwisko_do_porownania(wartosc or "")


def _pierwsze_imie(imiona):
    """Pierwsze imię małymi literami, bez kropki („J.” → „j”)."""
    czesci = normalize_nazwisko_do_porownania(imiona or "").replace(".", " ").split()
    return czesci[0] if czesci else ""


def _orcid(wartosc):
    return (normalize_orcid(wartosc or "") or "").upper()


PELNE_IMIE = "nazwisko i imię"
INICJAL = "nazwisko i inicjał imienia"


def _zgodnosc_imion(a, b):
    """Jak pasują do siebie dwa pierwsze imiona: ``PELNE_IMIE`` (to samo
    imię, także w pisowni polskiej / angielskiej), ``INICJAL`` (co najmniej
    jedna strona podaje sam inicjał albo nic i inicjały się nie wykluczają)
    albo ``None`` — dwa RÓŻNE pełne imiona (Jan ≠ Jerzy)."""
    a, b = _pierwsze_imie(a), _pierwsze_imie(b)
    if len(a) > 1 and len(b) > 1:
        warianty_a = {_pierwsze_imie(x) for x in polish_english_first_name_variants(a)}
        warianty_b = {_pierwsze_imie(x) for x in polish_english_first_name_variants(b)}
        return PELNE_IMIE if (warianty_a | {a}) & (warianty_b | {b}) else None
    if not a or not b or a[0] == b[0]:
        return INICJAL
    return None


class _AutorzyRekordu:
    """Autorzy rekordu z indeksami do dopasowania; każdy użyty raz."""

    def __init__(self, powiazania):
        self.powiazania = list(powiazania)
        self.wolne = set(range(len(self.powiazania)))
        self.po_pbn, self.po_orcid, self.po_nazwisku = {}, {}, {}
        for nr, wa in enumerate(self.powiazania):
            autor = wa.autor
            if autor.pbn_uid_id:
                self.po_pbn.setdefault(str(autor.pbn_uid_id), []).append(nr)
            if _orcid(autor.orcid):
                self.po_orcid.setdefault(_orcid(autor.orcid), []).append(nr)
            if _nazwisko(autor.nazwisko):
                self.po_nazwisku.setdefault(_nazwisko(autor.nazwisko), []).append(nr)

    def _wez(self, indeks, klucz):
        for nr in indeks.get(klucz, ()):
            if nr in self.wolne:
                self.wolne.discard(nr)
                return nr
        return None

    def _sprzeczne_identyfikatory(self, osoba, autor):
        """Obie strony mają ORCID albo identyfikator PBN i są one RÓŻNE —
        to na pewno dwie osoby, choćby nazwisko i inicjał się zgadzały."""
        orcid = _orcid(osoba.get("orcid"))
        if orcid and _orcid(autor.orcid) and orcid != _orcid(autor.orcid):
            return True
        pbn_uid = str(osoba.get("pbn_uid") or "")
        return bool(pbn_uid and autor.pbn_uid_id and pbn_uid != str(autor.pbn_uid_id))

    def _po_nazwisku(self, osoba):
        """(numer, sposób, czy do sprawdzenia) dla dopasowania po nazwisku.

        Kandydaci to wolni autorzy rekordu o tym nazwisku, bez sprzecznych
        identyfikatorów i bez innego pełnego imienia. Jeden kandydat —
        dopasowanie; kilku równie dobrych — „do sprawdzenia” (redaktor
        rozstrzyga, nie algorytm)."""
        kandydaci = {PELNE_IMIE: [], INICJAL: []}
        for nr in self.po_nazwisku.get(_nazwisko(osoba.get("family")), ()):
            autor = self.powiazania[nr].autor
            if nr not in self.wolne or self._sprzeczne_identyfikatory(osoba, autor):
                continue
            zgodnosc = _zgodnosc_imion(osoba.get("given"), autor.imiona)
            if zgodnosc:
                kandydaci[zgodnosc].append(nr)
        for sposob in (PELNE_IMIE, INICJAL):
            if kandydaci[sposob]:
                nr = kandydaci[sposob][0]
                self.wolne.discard(nr)
                return nr, sposob, len(kandydaci[sposob]) > 1
        return None, "", False

    def dopasuj(self, osoba):
        """(numer autora rekordu, sposób dopasowania, czy do sprawdzenia)
        albo (None, "", False)."""
        for indeks, klucz, sposob in (
            (self.po_pbn, osoba.get("pbn_uid") or None, "identyfikator PBN"),
            (self.po_orcid, _orcid(osoba.get("orcid")) or None, "ORCID"),
        ):
            if klucz is None:
                continue
            nr = self._wez(indeks, klucz)
            if nr is not None:
                return nr, sposob, False
        return self._po_nazwisku(osoba)


def _nazwa_osoby(osoba):
    return f"{osoba.get('family') or ''} {osoba.get('given') or ''}".strip() or "(?)"


def porownaj_autorow(rekord, osoby) -> PorownanieAutorow:
    """Porównaj ``osoby`` ze źródła (słowniki ``family``/``given``/``orcid``/
    ``pbn_uid``, w kolejności ze źródła) z autorami ``rekord``."""
    powiazania = rekord.autorzy_set.select_related("autor").order_by("kolejnosc", "pk")
    autorzy = _AutorzyRekordu(powiazania)
    wynik = PorownanieAutorow(w_zrodle=len(osoby), w_bpp=len(autorzy.powiazania))

    najdalszy = -1
    for nr_zrodlo, osoba in enumerate(osoby, start=1):
        nr, sposob, do_sprawdzenia = autorzy.dopasuj(osoba)
        wiersz = WierszAutora(
            status=BRAK_W_BPP,
            zrodlo=_nazwa_osoby(osoba),
            nr_zrodlo=nr_zrodlo,
            osoba=osoba,
        )
        if nr is not None:
            wiersz.status = ZGODNY if nr > najdalszy else INNA_KOLEJNOSC
            if do_sprawdzenia:
                wiersz.status = DO_SPRAWDZENIA
            najdalszy = max(najdalszy, nr)
            wiersz.osoba = None
            wiersz.bpp = str(autorzy.powiazania[nr].autor)
            wiersz.nr_bpp = nr + 1
            wiersz.sposob = sposob
        wynik.wiersze.append(wiersz)

    for nr in sorted(autorzy.wolne):
        wynik.wiersze.append(
            WierszAutora(
                status=TYLKO_W_BPP,
                bpp=str(autorzy.powiazania[nr].autor),
                nr_bpp=nr + 1,
            )
        )
    return wynik
