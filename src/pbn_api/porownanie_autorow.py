"""Porównanie listy autorów WYSŁANEJ do PBN z tą, którą PBN ZAPISAŁ (FD#509).

Zgłoszenie: w rekordzie BPP jest 6 autorów, a w PBN po wysyłce 4. BPP wysyła
wszystkich autorów pracy (także tych bez odpowiednika w PBN — jako samo imię
i nazwisko), więc różnica może powstać tylko po stronie PBN. Zaraz po wysyłce
pobieramy z PBN zapisany rekord i porównujemy go z tym, co poszło, żeby
redaktor zobaczył „PBN zapisał X z Y autorów” zamiast samego sukcesu.
"""

from collections import Counter
from dataclasses import dataclass, field

from pbn_client import normalize_author_name

ROLE_AUTOROW = ("authors", "editors", "translators", "translationEditors")

MAKS_NAZWISK = 5


def _klucz(autor):
    """Imię i nazwisko sprowadzone do postaci porównywalnej."""
    dane = normalize_author_name(autor)
    nazwisko = (dane.get("lastName") or "").strip()
    imie = (dane.get("firstName") or "").strip()
    return (nazwisko.casefold(), imie.casefold()), f"{nazwisko} {imie}".strip()


@dataclass
class PorownanieAutorow:
    """Wynik porównania: ilu autorów poszło, ilu PBN zapisał, kogo brakuje."""

    wyslano: int
    zapisano: int
    #: Nazwiska wysłane, których nie ma w odpowiedzi PBN. Dopasowanie po
    #: imieniu i nazwisku — PBN może zapisać osobę pod inną pisownią, więc
    #: to wskazówka, a nie pewnik; pewne są liczby.
    brakujacy: list[str] = field(default_factory=list)

    #: ``True``: porównanie z PROFILEM INSTYTUCJI (FD#641), a nie z rekordem
    #: publikacji — inny komunikat, bo to inne miejsce w PBN.
    profil_instytucji: bool = False

    @property
    def niepelne(self) -> bool:
        return self.zapisano < self.wyslano

    def komunikat(self) -> str:
        if self.profil_instytucji:
            return self._komunikat_profil_instytucji()
        tekst = (
            f"UWAGA: PBN zapisał {self.zapisano} z {self.wyslano} wysłanych "
            f"autorów — w PBN brakuje {self.wyslano - self.zapisano}."
        )
        if self.brakujacy:
            tekst += f" Prawdopodobnie brakuje: {self._kto()}."
        return tekst + (
            " Otwórz pracę w PBN i sprawdź listę autorów; najczęściej dotyczy "
            "to autorów bez ustawionego „Odpowiednika w PBN”."
        )

    def _kto(self) -> str:
        nazwiska = self.brakujacy[:MAKS_NAZWISK]
        reszta = len(self.brakujacy) - len(nazwiska)
        kto = ", ".join(nazwiska)
        if reszta > 0:
            kto += f" (oraz {reszta} kolejnych)"
        return kto

    def _komunikat_profil_instytucji(self) -> str:
        tekst = (
            f"UWAGA: w profilu instytucji w PBN jest {self.zapisano} z "
            f"{self.wyslano} wysłanych autorów — brakuje "
            f"{self.wyslano - self.zapisano}."
        )
        if self.brakujacy:
            tekst += f" Prawdopodobnie brakuje: {self._kto()}."
        return tekst + (
            " Sam rekord publikacji w PBN może mieć komplet autorów — różnica "
            "dotyczy profilu instytucji, który bywa aktualizowany przez PBN "
            "z opóźnieniem albo wskazuje inną wersję pracy. Otwórz pracę "
            "w profilu instytucji i sprawdź listę autorów; wszystkie takie "
            "prace pokazuje „PBN” → „niepełne listy autorów w PBN”."
        )


def porownaj_autorow_z_profilem(
    wyslane: dict, publikacja_instytucji
) -> PorownanieAutorow | None:
    """Porównuje autorów z wysłanego JSON-u z PROFILEM INSTYTUCJI (FD#641).

    Rekord publikacji w PBN ma zwykle komplet autorów; krótszą listę bywa
    widać dopiero w profilu instytucji (``PublikacjaInstytucji_V2``) — i to
    ją ogląda redaktor uczelni.

    :param wyslane: JSON wysłany do PBN.
    :param publikacja_instytucji: ``PublikacjaInstytucji_V2`` pobrana po
        wysyłce albo ``None`` (brak wpisu w profilu — nie ma czego porównać).
    """
    if publikacja_instytucji is None:
        return None
    wynik = _porownaj(wyslane, publikacja_instytucji.json_data or {})
    if wynik is not None:
        wynik.profil_instytucji = True
    return wynik


