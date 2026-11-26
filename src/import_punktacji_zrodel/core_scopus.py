"""Import CiteScore z eksportu źródeł Scopus do ``Punktacja_Zrodla`` (FD#370).

Zasady, których ten moduł pilnuje:

- dopasowanie źródła: najpierw ISSN/E-ISSN (gdy plik je ma), potem dokładny
  tytuł bez względu na wielkość liter i diakrytyki — ``kandydaci_zrodla``
  z ``import_common``; żadnego dopasowania rozmytego,
- wiersz pasujący do kilku źródeł ORAZ kilka wierszy pasujących do jednego
  źródła nie są zapisywane bez decyzji użytkownika
  (``ImportPunktacjiZrodel.wybory``),
- brak źródła w BPP = wiersz niedopasowany; nowych źródeł nie tworzymy,
- istniejąca wartość za dany rok zostaje, chyba że zaznaczono
  „Nadpisz istniejące”,
- kwartyl Scopus uzupełnia ``Punktacja_Zrodla.save()`` (pusty → z percentyla),
- każda zapisana zmiana trafia do historii źródła (``zmiana_rekordu``).
"""

from collections import defaultdict
from decimal import Decimal

from bpp.models import Punktacja_Zrodla, Zrodlo
from bpp.models.zrodlo import kwartyl_scopus_z_percentyla
from bpp.wersjonowanie import zmiana_rekordu
from import_common.core.zrodlo import kandydaci_zrodla
from import_punktacji_zrodel.models import (
    WYBOR_POMIN,
    WierszImportuPunktacjiZrodel,
)
from import_punktacji_zrodel.parser_scopus import wczytaj_plik_scopus

BRAK_ZRODLA = "Brak źródła w BPP"
BRAK_DECYZJI = (
    "Wybierz źródło albo pomiń wiersz — bez decyzji nic nie zostanie zapisane."
)


class NiedozwolonyWybor(ValueError):
    """Wybór użytkownika, którego nie da się przyjąć (komunikat dla człowieka)."""


def _dane(cz, sposob: str) -> dict:
    return {
        "nazwa": cz.nazwa,
        "issn": cz.issn,
        "e_issn": cz.e_issn,
        "wydawca": cz.wydawca,
        "citescore": str(cz.citescore) if cz.citescore is not None else None,
        "percentyl": cz.percentyl,
        "snip": str(cz.snip) if cz.snip is not None else None,
        "sposob": sposob,
        "niejednoznaczny": False,
        "powod": "",
        "wybor": None,
    }


def _porownaj_pole(etykieta, pole, nowe, pz, nadpisz, operacje, to_save):
    if nowe is None:
        operacje.append(f"{etykieta}: brak danych w pliku")
        return
    stare = getattr(pz, pole) if pz is not None else None
    # „Punktacja SNIP” nie ma wartości pustej — brak to 0,000.
    puste = stare is None or (pole == "punktacja_snip" and stare == 0)
    if puste:
        operacje.append(f"{etykieta}: brak → {nowe}")
        to_save[pole] = nowe
    elif stare == nowe:
        operacje.append(f"{etykieta}: bez zmian ({stare})")
    elif nadpisz:
        operacje.append(f"{etykieta}: {stare} → {nowe}")
        to_save[pole] = nowe
    else:
        operacje.append(
            f"{etykieta}: w BPP {stare}, w pliku {nowe} — zostaje {stare} "
            "(nie zaznaczono „Nadpisz istniejące”)"
        )


