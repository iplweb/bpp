"""
Funkcje wyszukiwania zdublowanych autorów.
"""

from django.db.models import Q, QuerySet

from bpp.models import Autor
from deduplikator_autorow.models import NotADuplicate
from import_common.normalization import poprzednie_nazwiska_token_regex
from pbn_api.models import OsobaZInstytucji


def word_match_filter(field: str, word: str) -> Q:
    """
    Tworzy filtr Q który dopasowuje słowo jako pełny wyraz w polu tekstowym.
    Równoważne regex: r"(^|[ ])" + word + r"($|[ ])"

    Dopasowuje gdy słowo jest:
    - dokładnie równe całemu polu
    - na początku pola (po nim spacja)
    - na końcu pola (przed nim spacja)
    - w środku pola (otoczone spacjami)
    """
    return (
        Q(**{f"{field}__iexact": word})
        | Q(**{f"{field}__istartswith": word + " "})
        | Q(**{f"{field}__iendswith": " " + word})
        | Q(**{f"{field}__icontains": " " + word + " "})
    )


def initial_match_filter(field: str, initial: str) -> Q:
    r"""
    Tworzy filtr Q który dopasowuje inicjał (np. "J." lub "J ") w polu tekstowym.
    Równoważne regex: r"(^|[ ])" + initial + r"(\.| |$)"

    Dopasowuje inicjał gdy jest:
    - sam (np. "J")
    - z kropką (np. "J.")
    - na początku pola
    - w środku pola (po spacji)
    - na końcu pola
    """
    return (
        Q(**{f"{field}__iexact": initial})
        | Q(**{f"{field}__iexact": initial + "."})
        | Q(**{f"{field}__istartswith": initial + "."})
        | Q(**{f"{field}__istartswith": initial + " "})
        | Q(**{f"{field}__iendswith": " " + initial})
        | Q(**{f"{field}__iendswith": " " + initial + "."})
        | Q(**{f"{field}__icontains": " " + initial + "."})
        | Q(**{f"{field}__icontains": " " + initial + " "})
    )


def _nazwisko_query(nazwisko: str) -> Q:
    """
    Buduje warunek Q dopasowujący kandydatów po samym nazwisku:
    pełne nazwisko, odwrócone dwuczłonowe, części złożonego oraz nazwisko
    jako pełny człon w nazwisku złożonym.
    """
    # 1. Pełne nazwisko - dokładne dopasowanie (case insensitive)
    q = Q(nazwisko__iexact=nazwisko)

    if "-" in nazwisko:
        czesci_nazwiska = nazwisko.split("-")

        # 2. Nazwisko odwrócone (np. "Gal-Cisoń" -> "Cisoń-Gal")
        if len(czesci_nazwiska) == 2:
            odwrocone_nazwisko = f"{czesci_nazwiska[1]}-{czesci_nazwiska[0]}"
            q |= Q(nazwisko__iexact=odwrocone_nazwisko)

        # 3. Części nazwiska złożonego (np. "Gal-Cisoń" -> "Gal" lub "Cisoń")
        for czesc in czesci_nazwiska:
            czesc = czesc.strip()
            if len(czesc) > 2:  # Tylko części dłuższe niż 2 znaki
                q |= Q(nazwisko__iexact=czesc)

    # 4. Nazwisko jako pełny człon w nazwisku złożonym
    # np. "Woźniak" dopasuje "Kowalska-Woźniak" lub "Woźniak-Kowalska"
    # ale NIE "Przewoźniak" (bo Woźniak to tylko część słowa)
    # Warunek: nazwisko musi być na początku (przed myślnikiem) lub na końcu (po myślniku)
    if len(nazwisko) > 3:
        # Dopasuj: "Nazwisko-..." lub "...-Nazwisko"
        q |= Q(nazwisko__istartswith=nazwisko + "-")
        q |= Q(nazwisko__iendswith="-" + nazwisko)

    return q


def _poprzednie_nazwiska_query(nazwisko: str, poprzednie_nazwiska: str) -> Q:
    """Buduje warunek Q dopasowujący kandydatów po poprzednich nazwiskach (FD#407).

    Łączy trzy kierunki (nazwisko dopasowywane jako pełny człon listy CSV
    ``poprzednie_nazwiska``, nie podłańcuch):

    - kandydat ma ``nazwisko`` głównego autora wśród swoich poprzednich nazwisk,
    - ``nazwisko`` kandydata równe jednemu z poprzednich nazwisk głównego autora,
    - kandydat dzieli z głównym autorem poprzednie nazwisko.
    """
    q = Q()
    if nazwisko:
        q |= Q(poprzednie_nazwiska__iregex=poprzednie_nazwiska_token_regex(nazwisko))
    for prev in (poprzednie_nazwiska or "").split(","):
        prev = prev.strip()
        if prev:
            q |= Q(nazwisko__iexact=prev)
            q |= Q(poprzednie_nazwiska__iregex=poprzednie_nazwiska_token_regex(prev))
    return q


def _swap_query(nazwisko: str, imiona: str) -> Q:
    """
    Buduje warunek Q dla zamiany imienia z nazwiskiem (swap detection):
    nazwisko duplikatu == imię głównego ORAZ imię duplikatu == nazwisko głównego.
    Wymaga minimum 3 znaków aby uniknąć fałszywych dopasowań.
    """
    q = Q()
    if imiona and len(nazwisko) >= 3:
        for imie_glownego in imiona.split():
            if len(imie_glownego) >= 3:
                # Obie strony zamiany muszą się zgadzać (AND, nie OR)
                q |= Q(nazwisko__iexact=imie_glownego) & word_match_filter(
                    "imiona", nazwisko
                )
    return q


