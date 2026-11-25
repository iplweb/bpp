"""Porównanie listy autorów ze źródła z autorami rekordu (tylko podgląd).

Dopasowanie po kolei: identyfikator osoby w PBN → ORCID → nazwisko i pierwsza
litera imienia. Autorów nie przenosimy: dodanie autora wymaga wskazania
jednostki i dyscypliny, a to robi się w formularzu rekordu.
"""

from dataclasses import dataclass, field

from import_common.normalization import (
    normalize_nazwisko_do_porownania,
    normalize_orcid,
)

ZGODNY = "zgodny"
INNA_KOLEJNOSC = "inna kolejność"
BRAK_W_BPP = "brak w BPP"
TYLKO_W_BPP = "tylko w BPP"

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
    def zgodni(self):
        return self._ile(ZGODNY)

    @property
    def sa_roznice(self):
        return bool(self.brakujacy or self.nadmiarowi or self.inna_kolejnosc)

    @property
    def widoczne(self):
        """Wiersze do tabeli: przy długich listach — same różnice."""
        if len(self.wiersze) <= LIMIT_PELNEJ_LISTY:
            return self.wiersze
        return [w for w in self.wiersze if w.status != ZGODNY]

    @property
    def ukryci_zgodni(self):
        return len(self.wiersze) - len(self.widoczne)


def _klucz_nazwiska(nazwisko, imiona):
    nazwisko = normalize_nazwisko_do_porownania(nazwisko or "")
    if not nazwisko:
        return None
    imie = normalize_nazwisko_do_porownania(imiona or "")
    return (nazwisko, imie[:1])


def _orcid(wartosc):
    return (normalize_orcid(wartosc or "") or "").upper()


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
            klucz = _klucz_nazwiska(autor.nazwisko, autor.imiona)
            if klucz:
                self.po_nazwisku.setdefault(klucz, []).append(nr)

    def _wez(self, indeks, klucz):
        for nr in indeks.get(klucz, ()):
            if nr in self.wolne:
                self.wolne.discard(nr)
                return nr
        return None

    def dopasuj(self, osoba):
        """(numer autora rekordu, sposób dopasowania) albo (None, "")."""
        proby = (
            (self.po_pbn, osoba.get("pbn_uid") or None, "identyfikator PBN"),
            (self.po_orcid, _orcid(osoba.get("orcid")) or None, "ORCID"),
            (
                self.po_nazwisku,
                _klucz_nazwiska(osoba.get("family"), osoba.get("given")),
                "nazwisko i imię",
            ),
        )
        for indeks, klucz, sposob in proby:
            if klucz is None:
                continue
            nr = self._wez(indeks, klucz)
            if nr is not None:
                return nr, sposob
        return None, ""


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
        nr, sposob = autorzy.dopasuj(osoba)
        wiersz = WierszAutora(
            status=BRAK_W_BPP,
            zrodlo=_nazwa_osoby(osoba),
            nr_zrodlo=nr_zrodlo,
            osoba=osoba,
        )
        if nr is not None:
            wiersz.status = ZGODNY if nr > najdalszy else INNA_KOLEJNOSC
            najdalszy = max(najdalszy, nr)
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