def porownaj(dane: dict, pz, parent) -> tuple[list[str], dict]:
    """Porównuje wiersz pliku z punktacją źródła za rok importu.

    Zwraca ``(operacje, to_save)``: opis dla człowieka (wartość obecna
    i nowa) oraz pola ``Punktacja_Zrodla`` do zapisania.
    """
    operacje: list[str] = []
    to_save: dict = {}
    nadpisz = parent.nadpisz_istniejace

    if parent.importuj_citescore:
        citescore = dane.get("citescore")
        _porownaj_pole(
            "CiteScore",
            "citescore",
            Decimal(citescore) if citescore is not None else None,
            pz,
            nadpisz,
            operacje,
            to_save,
        )
        _porownaj_pole(
            "Najwyższy percentyl",
            "citescore_percentyl",
            dane.get("percentyl"),
            pz,
            nadpisz,
            operacje,
            to_save,
        )
    if parent.importuj_snip:
        snip = dane.get("snip")
        _porownaj_pole(
            "SNIP",
            "punktacja_snip",
            Decimal(snip) if snip is not None else None,
            pz,
            nadpisz,
            operacje,
            to_save,
        )

    if "citescore_percentyl" in to_save:
        obecny = pz.kwartyl_w_scopus if pz is not None else None
        if obecny is None:
            kwartyl = kwartyl_scopus_z_percentyla(to_save["citescore_percentyl"])
            operacje.append(f"Kwartyl Scopus: brak → Q{kwartyl} (z percentyla)")
        else:
            operacje.append(f"Kwartyl Scopus: zostaje Q{obecny} (wpisany wcześniej)")
    return operacje, to_save


def _zapisz(zrodlo, rok, to_save, operacje, parent):
    komentarz = f"Import CiteScore (Scopus) za rok {rok}: " + "; ".join(operacje)
    with zmiana_rekordu(parent.owner, zrodlo, komentarz):
        pz = zrodlo.punktacja_zrodla_set.filter(rok=rok).first()
        if pz is None:
            pz = Punktacja_Zrodla(zrodlo=zrodlo, rok=rok)
            for pole, wartosc in to_save.items():
                setattr(pz, pole, wartosc)
            pz.save()
        else:
            for pole, wartosc in to_save.items():
                setattr(pz, pole, wartosc)
            pz.save(update_fields=list(to_save))


def ustal_wiersz(parent, wiersz, zrodla, wybor, uzyte, dry_run):
    """Wypełnia ``wiersz`` (źródło, rezultat, znaczniki) i — poza podglądem —
    zapisuje wartości przy źródle. NIE zapisuje samego wiersza.

    ``zrodla`` — {pk: Zrodlo} dla kandydatów wiersza; ``wybor`` — decyzja
    użytkownika (pk źródła, ``WYBOR_POMIN`` albo ``None``); ``uzyte`` —
    {pk źródła: nr wiersza}, źródła, które w tym przebiegu dostały już wartości.
    """
    dane = wiersz.dane_z_xls
    wiersz.zrodlo = None
    wiersz.do_rozstrzygniecia = False
    wiersz.wymaga_zmian = False
    dane["wybor"] = None

    if not wiersz.kandydaci:
        wiersz.rezultat = BRAK_ZRODLA
        return

    if dane["niejednoznaczny"]:
        if wybor == WYBOR_POMIN:
            dane["wybor"] = WYBOR_POMIN
            wiersz.rezultat = dane["powod"] + "\nPominięto — decyzja użytkownika."
            return
        if wybor not in wiersz.kandydaci:
            wiersz.do_rozstrzygniecia = True
            wiersz.rezultat = dane["powod"] + "\n" + BRAK_DECYZJI
            return
        zrodlo = zrodla[wybor]
        dane["wybor"] = wybor
        naglowek = dane["powod"] + f"\nWybrano: {zrodlo.nazwa} — decyzja użytkownika."
    else:
        zrodlo = zrodla[wiersz.kandydaci[0]]
        naglowek = f"Dopasowano po: {dane['sposob']}."

    wiersz.zrodlo = zrodlo
    if zrodlo.pk in uzyte:
        # Bezpiecznik: jedno źródło dostaje wartości najwyżej z jednego wiersza.
        wiersz.rezultat = (
            naglowek + f"\nPominięto: to źródło dostaje już wartości z wiersza "
            f"{uzyte[zrodlo.pk]}."
        )
        return
    uzyte[zrodlo.pk] = wiersz.nr_wiersza

    pz = zrodlo.punktacja_zrodla_set.filter(rok=parent.rok).first()
    operacje, to_save = porownaj(dane, pz, parent)
    if to_save and not dry_run:
        _zapisz(zrodlo, parent.rok, to_save, operacje, parent)
    wiersz.wymaga_zmian = bool(to_save)
    wiersz.rezultat = "\n".join([naglowek, *operacje])


def _powod(kandydaci, wspolne) -> str:
    if len(kandydaci) > 1:
        return f"Pasuje kilka źródeł w BPP ({len(kandydaci)})."
    numery = ", ".join(str(n) for n in wspolne)
    return f"To samo źródło pasuje też do innych wierszy pliku (wiersze: {numery})."