def _imiona_filter(imiona: str, nazwisko: str) -> Q:
    """
    Buduje dodatkowy filtr Q po imionach: dokładne/podobne dopasowanie pełnych
    imion, dopasowanie inicjałów oraz swap (imię duplikatu == nazwisko głównego).
    """
    filtr_imion = Q()

    for imie in imiona.split():
        if not imie:
            continue

        # Sprawdź czy to inicjał (1-2 znaki, ewentualnie z kropką)
        is_initial = len(imie) <= 2 or (len(imie) == 2 and imie[1] == ".")

        if is_initial:
            # Dla inicjałów - szukaj inicjału lub imion zaczynających się od tej litery
            inicjal = imie[0].upper()
            filtr_imion |= initial_match_filter("imiona", inicjal)
            filtr_imion |= Q(imiona__istartswith=inicjal)
            continue

        # Dla pełnych imion - bardziej restrykcyjne dopasowanie
        # Dokładne dopasowanie imienia (jako pełne słowo)
        filtr_imion |= word_match_filter("imiona", imie)

        # Podobne imiona (pierwsze 3+ znaki) - dla imion >= 3 znaków
        # np. "Jan" dopasuje "Janek", "Janusz"
        if len(imie) >= 3:
            prefix = imie[:3]
            filtr_imion |= Q(imiona__istartswith=prefix)

        # Dopasuj pełne imię do inicjału duplikatu
        # "Jan" powinien pasować do "J."
        inicjal = imie[0].upper()
        filtr_imion |= initial_match_filter("imiona", inicjal)

    # Dla swap detection - imię duplikatu może być równe nazwisku głównego
    # np. główny: "Kowalski Janusz" -> duplikat: "Janusz Kowalski"
    # Imię duplikatu ("Kowalski") = nazwisko głównego ("Kowalski")
    if len(nazwisko) >= 5:
        filtr_imion |= word_match_filter("imiona", nazwisko)

    return filtr_imion


def szukaj_kopii(osoba_z_instytucji: OsobaZInstytucji) -> QuerySet[Autor]:
    """
    Funkcja wyszukuje potencjalnie zdublowanych autorów w systemie BPP
    na podstawie głównego autora z OsobaZInstytucji.

    Proces:
    1. Znajduje Scientist po personId z OsobaZInstytucji
    2. Znajduje głównego autora BPP przez rekord_w_bpp()
    3. Wyszukuje wszystkich potencjalnych duplikatów na podstawie:
       - nazwiska (pełnego, odwróconego, części)
       - imienia (podobnego lub częściowego)
       - z tytułem naukowym i bez

    Args:
        osoba_z_instytucji: Obiekt OsobaZInstytucji jako punkt odniesienia

    Returns:
        QuerySet[Autor]: Zbiór potencjalnie zdublowanych autorów
    """
    # Znajdź odpowiednik w Scientist
    try:
        scientist = osoba_z_instytucji.personId
        if not scientist:
            return Autor.objects.none()
    except AttributeError:
        return Autor.objects.none()

    # Znajdź głównego autora w BPP
    glowny_autor = scientist.rekord_w_bpp

    if not glowny_autor:
        return Autor.objects.none()

    # Przygotuj dane do wyszukiwania
    nazwisko = glowny_autor.nazwisko.strip() if glowny_autor.nazwisko else ""
    imiona = glowny_autor.imiona.strip() if glowny_autor.imiona else ""

    if not nazwisko:
        return Autor.objects.none()

    # Zbuduj zapytanie na podstawie nazwiska + ewentualnej zamiany imię/nazwisko
    # + poprzednich nazwisk (FD#407 — zmiana nazwiska, np. panieńskie → po mężu)
    q = _nazwisko_query(nazwisko) | _swap_query(nazwisko, imiona)
    q |= _poprzednie_nazwiska_query(nazwisko, glowny_autor.poprzednie_nazwiska or "")

    # Wyszukaj kandydatów na duplikaty
    kandydaci = Autor.objects.filter(q).exclude(pk=glowny_autor.pk)

    # Dodatkowe filtrowanie po imieniu jeśli jest dostępne
    if imiona and imiona.split():
        filtr_imion = _imiona_filter(imiona, nazwisko)
        # Zastosuj filtr imion jako dodatkowy warunek OR z pustymi imionami
        kandydaci = kandydaci.filter(
            filtr_imion | Q(imiona__isnull=True) | Q(imiona__exact="")
        )

    kandydaci = kandydaci.exclude(
        pk__in=NotADuplicate.objects.values_list("autor_id", flat=True)
    )

    # Wyklucz autorów, którzy mają własny rekord w POL-on/PBN
    # (posiadają powiązanie Autor -> Scientist -> OsobaZInstytucji)
    # Tacy autorzy są pełnoprawnymi pracownikami i nie powinni być traktowani jako duplikaty
    kandydaci = kandydaci.exclude(pbn_uid__osobazinstytucji__isnull=False)

    # select_related dla optymalizacji - unikamy N+1 queries w analysis.py
    return kandydaci.select_related("tytul", "pbn_uid", "plec").distinct()
