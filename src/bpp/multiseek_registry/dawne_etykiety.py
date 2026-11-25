"""Dawne etykiety pól wyszukiwarki (FD#527).

Multiseek rozpoznaje pola po ETYKIECIE: bieżący formularz siedzi w sesji
użytkownika (``multiseek_json``), a zapisane formularze w bazie
(``multiseek_searchform``). Po zmianie etykiety formularz z dawną nazwą
przestaje się wczytywać. Migracje SQL (bpp 0346, 0533) poprawiają tylko
formularze zapisane w bazie — sesji nie dosięgają (na produkcji sesje są
w cache), więc dawne etykiety tłumaczymy także tutaj, przy odczycie.

Sortowanie jest w formularzu zapisane NUMEREM pozycji na liście, nie
etykietą, więc zmiana nazw kryteriów sortowania niczego nie psuje.
"""

import json

#: ``dawna etykieta: obecna etykieta``. „Punkty PK” i „Typ KBN” to nazwy
#: sprzed migracji 0346; „…MNiSW/MEiN” — sprzed FD#527.
DAWNE_ETYKIETY = {
    "Punkty PK": "Punkty MNiSW",
    "Punkty KBN": "Punkty MNiSW",
    "Punkty MNiSW/MEiN": "Punkty MNiSW",
    "Typ KBN": "Typ MNiSW",
    "Typ MNiSW/MEiN": "Typ MNiSW",
}


def aktualna_etykieta(nazwa):
    """Obecna etykieta pola dla ``nazwa`` (dawnej albo już aktualnej)."""
    return DAWNE_ETYKIETY.get(nazwa, nazwa)


def _popraw_galaz(galaz):
    """Podmienia dawne etykiety w (zagnieżdżonej) liście warunków formularza.
    Zwraca ``True``, gdy coś zmieniono."""
    zmieniono = False
    for element in galaz:
        if isinstance(element, list):
            zmieniono = _popraw_galaz(element) or zmieniono
        elif isinstance(element, dict):
            etykieta = element.get("field")
            if isinstance(etykieta, str) and etykieta in DAWNE_ETYKIETY:
                element["field"] = DAWNE_ETYKIETY[etykieta]
                zmieniono = True
    return zmieniono


def popraw_formularz(dane_json):
    """Formularz multiseek (tekst JSON) z dawnymi etykietami pól zamienionymi
    na obecne. Zwraca ``None``, gdy nie było nic do poprawienia albo tekst nie
    jest formularzem (wtedy o błędzie decyduje dalszy kod wyszukiwarki)."""
    if not isinstance(dane_json, str):
        return None
    try:
        dane = json.loads(dane_json)
    except ValueError:
        return None
    if not isinstance(dane, dict):
        return None
    warunki = dane.get("form_data")
    if not isinstance(warunki, list) or not _popraw_galaz(warunki):
        return None
    return json.dumps(dane)