def analyze_scopus_file(path, parent, p):
    if parent.rok is None:
        msg = "Podaj rok — plik Scopus go nie zawiera."
        p.log(msg)
        raise ValueError(msg)

    czasopisma = wczytaj_plik_scopus(path)
    dry_run = not parent.zapisz_zmiany_do_bazy
    n = len(czasopisma)

    dopasowania = []
    # {pk źródła: [nr wierszy]} — tylko wiersze z JEDNYM kandydatem; dwa takie
    # wiersze na to samo źródło wymagają decyzji, który jest właściwy.
    wiersze_zrodla = defaultdict(list)
    uzyte: dict[int, int] = {}

    # Dwa przebiegi pod jednym paskiem postępu: dopasowanie (wolne — pełny
    # skan tabeli źródeł na wiersz), potem porównanie/zapis.
    kroki = [(0, i) for i in range(n)] + [(1, i) for i in range(n)]
    for etap, i in p.track(kroki, total=len(kroki), label="Import CiteScore (Scopus)"):
        if etap == 0:
            cz = czasopisma[i]
            kandydaci, sposob = kandydaci_zrodla(cz.nazwa, cz.issn, cz.e_issn)
            dopasowania.append((kandydaci, sposob))
            if len(kandydaci) == 1:
                wiersze_zrodla[kandydaci[0].pk].append(i + 1)
            continue

        nr = i + 1
        kandydaci, sposob = dopasowania[i]
        wiersz = WierszImportuPunktacjiZrodel(
            parent=parent,
            nr_wiersza=nr,
            dane_z_xls=_dane(czasopisma[i], sposob),
            kandydaci=[z.pk for z in kandydaci],
        )
        wspolne = []
        if len(kandydaci) == 1:
            wspolne = [x for x in wiersze_zrodla[kandydaci[0].pk] if x != nr]
        if len(kandydaci) > 1 or wspolne:
            wiersz.dane_z_xls["niejednoznaczny"] = True
            wiersz.dane_z_xls["powod"] = _powod(kandydaci, wspolne)
        ustal_wiersz(
            parent,
            wiersz,
            {z.pk: z for z in kandydaci},
            parent.wybory.get(str(nr)),
            uzyte,
            dry_run,
        )
        wiersz.save()


def ustaw_wybor(parent, wiersz, wybor):
    """Zapisuje decyzję użytkownika dla wiersza niejednoznacznego i przelicza
    jego podgląd. ``wybor``: pk źródła, ``WYBOR_POMIN`` albo ``None`` (cofnij).

    Rzuca ``NiedozwolonyWybor``, gdy wybór jest spoza listy kandydatów albo
    źródło jest już przypisane do innego wiersza tego importu.
    """
    if not wiersz.dane_z_xls.get("niejednoznaczny"):
        raise NiedozwolonyWybor("Ten wiersz nie wymaga wyboru źródła.")
    if wybor not in (None, WYBOR_POMIN):
        if wybor not in wiersz.kandydaci:
            raise NiedozwolonyWybor("Wybrane źródło nie jest kandydatem tego wiersza.")
        if not Zrodlo.objects.filter(pk=wybor).exists():
            raise NiedozwolonyWybor("Wybrane źródło już nie istnieje w BPP.")
        inny = (
            parent.wierszimportupunktacjizrodel_set.filter(zrodlo_id=wybor)
            .exclude(pk=wiersz.pk)
            .first()
        )
        if inny is not None:
            raise NiedozwolonyWybor(
                f"To źródło jest już przypisane do wiersza {inny.nr_wiersza}. "
                "Jedno źródło może dostać wartości tylko z jednego wiersza — "
                "najpierw pomiń tamten wiersz."
            )

    klucz = str(wiersz.nr_wiersza)
    if wybor is None:
        parent.wybory.pop(klucz, None)
    else:
        parent.wybory[klucz] = wybor
    parent.save(update_fields=["wybory"])

    zrodla = {z.pk: z for z in Zrodlo.objects.filter(pk__in=wiersz.kandydaci)}
    ustal_wiersz(parent, wiersz, zrodla, wybor, {}, dry_run=True)
    wiersz.save()
