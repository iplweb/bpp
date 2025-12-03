"""
Funkcje wyszukiwania zdublowanych autorów.
"""

from django.db.models import Q, QuerySet

from bpp.models import Autor
from deduplikator_autorow.models import NotADuplicate
from pbn_api.models import OsobaZInstytucji


def szukaj_kopii(osoba_z_instytucji: OsobaZInstytucji) -> QuerySet[Autor]:  # noqa: C901
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

    # Rozpocznij budowanie zapytania
    q = Q()

    # 1. Pełne nazwisko - dokładne dopasowanie (case insensitive)
    q |= Q(nazwisko__iexact=nazwisko)

    # 2. Nazwisko odwrócone (np. "Gal-Cisoń" -> "Cisoń-Gal")
    if "-" in nazwisko:
        czesci_nazwiska = nazwisko.split("-")
        if len(czesci_nazwiska) == 2:
            odwrocone_nazwisko = f"{czesci_nazwiska[1]}-{czesci_nazwiska[0]}"
            q |= Q(nazwisko__iexact=odwrocone_nazwisko)

    # 3. Części nazwiska złożonego (np. "Gal-Cisoń" -> "Gal" lub "Cisoń")
    if "-" in nazwisko:
        czesci_nazwiska = nazwisko.split("-")
        for czesc in czesci_nazwiska:
            czesc = czesc.strip()
            if len(czesc) > 2:  # Tylko części dłuższe niż 2 znaki
                q |= Q(nazwisko__iexact=czesc)

    # 4. Substring matching tylko dla nazwisk BEZ myślnika i długich (>6 znaków)
    # Dla nazwisk z myślnikiem używamy TYLKO dokładnego dopasowania części
    if "-" not in nazwisko and len(nazwisko) > 6:
        q |= Q(nazwisko__icontains=nazwisko)

    # 6. Zamiana imienia z nazwiskiem (swap detection) - OBA warunki muszą być spełnione
    # Sprawdzamy czy:
    # - nazwisko duplikatu == imię głównego autora ORAZ
    # - imię duplikatu == nazwisko głównego autora
    # Wymaga minimum 5 znaków aby uniknąć fałszywych dopasowań
    if imiona and len(nazwisko) >= 5:
        for imie_glownego in imiona.split():
            if len(imie_glownego) >= 5:
                # Obie strony zamiany muszą się zgadzać (AND, nie OR)
                swap_condition = Q(nazwisko__iexact=imie_glownego) & Q(
                    imiona__iregex=r"(^|[ ])" + nazwisko + r"($|[ ])"
                )
                q |= swap_condition

    # Wyszukaj kandydatów na duplikaty
    kandydaci = Autor.objects.filter(q).exclude(pk=glowny_autor.pk)

    # Dodatkowe filtrowanie po imieniu jeśli jest dostępne
    if imiona:
        # Pobierz wszystkie imiona
        lista_imion = imiona.split()

        if lista_imion:
            filtr_imion = Q()

            for imie in lista_imion:
                if len(imie) > 0:
                    # Sprawdź czy to inicjał (1-2 znaki, ewentualnie z kropką)
                    is_initial = len(imie) <= 2 or (len(imie) == 2 and imie[1] == ".")

                    if is_initial:
                        # Dla inicjałów - szukaj inicjału lub imion zaczynających się od tej litery
                        inicjal = imie[0].upper()
                        filtr_imion |= Q(
                            imiona__iregex=r"(^|[ ])" + inicjal + r"(\.| |$)"
                        )
                        filtr_imion |= Q(imiona__istartswith=inicjal)
                    else:
                        # Dla pełnych imion - bardziej restrykcyjne dopasowanie
                        # Dokładne dopasowanie imienia (jako pełne słowo)
                        filtr_imion |= Q(imiona__iregex=r"(^|[ ])" + imie + r"($|[ ])")

                        # Podobne imiona (pierwsze 4 znaki) - ale tylko dla dłuższych imion
                        if len(imie) >= 4:
                            prefix = imie[:4]
                            filtr_imion |= Q(imiona__istartswith=prefix)

                        # NIE dopasowujemy inicjałów dla pełnych imion
                        # "Krzysztof" nie powinien pasować do "K." ani do "Barbara"

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

    return kandydaci.distinct()
