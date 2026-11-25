"""Ustalanie odpowiednika autora BPP wśród osób z PBN (FD#510).

Wspólny rdzeń dla dwóch miejsc:

* importera publikacji — zanim utworzy NOWEGO autora, szuka dla niego osoby
  w lokalnej kopii danych PBN (``znajdz_osobe_pbn``),
* komendy ``dopasuj_autorow_do_pbn`` — dla autorów, którzy już istnieją
  i nie mają odpowiednika w PBN (``zbadaj_autorow``).

Zasada nadrzędna: odpowiednik ustawiamy wyłącznie wtedy, gdy wskazanie jest
jednoznaczne. Błędne powiązanie jest gorsze niż jego brak — oświadczenia
autora trafiłyby w PBN do innej osoby.

Świadomie NIE używamy tu ``matchuj_autora_po_stronie_pbn``: tamta funkcja
przy kilku osobach o tym samym imieniu i nazwisku wybiera „najlepszą” wg
punktacji i akceptuje pojedyncze trafienie po samym nazwisku w całej kopii
PBN. Do automatu, który ma działać bez nadzoru, to za mało.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from pbn_client.const import DELETED

from import_common.normalization import normalize_orcid
from pbn_api.models import OsobaZInstytucji, Publication, Scientist
from pbn_integrator.utils.scientists import _qry_po_orcid

JEDNOZNACZNE = "jednoznaczne"
NIEJEDNOZNACZNE = "niejednoznaczne"
BRAK = "brak"

ZRODLO_IDENTYFIKATOR = "identyfikator PBN"
ZRODLO_ORCID = "ORCID"
ZRODLO_NAZWISKO = "imię i nazwisko (osoba z instytucji)"
ZRODLO_PUBLIKACJE = "publikacje"

PEWNE = "pewne"
PRAWDOPODOBNE = "prawdopodobne"
SPRZECZNE = "sprzeczne"
MOZLIWY_DUPLIKAT = "możliwy duplikat autora"
BRAK_DOWODU = "brak"

#: Kolejność poziomów w raporcie — od tych, które wymagają decyzji.
KOLEJNOSC_POZIOMOW = [PEWNE, MOZLIWY_DUPLIKAT, SPRZECZNE, PRAWDOPODOBNE, BRAK_DOWODU]

_ROZDZIELACZ_NAZWISK = re.compile(r"[,;/]")
_BIALE = re.compile(r"\s+")


def _norm(tekst):
    """Sprowadź napis do postaci porównywalnej: bez wielkości liter,
    znaków diakrytycznych, kropek i nadmiarowych odstępów."""
    tekst = (tekst or "").replace("ł", "l").replace("Ł", "L")
    tekst = unicodedata.normalize("NFKD", tekst)
    tekst = "".join(z for z in tekst if not unicodedata.combining(z))
    tekst = tekst.replace(".", " ").replace("‐", "-").replace("–", "-")
    tekst = re.sub(r"\s*-\s*", "-", tekst)
    return _BIALE.sub(" ", tekst).strip().casefold()


def warianty_nazwiska(nazwisko, poprzednie_nazwiska=""):
    """Zbiór znormalizowanych wariantów nazwiska: pełne, każdy człon
    nazwiska dwuczłonowego oraz poprzednie nazwiska."""
    warianty = set()
    for kawalek in [nazwisko, *_ROZDZIELACZ_NAZWISK.split(poprzednie_nazwiska or "")]:
        pelne = _norm(kawalek)
        if not pelne:
            continue
        warianty.add(pelne)
        warianty.update(czlon for czlon in pelne.split("-") if len(czlon) > 1)
    return warianty


def imiona_zgodne(a, b, *, inicjal=False):
    """Czy dwa zapisy imion mogą oznaczać tę samą osobę.

    Zgodne są: identyczne zapisy albo to samo pierwsze imię („Jan Maria”
    i „Jan”). Z ``inicjal=True`` także inicjał pierwszego imienia („J.”
    i „Jan”) — używane tylko przy porównywaniu autorów JEDNEJ publikacji,
    gdzie lista kandydatów ma kilka–kilkanaście osób.
    """
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return False
    if a == b:
        return True
    pierwsze_a, pierwsze_b = a.split(" ")[0], b.split(" ")[0]
    if pierwsze_a == pierwsze_b:
        return True
    if inicjal and 1 in (len(pierwsze_a), len(pierwsze_b)):
        return pierwsze_a[0] == pierwsze_b[0]
    return False


class OsobyInstytucji:
    """Osoby z PBN zatrudnione w instytucji — do szukania po imieniu
    i nazwisku. Wczytywane raz (to kilka tysięcy wierszy), żeby dopasowanie
    wielu autorów nie odpytywało za każdym razem ogromnej tabeli osób.

    W instalacji z wieloma uczelniami lista jest zawężona do instytucji PBN
    danej uczelni; uczelnia bez odpowiednika w PBN nie ma wtedy żadnych osób
    (nie pożyczamy kadry innej uczelni).
    """

    def __init__(self, uczelnia=None):
        from bpp.models import Uczelnia

        self._po_nazwisku = defaultdict(set)
        self.identyfikatory = set()

        osoby = OsobaZInstytucji.objects.exclude(personId__status=DELETED)
        jedna_uczelnia = Uczelnia.objects.count() <= 1
        if uczelnia is not None and uczelnia.pbn_uid_id:
            osoby = osoby.filter(institutionId_id=uczelnia.pbn_uid_id)
        elif not jedna_uczelnia:
            osoby = osoby.none()

        for pk, imiona, nazwisko in osoby.values_list(
            "personId_id", "firstName", "lastName"
        ):
            self._dodaj(pk, imiona, nazwisko)

        if jedna_uczelnia:
            # Osoby pobrane z API instytucji, którym nie dało się zapisać
            # wiersza zatrudnienia (np. PBN nie podał identyfikatora POL-on).
            for pk, imiona, nazwisko in (
                Scientist.objects.filter(from_institution_api=True)
                .exclude(status=DELETED)
                .values_list("pk", "name", "lastName")
            ):
                self._dodaj(pk, imiona, nazwisko)

    def _dodaj(self, pk, imiona, nazwisko):
        self.identyfikatory.add(pk)
        for wariant in warianty_nazwiska(nazwisko):
            self._po_nazwisku[wariant].add((pk, imiona or ""))

    def szukaj(self, imiona, nazwisko, poprzednie_nazwiska=""):
        """Identyfikatory osób pasujących po nazwisku (z wariantami)
        i imieniu."""
        znalezione = set()
        for wariant in warianty_nazwiska(nazwisko, poprzednie_nazwiska):
            for pk, imiona_osoby in self._po_nazwisku.get(wariant, ()):
                if imiona_zgodne(imiona, imiona_osoby):
                    znalezione.add(pk)
        return znalezione


@dataclass
class WynikSzukania:
    """Wynik szukania osoby PBN jednym źródłem dowodu."""

    status: str = BRAK
    scientist_id: str | None = None
    zrodlo: str = ""
    kandydaci: list = field(default_factory=list)

    @property
    def opis(self):
        if self.status == JEDNOZNACZNE:
            return f"{self.zrodlo}: {self.scientist_id}"
        if self.status == NIEJEDNOZNACZNE:
            return (
                f"{self.zrodlo}: pasuje kilka osób w PBN "
                f"({', '.join(sorted(self.kandydaci))})"
            )
        return ""


def _jeden_albo_kilku(zrodlo, identyfikatory):
    identyfikatory = sorted(set(identyfikatory))
    if not identyfikatory:
        return WynikSzukania()
    if len(identyfikatory) == 1:
        return WynikSzukania(JEDNOZNACZNE, identyfikatory[0], zrodlo, identyfikatory)
    return WynikSzukania(NIEJEDNOZNACZNE, None, zrodlo, identyfikatory)


def szukaj_po_orcid(orcid, osoby_instytucji=None):
    """Osoba PBN o podanym ORCID. Gdy ORCID nosi kilka osób (zdublowane
    profile w PBN), rozstrzyga tylko jedyna osoba z instytucji."""
    orcid = normalize_orcid(orcid)
    if not orcid:
        return WynikSzukania()
    identyfikatory = list(
        Scientist.objects.filter(_qry_po_orcid(orcid))
        .exclude(status=DELETED)
        .values_list("pk", flat=True)
    )
    if len(identyfikatory) > 1 and osoby_instytucji is not None:
        z_instytucji = [
            pk for pk in identyfikatory if pk in osoby_instytucji.identyfikatory
        ]
        if len(z_instytucji) == 1:
            return WynikSzukania(JEDNOZNACZNE, z_instytucji[0], ZRODLO_ORCID)
    return _jeden_albo_kilku(ZRODLO_ORCID, identyfikatory)


def szukaj_po_nazwisku(imiona, nazwisko, poprzednie_nazwiska, osoby_instytucji):
    """Osoba z instytucji o podanym imieniu i nazwisku."""
    if osoby_instytucji is None:
        return WynikSzukania()
    return _jeden_albo_kilku(
        ZRODLO_NAZWISKO,
        osoby_instytucji.szukaj(imiona, nazwisko, poprzednie_nazwiska),
    )


def znajdz_osobe_pbn(
    *,
    pbn_uid="",
    orcid="",
    imiona="",
    nazwisko="",
    poprzednie_nazwiska="",
    osoby_instytucji=None,
):
    """Znajdź osobę PBN dla danych autora — pierwszym źródłem, które coś
    wskazuje: identyfikator osoby z danych → ORCID → imię i nazwisko wśród
    osób z instytucji.

    Niejednoznaczność mocniejszego źródła NIE jest rozstrzygana słabszym:
    kilka osób z tym samym ORCID to sygnał bałaganu, którego nie wolno
    przykrywać zgadywaniem po nazwisku.
    """
    pbn_uid = (pbn_uid or "").strip()
    if pbn_uid:
        if Scientist.objects.filter(pk=pbn_uid).exclude(status=DELETED).exists():
            return WynikSzukania(JEDNOZNACZNE, pbn_uid, ZRODLO_IDENTYFIKATOR, [pbn_uid])

    wynik = szukaj_po_orcid(orcid, osoby_instytucji)
    if wynik.status != BRAK:
        return wynik

    return szukaj_po_nazwisku(imiona, nazwisko, poprzednie_nazwiska, osoby_instytucji)


# --- Dowód „po publikacjach” ------------------------------------------------


def _osoby_publikacji(publikacja):
    """Lista ``(identyfikator, imiona, nazwisko, pozycja)`` osób publikacji
    PBN — autorów i redaktorów. Uwzględnia tylko zapisy, w których PBN
    podaje identyfikator osoby (słownik kluczowany identyfikatorem)."""
    obiekt = (publikacja.current_version or {}).get("object") or {}
    kolejnosci = obiekt.get("orderList") or {}
    osoby = []
    for klucz, rola in (("authors", "AUTHOR"), ("editors", "EDITOR")):
        slownik = obiekt.get(klucz)
        if not isinstance(slownik, dict):
            continue
        kolejnosc = kolejnosci.get(rola) or []
        for identyfikator, dane in slownik.items():
            if not isinstance(dane, dict):
                continue
            pozycja = (
                kolejnosc.index(identyfikator) if identyfikator in kolejnosc else None
            )
            osoby.append(
                (
                    identyfikator,
                    dane.get("name") or dane.get("firstName") or "",
                    dane.get("lastName") or "",
                    pozycja,
                )
            )
    return osoby


def _osoba_w_publikacji(autor, powiazanie, osoby):
    """Która osoba z publikacji PBN odpowiada autorowi BPP w tej pracy.

    Po nazwisku (z wariantami i zapisem z rekordu) i imieniu; gdy pasuje
    kilka osób (np. rodzeństwo o tym samym inicjale), rozstrzyga pozycja
    na liście autorów. Zwraca identyfikator albo ``None``.
    """
    nazwiska = warianty_nazwiska(autor.nazwisko, autor.poprzednie_nazwiska)
    zapisany = _norm(powiazanie["zapisany_jako"])
    pasujace = []
    for identyfikator, imiona, nazwisko, pozycja in osoby:
        nazwiska_osoby = warianty_nazwiska(nazwisko)
        if not nazwiska_osoby:
            continue
        zgodne_nazwisko = bool(nazwiska & nazwiska_osoby) or any(
            wariant in zapisany.replace("-", " ").split(" ")
            for wariant in nazwiska_osoby
        )
        if zgodne_nazwisko and imiona_zgodne(autor.imiona, imiona, inicjal=True):
            pasujace.append((identyfikator, pozycja))
    if len(pasujace) == 1:
        return pasujace[0][0]
    na_pozycji = [
        identyfikator
        for identyfikator, pozycja in pasujace
        if pozycja is not None and pozycja == powiazanie["kolejnosc"]
    ]
    if len(na_pozycji) == 1:
        return na_pozycji[0]
    return None


def _powiazania_z_publikacjami_pbn(autor_ids):
    """Powiązania autor–rekord dla prac, które mają odpowiednik w PBN."""
    from bpp.models import Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor

    for model in (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor):
        yield from (
            model.objects.filter(
                autor_id__in=autor_ids, rekord__pbn_uid_id__isnull=False
            )
            .values(
                "autor_id",
                "kolejnosc",
                "zapisany_jako",
                "rekord__pbn_uid_id",
            )
            .iterator()
        )


def dowody_z_publikacji(autorzy):
    """Dla każdego autora: ``Counter`` {identyfikator osoby PBN: liczba
    prac, w których lokalna kopia publikacji PBN wskazuje tę osobę}."""
    po_id = {autor.pk: autor for autor in autorzy}
    powiazania = list(_powiazania_z_publikacjami_pbn(list(po_id)))
    publikacje = {}
    identyfikatory = sorted({p["rekord__pbn_uid_id"] for p in powiazania})
    for start in range(0, len(identyfikatory), 500):
        for publikacja in Publication.objects.filter(
            pk__in=identyfikatory[start : start + 500]
        ):
            publikacje[publikacja.pk] = _osoby_publikacji(publikacja)

    glosy = defaultdict(Counter)
    for powiazanie in powiazania:
        osoby = publikacje.get(powiazanie["rekord__pbn_uid_id"])
        if not osoby:
            continue
        identyfikator = _osoba_w_publikacji(
            po_id[powiazanie["autor_id"]], powiazanie, osoby
        )
        if identyfikator:
            glosy[powiazanie["autor_id"]][identyfikator] += 1
    return glosy


# --- Ocena łączna -----------------------------------------------------------


@dataclass
class Propozycja:
    """Wynik badania jednego autora BPP."""

    autor: object
    poziom: str = BRAK_DOWODU
    scientist_id: str | None = None
    zrodla: list = field(default_factory=list)
    liczba_prac: int = 0
    uwagi: list = field(default_factory=list)
    zapisano: bool = False

    @property
    def do_zapisu(self):
        return self.poziom == PEWNE and self.scientist_id is not None


def _ocen_autora(autor, osoby_instytucji, glosy, pewne_od_prac):
    propozycja = Propozycja(autor=autor)
    wskazania = {}  # źródło -> identyfikator osoby

    po_orcid = szukaj_po_orcid(autor.orcid, osoby_instytucji)
    po_nazwisku = szukaj_po_nazwisku(
        autor.imiona, autor.nazwisko, autor.poprzednie_nazwiska, osoby_instytucji
    )
    for wynik in (po_orcid, po_nazwisku):
        if wynik.status == JEDNOZNACZNE:
            wskazania[wynik.zrodlo] = wynik.scientist_id
            propozycja.zrodla.append(wynik.opis)
        elif wynik.status == NIEJEDNOZNACZNE:
            propozycja.uwagi.append(wynik.opis)

    if len(glosy) == 1:
        ((identyfikator, liczba),) = glosy.items()
        wskazania[ZRODLO_PUBLIKACJE] = identyfikator
        propozycja.liczba_prac = liczba
        propozycja.zrodla.append(
            f"{ZRODLO_PUBLIKACJE}: {identyfikator} (zgodnie w {liczba} pracach)"
        )
    elif len(glosy) > 1:
        propozycja.poziom = SPRZECZNE
        propozycja.uwagi.append(
            "publikacje wskazują różne osoby PBN: "
            + ", ".join(f"{pk} ({n} prac)" for pk, n in glosy.most_common())
        )

    osoby = set(wskazania.values())
    if propozycja.poziom == SPRZECZNE or len(osoby) > 1:
        propozycja.poziom = SPRZECZNE
        if len(osoby) > 1:
            propozycja.uwagi.append("źródła wskazują różne osoby PBN")
        return propozycja
    if not osoby:
        return propozycja

    propozycja.scientist_id = osoby.pop()
    pewne = (
        ZRODLO_ORCID in wskazania
        or (ZRODLO_NAZWISKO in wskazania and ZRODLO_PUBLIKACJE in wskazania)
        or (
            pewne_od_prac
            and ZRODLO_PUBLIKACJE in wskazania
            and propozycja.liczba_prac >= pewne_od_prac
        )
    )
    if po_orcid.status == NIEJEDNOZNACZNE:
        # ORCID autora nosi w PBN kilka osób — dopóki ktoś tego nie
        # rozstrzygnie, żadne inne źródło nie daje pewności.
        pewne = False
    propozycja.poziom = PEWNE if pewne else PRAWDOPODOBNE
    return propozycja


def _odrzuc_sprzeczne_orcid(propozycje, orcidy):
    """Autor i wskazana osoba PBN mają RÓŻNE, niepuste ORCID — to nie może
    być ta sama osoba, choćby nazwisko i publikacje się zgadzały. Nigdy
    automatycznie."""
    for propozycja in propozycje:
        orcid_autora = normalize_orcid(propozycja.autor.orcid)
        orcid_osoby = orcidy.get(propozycja.scientist_id)
        if orcid_autora and orcid_osoby and orcid_autora != orcid_osoby:
            propozycja.poziom = SPRZECZNE
            propozycja.uwagi.append(
                f"ORCID autora ({orcid_autora}) różni się od ORCID wskazanej "
                f"osoby PBN ({orcid_osoby})"
            )


def _zastosuj_bezpieczniki(propozycje):
    """Zdejmij „pewne” tam, gdzie zapis byłby błędem: osoba PBN nieznana
    lokalnie albo skasowana, już przypięta do innego autora BPP, albo
    proponowana kilku autorom naraz."""
    from bpp.models import Autor

    proponowane = [p.scientist_id for p in propozycje if p.scientist_id]
    osoby = list(
        Scientist.objects.filter(pk__in=proponowane).values_list(
            "pk", "status", "orcid"
        )
    )
    stany = {pk: status for pk, status, _ in osoby}
    _odrzuc_sprzeczne_orcid(
        propozycje, {pk: normalize_orcid(orcid) for pk, _, orcid in osoby}
    )
    przypieci = defaultdict(list)
    for pk, pbn_uid, nazwisko, imiona in Autor.objects.filter(
        pbn_uid_id__in=proponowane
    ).values_list("pk", "pbn_uid_id", "nazwisko", "imiona"):
        przypieci[pbn_uid].append(f"{nazwisko} {imiona} (ID {pk})")
    ile_razy = Counter(proponowane)

    for propozycja in propozycje:
        pk = propozycja.scientist_id
        if pk is None:
            continue
        if pk in przypieci:
            propozycja.poziom = MOZLIWY_DUPLIKAT
            propozycja.uwagi.append(
                "osoba PBN jest już przypisana do autora: " + "; ".join(przypieci[pk])
            )
        elif ile_razy[pk] > 1:
            inni = [
                f"{p.autor.nazwisko} {p.autor.imiona} (ID {p.autor.pk})"
                for p in propozycje
                if p.scientist_id == pk and p is not propozycja
            ]
            propozycja.poziom = MOZLIWY_DUPLIKAT
            propozycja.uwagi.append(
                "tę samą osobę PBN wskazują też autorzy bez odpowiednika: "
                + "; ".join(inni)
            )
        elif pk not in stany:
            if propozycja.poziom == PEWNE:
                propozycja.poziom = PRAWDOPODOBNE
            propozycja.uwagi.append(
                "osoby nie ma w lokalnej kopii danych PBN — pobierz dane osób "
                "z PBN i uruchom dopasowanie ponownie"
            )
        elif stany[pk] == DELETED:
            if propozycja.poziom == PEWNE:
                propozycja.poziom = PRAWDOPODOBNE
            propozycja.uwagi.append("osoba jest w PBN oznaczona jako usunięta")


def zbadaj_autorow(autorzy, *, uczelnia=None, pewne_od_prac=0, osoby_instytucji=None):
    """Zbadaj autorów bez odpowiednika w PBN. Niczego nie zapisuje.

    Zwraca listę ``Propozycja`` w kolejności autorów. ``osoby_instytucji``
    — już wczytana lista osób z instytucji (gdy wołający też jej używa).
    """
    autorzy = list(autorzy)
    if osoby_instytucji is None:
        osoby_instytucji = OsobyInstytucji(uczelnia)
    glosy = dowody_z_publikacji(autorzy)
    propozycje = [
        _ocen_autora(autor, osoby_instytucji, glosy.get(autor.pk, {}), pewne_od_prac)
        for autor in autorzy
    ]
    _zastosuj_bezpieczniki(propozycje)
    return propozycje


def zapisz_propozycje(propozycje, uzytkownik=None):
    """Zapisz wskazania „pewne”. Każdy autor w osobnej transakcji,
    z ponownym sprawdzeniem pod blokadą — PBN UID, który pojawił się
    w międzyczasie, nigdy nie jest nadpisywany. Historia zmian trafia na
    konto ``uzytkownik`` (``None`` = konto systemowe)."""
    from django.db import transaction

    from bpp.models import Autor
    from bpp.wersjonowanie import jako_uzytkownik
    from pbn_integrator.utils.scientists import _powiaz_autora_z_pbn

    with jako_uzytkownik(uzytkownik):
        for propozycja in propozycje:
            if not propozycja.do_zapisu:
                continue
            with transaction.atomic():
                autor = Autor.objects.select_for_update().get(pk=propozycja.autor.pk)
                if autor.pbn_uid_id is not None:
                    propozycja.uwagi.append(
                        "nie zapisano: autor dostał PBN UID w międzyczasie"
                    )
                    continue
                # Blokada wiersza OSOBY PBN: dwa równoległe zlecenia nie
                # przypiszą tej samej osoby dwóm autorom (``Autor.pbn_uid``
                # nie jest unikalny, a blokada autora chroni tylko jego).
                list(
                    Scientist.objects.select_for_update()
                    .filter(pk=propozycja.scientist_id)
                    .values_list("pk", flat=True)
                )
                if (
                    Autor.objects.filter(pbn_uid_id=propozycja.scientist_id)
                    .exclude(pk=autor.pk)
                    .exists()
                ):
                    propozycja.uwagi.append(
                        "nie zapisano: osoba PBN została w międzyczasie "
                        "przypisana do innego autora"
                    )
                    continue
                _powiaz_autora_z_pbn(
                    autor,
                    propozycja.scientist_id,
                    "dopasowanie autorów bez odpowiednika w PBN: "
                    + "; ".join(propozycja.zrodla),
                )
                propozycja.zapisano = True
