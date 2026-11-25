"""Odpowiednik PBN jednego autora — dla przycisku „Pobierz z PBN” w edycji
autora (FD#519).

Buduje na dopasowaniu z FD#510 (``dopasowanie_autorow``): te same źródła
dowodu i te same bezpieczniki. Dokłada dwie rzeczy potrzebne w formularzu:

* gdy autor ma ORCID, którego nie ma w lokalnej kopii danych PBN — pyta
  o niego serwer PBN i zapisuje znalezioną osobę w kopii,
* listę kandydatów do wyboru, gdy wskazanie nie jest jednoznaczne —
  osoby z profilu instytucji (API instytucjonalne PBN) na początku.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pbn_client.const import DELETED

from import_common.normalization import normalize_orcid
from pbn_api.exceptions import HttpException
from pbn_api.models import Scientist
from pbn_integrator.utils.dopasowanie_autorow import (
    BRAK,
    MOZLIWY_DUPLIKAT,
    PEWNE,
    OsobyInstytucji,
    dowody_z_publikacji,
    imiona_zgodne,
    szukaj_po_orcid,
    zbadaj_autorow,
)

#: Ilu najwyżej kandydatów pokazujemy redaktorowi.
MAX_KANDYDATOW = 20

#: Opis dowodu „ten sam ORCID” — taki kandydat jest zawsze na górze listy.
DOWOD_ORCID = "zgodny ORCID"

STATUS_PEWNY = "pewny"
STATUS_DO_WYBORU = "do_wyboru"
STATUS_BRAK = "brak"


@dataclass
class OdpowiednikAutora:
    status: str = STATUS_BRAK
    komunikat: str = ""
    #: Słowniki: id, etykieta, opis, oficjalny, zajety.
    kandydaci: list = field(default_factory=list)
    uwaga: str = ""
    propozycja: object = None


def pobierz_osobe_po_orcid(klient, orcid):
    """Zapytaj serwer PBN o osobę z danym ORCID i zapisz ją w lokalnej
    kopii. Zwraca ``Scientist`` albo ``None``, gdy PBN takiej osoby nie zna."""
    from pbn_integrator.utils import zapisz_mongodb

    try:
        osoby = klient.get_person_by_orcid(orcid)
    except HttpException as e:
        if e.status_code == 404:
            return None  # PBN nie zna tego ORCID — to nie błąd
        raise
    if not osoby:
        return None
    if isinstance(osoby, dict):
        osoby = [osoby]
    return zapisz_mongodb(osoby[0], Scientist)


def uzupelnij_kopie_po_orcid(autor, osoby_instytucji, serwer):
    """Jeśli ORCID autora nie występuje w lokalnej kopii danych PBN,
    spróbuj pobrać osobę z serwera PBN. ``serwer`` — ``SerwerPBN``."""
    orcid = normalize_orcid(autor.orcid)
    if not orcid or serwer is None:
        return None
    if szukaj_po_orcid(orcid, osoby_instytucji).status != BRAK:
        return None
    return serwer.wykonaj(lambda klient: pobierz_osobe_po_orcid(klient, orcid))


def _imienniki(autor):
    """Osoby z całej lokalnej kopii PBN o tym samym nazwisku i zgodnym
    imieniu — „pozostali” kandydaci, spoza profilu instytucji."""
    if not (autor.nazwisko and autor.imiona):
        return []
    return [
        pk
        for pk, imiona in Scientist.objects.filter(
            lastName__iexact=autor.nazwisko.strip()
        )
        .exclude(status=DELETED)
        .values_list("pk", "name")[:500]
        if imiona_zgodne(autor.imiona, imiona)
    ]


def _zajeci(identyfikatory, autor):
    """{PBN UID: opis autora BPP}, który już ma ten odpowiednik."""
    from bpp.models import Autor

    zajeci = {}
    qs = Autor.objects.filter(pbn_uid_id__in=identyfikatory)
    if autor.pk:
        qs = qs.exclude(pk=autor.pk)
    for pk, pbn_uid, nazwisko, imiona in qs.values_list(
        "pk", "pbn_uid_id", "nazwisko", "imiona"
    ):
        zajeci[pbn_uid] = f"{nazwisko} {imiona} (ID {pk})"
    return zajeci


def _powody(autor, propozycja, osoby_instytucji):
    """{PBN UID: lista opisów dowodu} dla wszystkich osób, które mogą być
    odpowiednikiem autora. Pusta lista = samo imię i nazwisko."""
    powody = {}

    def dodaj(pk, powod=""):
        powody.setdefault(pk, [])
        if powod and powod not in powody[pk]:
            powody[pk].append(powod)

    orcid = normalize_orcid(autor.orcid)
    if orcid:
        po_orcid = szukaj_po_orcid(orcid, osoby_instytucji)
        for pk in po_orcid.kandydaci or filter(None, [po_orcid.scientist_id]):
            dodaj(pk, DOWOD_ORCID)
    if autor.pk:
        glosy = dowody_z_publikacji([autor]).get(autor.pk, {})
        for pk, liczba in glosy.items():
            dodaj(pk, f"autor w {liczba} pracach powiązanych z PBN")
    po_nazwisku = set(_imienniki(autor))
    if autor.nazwisko and autor.imiona:
        po_nazwisku |= osoby_instytucji.szukaj(
            autor.imiona, autor.nazwisko, autor.poprzednie_nazwiska
        )
    for pk in sorted(po_nazwisku | set(filter(None, [propozycja.scientist_id]))):
        dodaj(pk)
    return powody


def _opis_kandydata(osoba, dowody, oficjalny):
    opisy = list(dowody)
    if oficjalny:
        opisy.append("osoba z profilu instytucji w PBN")
    if not opisy:
        opisy.append("zgodne imię i nazwisko")
    if osoba.orcid:
        opisy.append(f"ORCID w PBN: {osoba.orcid}")
    return "; ".join(opisy)


def _kandydaci(autor, propozycja, osoby_instytucji):
    """Lista kandydatów: na górze osoba ze zgodnym ORCID, potem osoby
    z profilu instytucji, potem reszta; w grupach najpierw ci, za którymi
    stoi mocniejszy dowód."""
    powody = _powody(autor, propozycja, osoby_instytucji)
    osoby = Scientist.objects.in_bulk(list(powody))
    zajeci = _zajeci(list(powody), autor)
    pewny = propozycja.scientist_id if propozycja.poziom == PEWNE else None

    kandydaci = []
    for pk, dowody in powody.items():
        osoba = osoby.get(pk)
        if osoba is None or osoba.status == DELETED:
            continue
        oficjalny = pk in osoby_instytucji.identyfikatory
        kandydaci.append(
            (
                (
                    pk != pewny,
                    DOWOD_ORCID not in dowody,
                    not oficjalny,
                    -len(dowody),
                    str(osoba),
                ),
                {
                    "id": pk,
                    "etykieta": str(osoba),
                    "opis": _opis_kandydata(osoba, dowody, oficjalny),
                    "oficjalny": oficjalny,
                    "zajety": zajeci.get(pk, ""),
                },
            )
        )
    kandydaci.sort(key=lambda para: para[0])
    return [kandydat for _, kandydat in kandydaci[:MAX_KANDYDATOW]]


def szukaj_odpowiednika_autora(autor, *, uczelnia=None, klient=None):
    """Ustal odpowiednik PBN autora. Niczego nie zapisuje w autorze.

    ``autor`` może być niezapisany (formularz dodawania) — wtedy nie ma
    dowodu z publikacji. ``klient`` — fabryka klienta PBN, ``SerwerPBN``
    albo ``None`` (tylko lokalna kopia).

    Wynik jest pewny (do wpisania bez pytania) dokładnie wtedy, gdy za
    pewny uznaje go dopasowanie z FD#510: jednoznaczny ORCID albo zgodne
    wskazanie z imienia i nazwiska ORAZ z publikacji. Wszystko inne to
    lista do wyboru.
    """
    from bpp.views.api.pbn_odpowiednik import SerwerPBN

    serwer = klient if isinstance(klient, SerwerPBN) else SerwerPBN(klient)
    osoby_instytucji = OsobyInstytucji(uczelnia)
    uzupelnij_kopie_po_orcid(autor, osoby_instytucji, serwer)

    propozycja = zbadaj_autorow(
        [autor], uczelnia=uczelnia, osoby_instytucji=osoby_instytucji
    )[0]
    kandydaci = _kandydaci(autor, propozycja, osoby_instytucji)
    wynik = OdpowiednikAutora(
        kandydaci=kandydaci, propozycja=propozycja, uwaga=serwer.powod
    )

    if propozycja.poziom == PEWNE and kandydaci:
        wynik.status = STATUS_PEWNY
        wynik.uwaga = ""
        wynik.komunikat = "Znaleziono po: " + "; ".join(propozycja.zrodla) + "."
    elif kandydaci:
        wynik.status = STATUS_DO_WYBORU
        if propozycja.poziom == MOZLIWY_DUPLIKAT:
            wynik.komunikat = (
                "Znaleziona osoba PBN jest już odpowiednikiem innego autora "
                "w BPP — to prawdopodobnie duplikat autora do scalenia."
            )
        else:
            wynik.komunikat = (
                "Nie da się wskazać odpowiednika jednoznacznie — wybierz "
                "właściwą osobę z listy."
            )
        if propozycja.uwagi:
            wynik.komunikat += " (" + "; ".join(propozycja.uwagi) + ")"
    else:
        sprawdzono = ["imię i nazwisko", "publikacje powiązane z PBN"]
        if normalize_orcid(autor.orcid):
            sprawdzono.insert(0, f"ORCID {autor.orcid}")
        wynik.komunikat = (
            "Nie udało się znaleźć odpowiednika autora w PBN "
            f"(sprawdzono: {', '.join(sprawdzono)})."
        )
    return wynik
