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

    # 6. Zamiana imienia z nazwiskiem (swap detection) - tylko dokładne dopasowania
    # Sprawdzamy czy nazwisko głównego autora może być dokładnie imieniem duplikatu i odwrotnie
    if imiona:
        # Pobierz wszystkie imiona głównego autora
        lista_imion_glownego = imiona.split()

        for imie_glownego in lista_imion_glownego:
            # Sprawdź czy nazwisko duplikatu dokładnie pasuje do imienia głównego autora
            q |= Q(nazwisko__iexact=imie_glownego)

        # Sprawdź czy nazwisko głównego może być imieniem duplikatu
        # Szukaj PEŁNEGO nazwiska w imionach (dla swap detection)
        # Ale NIE szukamy CZĘŚCI nazwiska złożonego - to zostało usunięte poniżej
        q |= Q(imiona__icontains=nazwisko)

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
                    # Dokładne dopasowanie imienia
                    filtr_imion |= Q(imiona__icontains=imie)

                    # Podobne imiona (pierwsze 3 znaki)
                    if len(imie) >= 3:
                        prefix = imie[:3]
                        filtr_imion |= Q(imiona__istartswith=prefix)

                    # Dopasowanie inicjału (pierwsza litera + kropka opcjonalna)
                    inicjal = imie[0].upper()
                    # Szukaj inicjału na początku stringa, po spacji lub z kropką
                    filtr_imion |= Q(imiona__iregex=r"(^|[ ])" + inicjal + r"(\.| |$)")

            # Dodaj warunki dla zamiany imienia z nazwiskiem
            # Szukaj PEŁNEGO nazwiska w imionach (dla swap detection)
            # Ale NIE szukamy CZĘŚCI nazwiska złożonego - to zostało usunięte wyżej
            filtr_imion |= Q(imiona__icontains=nazwisko)

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
