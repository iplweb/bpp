"""Wspólne helpery testowe pakietu ``import_pracownikow``."""

import uuid


def unikalna_nazwa(baza: str) -> str:
    """Czytelna, ale globalnie unikalna nazwa testowa.

    ``Jednostka`` ma unikalne ``nazwa``/``skrot``/``slug``, a te same dosłowne
    nazwy ("Katedra Testowa" itd.) są tworzone w dziesiątkach testów tego
    pakietu (i w sąsiednich: ``api_v1``, ``pbn_import``, ``import_common``).
    Pod shardowaniem xdista testy dzielą jeden worker/bazę i — gdy scommitowany
    wiersz przecieknie poza rollback sąsiada — kolidują na unikalnym constraincie
    (``IntegrityError: bpp_jednostka_nazwa_key`` w setupie fixture'a) albo na
    matchowaniu (ambient wiersz zmienia wynik dopasowania). Doklejamy losowy
    sufiks w NAWIASACH KWADRATOWYCH — nie okrągłych, bo ``()`` matcher
    ``matchuj_jednostke`` interpretuje jako skrót — zachowując czytelny prefiks
    ("nazwę klastra"), po którym nadal poznać o co chodzi w logu/diffie.
    """
    return f"{baza} [{uuid.uuid4().hex[:8]}]"


def unikalny_id(baza: str) -> str:
    """Zwróć czytelny identyfikator odporny na dane pozostawione w testowej DB."""
    return f"{baza}-{uuid.uuid4().hex[:8]}"


def ustaw_biezaca_uczelnie(uczelnia, settings, host="testserver"):
    """Zwiąż uczelnię z hostem testowego klienta → ``SiteResolutionMiddleware``
    ustawi ``request._uczelnia = uczelnia`` (jak produkcyjne domena→Site→Uczelnia).

    Potrzebne w testach multi-hosted (>1 uczelnia), gdzie bramka importu wymaga,
    by request rozstrzygał bieżącą uczelnię — inaczej ``get_for_request`` zwraca
    ``None`` i widok redirectuje na home. Zwraca host do przekazania jako
    ``HTTP_HOST`` w ``client.get/post``."""
    uczelnia.site.domain = host
    uczelnia.site.save(update_fields=["domain"])
    if host not in settings.ALLOWED_HOSTS:
        settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + [host]
    return host
