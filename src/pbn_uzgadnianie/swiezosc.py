"""Z kiedy są dane z PBN, na których pracuje uzgadnianie.

Źródłem prawdy są znaczniki zapisane przy pobieraniu
(``UzgodnienieZPBN.zakres["pobrano"]``), osobno dla każdego źródła.
"""

from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

ZRODLA = (
    ("profil", "profil instytucji (lista prac i przypięte wersje)"),
    ("publikacje", "publikacje (dane prac z wybranych lat)"),
    ("oswiadczenia", "oświadczenia (dyscypliny autorów)"),
    ("wyszukiwanie", "wyszukiwanie w PBN po DOI/ISBN (rekordy BPP bez powiązania)"),
)

JAK_ODSWIEZYC = (
    "Odśwież je przyciskiem „Pobierz dane z PBN” na stronie „uzgodnij z PBN” "
    "(albo poleceniem pbn_uzgodnij z opcją --pobierz)."
)


def opis_daty(kiedy, teraz=None):
    """„wczoraj, 22.11.2026 14:10” — w czasie lokalnym."""
    teraz = timezone.localtime(teraz or timezone.now())
    kiedy = timezone.localtime(kiedy)
    dni = (teraz.date() - kiedy.date()).days
    if dni <= 0:
        dzien = "dzisiaj"
    elif dni == 1:
        dzien = "wczoraj"
    else:
        dzien = f"{dni} dni temu"
    return f"{dzien}, {kiedy:%d.%m.%Y %H:%M}"


def stan_danych(zakres, teraz=None):
    """Opis danych z ``zakres`` przebiegu albo ``None``, gdy danych nie ma.

    Zwraca ``{"zrodla": [{klucz, nazwa, kiedy, opis, stare}], "stare": bool,
    "lata": (od, do) | None, "godzin": próg}``.
    """
    pobrano = (zakres or {}).get("pobrano")
    if not pobrano:
        return None
    teraz = teraz or timezone.now()
    prog = settings.PBN_UZGADNIANIE_DANE_AKTUALNE_GODZIN
    granica = teraz - timedelta(hours=prog)
    zrodla = []
    for klucz, nazwa in ZRODLA:
        if klucz not in pobrano:
            continue
        kiedy = datetime.fromisoformat(pobrano[klucz])
        zrodla.append(
            {
                "klucz": klucz,
                "nazwa": nazwa,
                "kiedy": kiedy,
                "opis": opis_daty(kiedy, teraz),
                "stare": kiedy < granica,
            }
        )
    lata = zakres.get("pobrano_lata")
    return {
        "zrodla": zrodla,
        "stare": any(z["stare"] for z in zrodla),
        "lata": tuple(lata) if lata else None,
        "godzin": prog,
    }


def linie_opisu(stan):
    """Opis stanu danych jako linie tekstu (komenda, XLSX)."""
    if stan is None:
        return ["Dane z PBN: brak informacji o pobraniu."]
    linie = [f"Dane z PBN — {z['nazwa']}: pobrane {z['opis']}" for z in stan["zrodla"]]
    if stan["stare"]:
        linie.append(
            f"UWAGA: dane z PBN są starsze niż {stan['godzin']} godz. {JAK_ODSWIEZYC}"
        )
    return linie
