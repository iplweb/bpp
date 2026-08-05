"""Identyfikatory ROR (Research Organization Registry) — normalizacja i walidacja.

Eksport CERIF/OpenAIRE wystawia ``Uczelnia.ror_id`` i ``Jednostka.ror_id`` jako
element ``RORID`` (patrz ``cerif_export.cerif.orgunit``). Bez poprawnego ROR-a
OpenAIRE Explore nie sklei publikacji z profilem instytucji — a rekord z ROR-em
przepisanym z literówką jest gorszy niż jego brak, bo wygląda na uzupełniony.

Identyfikator ROR to 9 znaków: ``0`` + 6 znaków alfabetu base32 Crockforda
+ 2 cyfry kontrolne wyliczone wg ISO/IEC 7064 MOD 97-10. Alfabet Crockforda
pomija litery ``i``, ``l``, ``o`` i ``u`` (mylone z ``1``, ``1``, ``0``, ``v``),
więc **nie da się** użyć wbudowanego ``int(tekst, 32)`` — Python interpretuje
podstawę 32 jako ``0-9a-v``, co daje inne liczby i inną sumę kontrolną.
"""

import re
from urllib.parse import urlsplit

import requests
from django.core.exceptions import ValidationError

#: Alfabet base32 Crockforda w kolejności wartości 0..31.
ALFABET_CROCKFORDA = "0123456789abcdefghjkmnpqrstvwxyz"

PREFIKS = "https://ror.org/"

#: Sam identyfikator (bez prefiksu), już po normalizacji do małych liter.
WZORZEC_IDENTYFIKATORA = re.compile(r"^0[0-9a-hj-km-np-tv-z]{6}[0-9]{2}$")

URL_API = "https://api.ror.org/organizations"

#: Publiczne API ROR bywa wolne (potrafi mielić kilka sekund), ale komenda
#: interaktywna nie może wisieć w nieskończoność.
TIMEOUT = 15

DOMYSLNY_LIMIT = 5


class BladWyszukiwania(RuntimeError):
    """Nie udało się odpytać publicznego API ROR (sieć, HTTP, format odpowiedzi)."""


HOSTY_ROR = frozenset({"ror.org", "www.ror.org"})


def _sufiks(wartosc):
    """Wytnij z dowolnej postaci wejściowej sam identyfikator, małymi literami.

    Przyjmuje ``https://ror.org/02zbb2597``, ``ror.org/02zbb2597``,
    ``02zbb2597`` oraz warianty z ukośnikiem na końcu, ``http://``, ``www.``
    i wielkimi literami. **Nie waliduje** — to robi `poprawny`.
    """
    if wartosc is None:
        return ""

    tekst = str(wartosc).strip()
    if not tekst:
        return ""

    # Adres z jawnym schematem rozbieramy parserem i porównujemy HOST
    # dokładnie. `startswith("ror.org")` po odcięciu schematu przepuszczał
    # `https://ror.org.evil.example/x` — CodeQL zgłasza to jako
    # py/incomplete-url-substring-sanitization i ma rację, nawet jeśli
    # realnego skutku nie ma (o poprawności decyduje `poprawny`).
    if "//" in tekst:
        rozbite = urlsplit(tekst)
        host = (rozbite.hostname or "").lower()
        if host not in HOSTY_ROR:
            # Świadomie NIE zwracamy pustego łańcucha: pusty znaczy „nie
            # podano ROR-a" i przechodzi walidację. Obcy adres ma zostać
            # odrzucony głośno, a nie po cichu wyczyścić pole.
            return tekst.lower()
        return rozbite.path.strip("/").strip().lower()

    tekst = tekst.lower()
    if tekst.startswith("www."):
        tekst = tekst[len("www.") :]

    # Bez ukośnika we wzorcu, żeby samo ``ror.org`` (bez identyfikatora)
    # zredukowało się do pustego łańcucha.
    if tekst.startswith("ror.org"):
        tekst = tekst[len("ror.org") :]

    return tekst.strip("/").strip()


def normalizuj(wartosc):
    """Sprowadź identyfikator ROR do postaci kanonicznej ``https://ror.org/<id>``.

    Pusta wartość (również ``None``) → pusty łańcuch, żeby dało się wynik wpisać
    wprost do pola ``CharField(blank=True, default="")``.

    Wartość, która nie jest poprawnym ROR-em, też dostaje prefiks — normalizacja
    jest czysto tekstowa, a osąd o poprawności zostawiamy `poprawny`/`waliduj`.
    """
    sufiks = _sufiks(wartosc)
    if not sufiks:
        return ""
    return PREFIKS + sufiks


def _dekoduj_crockforda(tekst):
    """Zamień łańcuch base32 Crockforda na liczbę całkowitą."""
    liczba = 0
    for znak in tekst:
        liczba = liczba * 32 + ALFABET_CROCKFORDA.index(znak)
    return liczba


def suma_kontrolna(rdzen):
    """Dwie cyfry kontrolne ISO/IEC 7064 MOD 97-10 dla 7-znakowego rdzenia.

    ``rdzen`` to identyfikator bez dwóch ostatnich znaków, tzn. ``0`` + 6 znaków
    alfabetu Crockforda. Zwraca łańcuch dwucyfrowy (z wiodącym zerem).
    """
    liczba = _dekoduj_crockforda(rdzen)
    return f"{98 - (liczba * 100) % 97:02d}"


