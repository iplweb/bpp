"""Pobieranie danych pracowników (przyszłych autorów) z USOS API.

W odróżnieniu od jednostek, ``users/staff_index`` **wymaga consumer key** —
anonimowo USOS odpowiada ``method_forbidden`` / ``consumer_missing``.

Metoda przyjmuje selektor ``fields`` obejmujący podpola użytkownika, więc
komplet danych bierzemy jednym stronicowanym przelotem — bez dopytywania
``users/user`` osoba po osobie.

Czego tu NIE ma, a czego potrzebuje moduł kadrowy BPP: wymiaru etatu, grupy
pracowniczej, dat zatrudnienia i informacji o podstawowym miejscu pracy.
Tych danych USOS API nie udostępnia — pochodzą z systemu płacowo-kadrowego
uczelni i dalej muszą wchodzić inną drogą.
"""

from usos_api.fields import buduj_selektor

POLA_PRACOWNIKA = [
    "id",
    "first_name",
    "last_name",
    {"titles": ["before", "after"]},
    "staff_status",
    "email",
    {"external_ids": ["orcid", "pbn_id"]},
    {"employment_positions": [{"position": ["name"]}, {"faculty": ["id", "name"]}]},
    {
        "employment_functions": [
            "function",
            {"faculty": ["id", "name"]},
            "is_official",
        ]
    },
]

POLA_STRONY = buduj_selektor({"users": POLA_PRACOWNIKA}, "next_page", "total")

#: Maksimum dopuszczane przez USOS dla parametru ``num``.
MAKSYMALNY_ROZMIAR_STRONY = 100


def pobierz_pracownikow(
    client,
    fac_ids,
    tylko_nauczyciele=False,
    rozmiar_strony=MAKSYMALNY_ROZMIAR_STRONY,
):
    """Generator znormalizowanych słowników pracowników podanych jednostek.

    ``fac_ids`` to kod jednostki albo lista kodów. Uwaga: ``staff_index`` NIE
    schodzi rekurencyjnie w poddrzewo — żeby objąć całą uczelnię, podaj kody
    z ``usos_api.jednostki.pobierz_jednostki``.
    """
    if isinstance(fac_ids, str):
        fac_ids = [fac_ids]

    start = 0
    while True:
        odpowiedz = client.call(
            "services/users/staff_index",
            fac_ids="|".join(fac_ids),
            fields=POLA_STRONY,
            num=rozmiar_strony,
            start=start,
            teachers_only="true" if tylko_nauczyciele else None,
        )

        uzytkownicy = odpowiedz.get("users") or []
        for surowy in uzytkownicy:
            yield znormalizuj_pracownika(surowy)

        if not odpowiedz.get("next_page") or not uzytkownicy:
            # Drugi warunek chroni przed nieskończoną pętlą, gdyby USOS oddał
            # next_page=true przy pustej stronie.
            return

        start += len(uzytkownicy)


def znormalizuj_pracownika(surowy):
    tytuly = surowy.get("titles") or {}
    zewnetrzne = surowy.get("external_ids") or {}

    return {
        "usos_id": surowy["id"],
        "imie": surowy.get("first_name") or "",
        "nazwisko": surowy.get("last_name") or "",
        "tytul_przed": tytuly.get("before") or "",
        "tytul_po": tytuly.get("after") or "",
        "email": surowy.get("email"),
        "orcid": zewnetrzne.get("orcid"),
        "pbn_id": zewnetrzne.get("pbn_id"),
        "nauczyciel_akademicki": surowy.get("staff_status") == 2,
        "stanowiska": [
            _stanowisko(pozycja)
            for pozycja in (surowy.get("employment_positions") or [])
        ],
        "funkcje": [
            _funkcja(funkcja) for funkcja in (surowy.get("employment_functions") or [])
        ],
    }


def _stanowisko(pozycja):
    jednostka = pozycja.get("faculty") or {}
    stanowisko = (pozycja.get("position") or {}).get("name") or {}
    return {
        "stanowisko": stanowisko.get("pl") or "",
        "jednostka_usos_id": jednostka.get("id"),
        "jednostka": (jednostka.get("name") or {}).get("pl") or "",
    }


def _funkcja(funkcja):
    jednostka = funkcja.get("faculty") or {}
    nazwa = funkcja.get("function") or {}
    return {
        "funkcja": nazwa.get("pl") or "",
        "jednostka_usos_id": jednostka.get("id"),
        "jednostka": (jednostka.get("name") or {}).get("pl") or "",
        "oficjalna": bool(funkcja.get("is_official")),
    }
