"""Pobieranie struktury organizacyjnej uczelni z USOS API.

Moduł ``fac`` USOS-a działa **bez consumer key** — strukturę jednostek da się
pobrać anonimowo, w odróżnieniu od danych pracowników (patrz
``usos_api.autorzy``).

Hierarchia: ``fac/subfaculties_deep`` oddaje wszystkich potomków podanej
jednostki (bez niej samej), a pole ``path`` każdej jednostki to lista jej
przodków od korzenia — **bez niej samej**, więc rodzicem jest ostatni element
ścieżki, a głębokością jej długość.
"""

from usos_api.fields import buduj_selektor

POLA_JEDNOSTKI = buduj_selektor(
    "id",
    "name",
    {"path": ["id"]},
    {"stats": ["staff_count"]},
)

#: fac_ids trafia do URL-a jako jeden parametr, więc pytamy porcjami.
DOMYSLNY_ROZMIAR_PACZKI = 30


def pobierz_jednostki(client, root_fac_id, rozmiar_paczki=DOMYSLNY_ROZMIAR_PACZKI):
    """Zwraca listę jednostek poddrzewa ``root_fac_id`` (wraz z korzeniem).

    Kolejność wyniku jest stabilna: najpierw korzeń, potem potomkowie
    w kolejności, w jakiej oddał ich USOS.
    """
    potomkowie = client.call(
        "services/fac/subfaculties_deep",
        fac_id=root_fac_id,
    )
    identyfikatory = [root_fac_id] + [
        fac_id for fac_id in potomkowie if fac_id != root_fac_id
    ]

    jednostki = []
    for paczka in _paczki(identyfikatory, rozmiar_paczki):
        odpowiedz = client.call(
            "services/fac/faculties",
            fac_ids="|".join(paczka),
            fields=POLA_JEDNOSTKI,
        )
        for fac_id in paczka:
            surowa = odpowiedz.get(fac_id)
            if surowa is None:
                # USOS pomija w odpowiedzi jednostki, do których nie mamy
                # dostępu — to nie jest błąd, ale nie chcemy po cichu zgubić
                # informacji, że czegoś brakuje.
                continue
            jednostki.append(znormalizuj_jednostke(surowa))

    return jednostki


def znormalizuj_jednostke(surowa):
    sciezka = surowa.get("path") or []
    nazwa = surowa.get("name") or {}
    return {
        "usos_id": surowa["id"],
        "nazwa": nazwa.get("pl") or "",
        "nazwa_en": nazwa.get("en") or "",
        "parent_usos_id": sciezka[-1]["id"] if sciezka else None,
        "poziom": len(sciezka),
        "liczba_pracownikow": (surowa.get("stats") or {}).get("staff_count"),
    }


def _paczki(elementy, rozmiar):
    for poczatek in range(0, len(elementy), rozmiar):
        yield elementy[poczatek : poczatek + rozmiar]