def porownaj_autorow(wyslane: dict, publikacja) -> PorownanieAutorow | None:
    """Porównuje autorów z wysłanego JSON-u z rekordem pobranym z PBN.

    Liczy wszystkie role razem (autorzy, redaktorzy, tłumacze, redaktorzy
    tłumaczenia) — PBN potrafi przenieść osobę między rolami, a zgłoszenie
    dotyczy tego, że ktoś z pracy ZNIKA.

    :param wyslane: JSON wysłany do PBN (``WydawnictwoPBNAdapter.pbn_get_json``).
    :param publikacja: ``pbn_api.models.Publication`` pobrana po wysyłce.
    :return: wynik porównania albo ``None``, gdy odpowiedź PBN nie zawiera
        danych publikacji (nie ma czego porównywać).
    """
    obiekt = publikacja.value_or_none("object")
    if obiekt is None:
        return None
    return _porownaj(wyslane, obiekt)


def _porownaj(wyslane: dict, zapisane: dict) -> PorownanieAutorow | None:
    """Wspólne porównanie: wysłany JSON kontra słownik z kolekcjami ról."""
    wyslani = [
        _klucz(autor) for rola in ROLE_AUTOROW for autor in (wyslane.get(rola) or [])
    ]
    if not wyslani:
        return None

    zapisani = Counter()
    zapisano = 0
    for rola in ROLE_AUTOROW:
        kolekcja = zapisane.get(rola) or []
        if isinstance(kolekcja, dict):
            kolekcja = kolekcja.values()
        for autor in kolekcja:
            zapisani[_klucz(autor)[0]] += 1
            zapisano += 1

    brakujacy = []
    for klucz, nazwa in wyslani:
        if zapisani[klucz] > 0:
            zapisani[klucz] -= 1
        else:
            brakujacy.append(nazwa)

    return PorownanieAutorow(
        wyslano=len(wyslani), zapisano=zapisano, brakujacy=brakujacy
    )


# --------------------------------------------------------------------------
# Zestawienie dla prac już istniejących (FD#641)
# --------------------------------------------------------------------------

_SQL_LICZBA_AUTOROW_W_PROFILU = """
(SELECT COALESCE(SUM(jsonb_array_length(json_data -> rola)), 0)
   FROM unnest(ARRAY['authors', 'editors', 'translators', 'translationEditors'])
        AS rola
  WHERE jsonb_typeof(json_data -> rola) = 'array')
"""


@dataclass
class PracaZNiepelnaListaAutorow:
    """Wiersz zestawienia: praca, która w profilu instytucji ma mniej autorów."""

    rekord: object
    w_bpp: int
    w_profilu: int
    profil_pobrany: object
    wyslana_z_bpp: bool

    @property
    def brakuje(self) -> int:
        return self.w_bpp - self.w_profilu


def prace_z_niepelna_lista_autorow_w_profilu(uczelnia):
    """Prace uczelni, które w profilu instytucji w PBN mają MNIEJ autorów
    niż rekord BPP.

    Liczone z lokalnej kopii profilu instytucji (``PublikacjaInstytucji_V2``)
    — bez zapytań do PBN — więc wynik jest tak świeży, jak ostatnie
    „pobieranie danych z PBN”. Liczone są wszystkie role razem (autorzy,
    redaktorzy, tłumacze, redaktorzy tłumaczenia).

    :return: lista ``PracaZNiepelnaListaAutorow``, od najnowszych prac.
    """
    from django.db.models import Count
    from django.db.models.expressions import RawSQL

    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
    from pbn_api.models import PublikacjaInstytucji_V2, SentData

    profil = {}
    for pbn_uid, w_profilu, pobrany in (
        PublikacjaInstytucji_V2.objects.filter(uczelnia=uczelnia)
        .annotate(w_profilu=RawSQL(_SQL_LICZBA_AUTOROW_W_PROFILU, []))
        .values_list("objectId_id", "w_profilu", "last_updated")
    ):
        profil[pbn_uid] = (int(w_profilu), pobrany)
    if not profil:
        return []

    wyslane = set(
        SentData.objects.filter(
            uczelnia=uczelnia, uploaded_okay=True, pbn_uid_id__in=list(profil)
        ).values_list("pbn_uid_id", flat=True)
    )

    wynik = []
    for model in (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte):
        for rekord in (
            model.objects.filter(pbn_uid_id__in=list(profil))
            .annotate(w_bpp=Count("autorzy_set"))
            .only("pk", "tytul_oryginalny", "rok", "pbn_uid_id")
        ):
            w_profilu, pobrany = profil[rekord.pbn_uid_id]
            if w_profilu < rekord.w_bpp:
                wynik.append(
                    PracaZNiepelnaListaAutorow(
                        rekord=rekord,
                        w_bpp=rekord.w_bpp,
                        w_profilu=w_profilu,
                        profil_pobrany=pobrany,
                        wyslana_z_bpp=rekord.pbn_uid_id in wyslane,
                    )
                )
    wynik.sort(key=lambda w: (-(w.rekord.rok or 0), w.rekord.tytul_oryginalny or ""))
    return wynik
