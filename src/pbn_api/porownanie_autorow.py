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

    @property
    def niepelne(self) -> bool:
        return self.zapisano < self.wyslano

    def komunikat(self) -> str:
        tekst = (
            f"UWAGA: PBN zapisał {self.zapisano} z {self.wyslano} wysłanych "
            f"autorów — w PBN brakuje {self.wyslano - self.zapisano}."
        )
        if self.brakujacy:
            nazwiska = self.brakujacy[:MAKS_NAZWISK]
            reszta = len(self.brakujacy) - len(nazwiska)
            kto = ", ".join(nazwiska)
            if reszta > 0:
                kto += f" (oraz {reszta} kolejnych)"
            tekst += f" Prawdopodobnie brakuje: {kto}."
        return tekst + (
            " Otwórz pracę w PBN i sprawdź listę autorów; najczęściej dotyczy "
            "to autorów bez ustawionego „Odpowiednika w PBN”."
        )


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
    if publikacja.value_or_none("object") is None:
        return None

    wyslani = [
        _klucz(autor) for rola in ROLE_AUTOROW for autor in (wyslane.get(rola) or [])
    ]
    if not wyslani:
        return None

    zapisani = Counter()
    zapisano = 0
    for rola in ROLE_AUTOROW:
        kolekcja = publikacja.value_or_none("object", rola) or []
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
