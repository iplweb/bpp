"""
Moduł do wyszukiwania zdublowanych autorów w systemie BPP.
"""

from django.db.models import Q, QuerySet

from pbn_api.models import OsobaZInstytucji

from bpp.models import Autor


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

    # 4. Nazwiska zawierające szukane jako część
    if len(nazwisko) > 3:
        q |= Q(nazwisko__icontains=nazwisko)

    # 5. Szukane nazwisko jako część innych nazwisk
    q |= Q(nazwisko__icontains=nazwisko)

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

            # Zastosuj filtr imion jako dodatkowy warunek OR z pustymi imionami
            kandydaci = kandydaci.filter(
                filtr_imion | Q(imiona__isnull=True) | Q(imiona__exact="")
            )

    return kandydaci.distinct()


def analiza_duplikatow(osoba_z_instytucji: OsobaZInstytucji) -> dict:
    """
    Przeprowadza szczegółową analizę znalezionych duplikatów.

    Args:
        osoba_z_instytucji: Obiekt OsobaZInstytucji jako punkt odniesienia

    Returns:
        dict: Słownik z analizą duplikatów zawierający:
            - glowny_autor: główny autor z BPP
            - duplikaty: lista znalezionych duplikatów
            - analiza: szczegółowa analiza każdego duplikatu
    """
    try:
        scientist = osoba_z_instytucji.personId
        if not scientist:
            return {"error": "Nie można znaleźć głównego autora"}
        glowny_autor = scientist.rekord_w_bpp
    except BaseException:
        return {"error": "Nie można znaleźć głównego autora"}

    if not glowny_autor:
        return {"error": "Nie można znaleźć głównego autora"}

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    analiza_duplikatow_lista = []

    for duplikat in duplikaty:
        analiza = {"autor": duplikat, "powody_podobienstwa": [], "pewnosc": 0}  # 0-100%

        # Analiza nazwiska
        if duplikat.nazwisko and glowny_autor.nazwisko:
            if duplikat.nazwisko.lower() == glowny_autor.nazwisko.lower():
                analiza["powody_podobienstwa"].append("identyczne nazwisko")
                analiza["pewnosc"] += 40
            elif (
                glowny_autor.nazwisko.lower() in duplikat.nazwisko.lower()
                or duplikat.nazwisko.lower() in glowny_autor.nazwisko.lower()
            ):
                analiza["powody_podobienstwa"].append("podobne nazwisko")
                analiza["pewnosc"] += 30

        # Analiza imion
        if duplikat.imiona and glowny_autor.imiona:
            imiona_glowny = glowny_autor.imiona.split()
            imiona_duplikat = duplikat.imiona.split()

            # Sprawdź dokładne dopasowania imion
            dokladne_dopasowania = sum(
                1
                for imie_g in imiona_glowny
                for imie_d in imiona_duplikat
                if imie_g.lower() == imie_d.lower()
            )

            if dokladne_dopasowania > 0:
                analiza["powody_podobienstwa"].append(
                    f"wspólne imię ({dokladne_dopasowania})"
                )
                analiza["pewnosc"] += 30 * dokladne_dopasowania

            # Sprawdź podobne imiona (pierwsze 3 znaki)
            podobne_dopasowania = sum(
                1
                for imie_g in imiona_glowny
                for imie_d in imiona_duplikat
                if len(imie_g) >= 3
                and len(imie_d) >= 3
                and (
                    imie_g.lower().startswith(imie_d.lower()[:3])
                    or imie_d.lower().startswith(imie_g.lower()[:3])
                )
                and imie_g.lower() != imie_d.lower()
            )

            if podobne_dopasowania > 0:
                analiza["powody_podobienstwa"].append(
                    f"podobne imię ({podobne_dopasowania})"
                )
                analiza["pewnosc"] += 15 * podobne_dopasowania

            # Sprawdź dopasowania inicjałów
            inicjaly_glowny = [
                imie[0].upper() for imie in imiona_glowny if len(imie) > 0
            ]

            # Wyodrębnij inicjały z duplikatu (obsługa "J.", "J. M.", "Jan M." itp.)
            inicjaly_duplikat = []
            for token in duplikat.imiona.split():
                if len(token) == 1 or (len(token) == 2 and token.endswith(".")):
                    # To jest inicjał
                    inicjaly_duplikat.append(token[0].upper())
                elif len(token) > 1 and not token.endswith("."):
                    # To jest pełne imię
                    inicjaly_duplikat.append(token[0].upper())

            dopasowania_inicjalow = sum(
                1
                for inicjal_g in inicjaly_glowny
                for inicjal_d in inicjaly_duplikat
                if inicjal_g == inicjal_d
            )

            if dopasowania_inicjalow > 0:
                analiza["powody_podobienstwa"].append(
                    f"pasujące inicjały ({dopasowania_inicjalow})"
                )
                analiza["pewnosc"] += 5 * dopasowania_inicjalow

        elif not duplikat.imiona and glowny_autor.imiona:
            analiza["powody_podobienstwa"].append("brak imion w duplikacie")
            analiza["pewnosc"] += 10

        analiza_duplikatow_lista.append(analiza)

    # Sortuj duplikaty według pewności
    analiza_duplikatow_lista.sort(key=lambda x: x["pewnosc"], reverse=True)

    return {
        "glowny_autor": glowny_autor,
        "duplikaty": duplikaty,
        "analiza": analiza_duplikatow_lista,
        "ilosc_duplikatow": duplikaty.count(),
    }