def poprawny(wartosc):
    """Czy ``wartosc`` jest poprawnym identyfikatorem ROR (format + suma)?

    Pusta wartość → ``False``; „brak ROR-a" to nie to samo co „ROR poprawny",
    a rozstrzygnięcie, czy brak jest dopuszczalny, należy do wywołującego.
    """
    sufiks = _sufiks(wartosc)
    if WZORZEC_IDENTYFIKATORA.match(sufiks) is None:
        return False
    return suma_kontrolna(sufiks[:-2]) == sufiks[-2:]


def waliduj(wartosc):
    """Walidator Django dla pól ``ror_id``.

    Pustą wartość przepuszcza — o wymagalności decyduje ``blank`` na polu, nie
    walidator. Rozróżnia błąd formatu od błędnej sumy kontrolnej, bo to zupełnie
    inne pomyłki: pierwszą widać gołym okiem, druga to zwykle literówka
    w przepisywanym identyfikatorze.
    """
    sufiks = _sufiks(wartosc)
    if not sufiks:
        return

    if WZORZEC_IDENTYFIKATORA.match(sufiks) is None:
        raise ValidationError(
            "Nieprawidłowy identyfikator ROR: %(wartosc)s. Oczekiwano dziewięciu "
            "znaków w postaci: zero, sześć znaków z alfabetu base32 Crockforda "
            "(cyfry i litery bez i, l, o, u) i dwie cyfry kontrolne — samych "
            "albo poprzedzonych adresem https://ror.org/ .",
            code="ror_format",
            params={"wartosc": wartosc},
        )

    oczekiwana = suma_kontrolna(sufiks[:-2])
    if oczekiwana != sufiks[-2:]:
        raise ValidationError(
            "Niezgodna suma kontrolna identyfikatora ROR %(wartosc)s: dwie "
            "ostatnie cyfry powinny wynosić %(oczekiwana)s, a wpisano "
            "%(podana)s. Najczęściej oznacza to literówkę — proszę porównać "
            "identyfikator ze stroną https://ror.org/ .",
            code="ror_suma_kontrolna",
            params={
                "wartosc": wartosc,
                "oczekiwana": oczekiwana,
                "podana": sufiks[-2:],
            },
        )


def _nazwa_z_pozycji(pozycja):
    """Nazwa organizacji — schemat v2 (``names``) z odwrotem do v1 (``name``).

    Endpoint ``/organizations`` serwuje dziś rekordy w schemacie v2, gdzie nazw
    jest wiele (etykiety w różnych językach, akronimy, warianty historyczne),
    a ta „główna" jest oznaczona typem ``ror_display``. Starszy schemat v1 miał
    płaskie ``name`` — obsługujemy oba, bo nie mamy wpływu na to, co ROR
    zwróci po kolejnej zmianie domyślnej wersji API.
    """
    nazwa = (pozycja.get("name") or "").strip()
    if nazwa:
        return nazwa

    nazwy = pozycja.get("names") or []
    for wymagany_typ in ("ror_display", "label"):
        for wpis in nazwy:
            if wymagany_typ in (wpis.get("types") or []):
                wartosc = (wpis.get("value") or "").strip()
                if wartosc:
                    return wartosc

    for wpis in nazwy:
        wartosc = (wpis.get("value") or "").strip()
        if wartosc:
            return wartosc

    return ""


def _kraj_z_pozycji(pozycja):
    """Kraj organizacji — schemat v2 (``locations``) z odwrotem do v1."""
    kraj = pozycja.get("country") or {}
    nazwa = (kraj.get("country_name") or "").strip()
    if nazwa:
        return nazwa

    for lokalizacja in pozycja.get("locations") or []:
        szczegoly = lokalizacja.get("geonames_details") or {}
        nazwa = (szczegoly.get("country_name") or "").strip()
        if nazwa:
            return nazwa

    return ""


def szukaj(nazwa, limit=DOMYSLNY_LIMIT):
    """Znajdź w publicznym API ROR organizacje pasujące do ``nazwa``.

    Zwraca listę słowników ``{"id", "nazwa", "kraj"}`` — ``id`` w postaci
    kanonicznej. Pusta nazwa → pusta lista (bez odpytywania sieci).

    Podnosi `BladWyszukiwania` z czytelnym komunikatem, gdy API jest
    niedostępne, odpowie błędem HTTP albo zwróci coś, czego nie da się
    sparsować. Wywołujący ma wtedy szansę pokazać powód i pracować dalej
    zamiast wywalić się na wyjątku z ``requests``.
    """
    nazwa = (nazwa or "").strip()
    if not nazwa:
        return []

    try:
        odpowiedz = requests.get(
            URL_API,
            params={"query": nazwa},
            headers={"Accept": "application/json"},
            timeout=TIMEOUT,
        )
        odpowiedz.raise_for_status()
        dane = odpowiedz.json()
    except requests.RequestException as exc:
        raise BladWyszukiwania(
            f"Nie udało się odpytać API ROR ({URL_API}): {exc}"
        ) from exc
    except ValueError as exc:
        # Zwykle strona błędu proxy/WAF podana jako HTML zamiast JSON-a.
        raise BladWyszukiwania(
            f"API ROR ({URL_API}) zwróciło odpowiedź, której nie da się "
            f"odczytać jako JSON: {exc}"
        ) from exc

    if not isinstance(dane, dict):
        raise BladWyszukiwania(
            f"API ROR ({URL_API}) zwróciło JSON w nieoczekiwanym kształcie "
            f"({type(dane).__name__} zamiast obiektu)."
        )

    wynik = []
    for pozycja in (dane.get("items") or [])[:limit]:
        if not isinstance(pozycja, dict):
            continue
        wynik.append(
            {
                "id": normalizuj(pozycja.get("id")),
                "nazwa": _nazwa_z_pozycji(pozycja),
                "kraj": _kraj_z_pozycji(pozycja),
            }
        )

    return wynik
