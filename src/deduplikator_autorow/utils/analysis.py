"""
Funkcje analizy duplikatów autorów.
"""

from bpp.models import Autor
from bpp.models.cache import Rekord
from pbn_api.models import OsobaZInstytucji

from .search import szukaj_kopii


def analiza_duplikatow(osoba_z_instytucji: OsobaZInstytucji) -> dict:  # noqa: C901
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

        # Analiza liczby publikacji - autorzy z wieloma publikacjami rzadziej są duplikatami
        publikacje_duplikat = Rekord.objects.prace_autora(duplikat).count()
        publikacje_glowny = Rekord.objects.prace_autora(glowny_autor).count()

        # Sprawdź czy potencjalny duplikat ma więcej publikacji niż główny autor
        if publikacje_duplikat > publikacje_glowny and publikacje_duplikat > 3:
            analiza["powody_podobienstwa"].append(
                f"duplikat ma więcej publikacji ({publikacje_duplikat}) niż główny "
                f"({publikacje_glowny}) - prawdopodobnie NIE jest duplikatem"
            )
            analiza["pewnosc"] -= 30  # znacznie zmniejsz pewność
        elif publikacje_duplikat > 10:
            analiza["powody_podobienstwa"].append(
                f"wiele publikacji ({publikacje_duplikat}) - mało prawdopodobny duplikat"
            )
            analiza["pewnosc"] -= 20  # znacznie zmniejsz pewność
        elif publikacje_duplikat > 5:
            analiza["powody_podobienstwa"].append(
                f"średnio publikacji ({publikacje_duplikat}) - możliwy duplikat"
            )
            analiza["pewnosc"] -= 10  # zmniejsz pewność
        elif publikacje_duplikat <= 5:
            analiza["powody_podobienstwa"].append(
                f"mało publikacji ({publikacje_duplikat}) - prawdopodobny duplikat"
            )
            analiza["pewnosc"] += (
                10  # zwiększ pewność dla autorów z małą liczbą publikacji
            )

        # Analiza tytułu naukowego
        if not duplikat.tytul and glowny_autor.tytul:
            analiza["powody_podobienstwa"].append(
                "brak tytułu naukowego - prawdopodobny duplikat"
            )
            analiza["pewnosc"] += 15
        elif duplikat.tytul and glowny_autor.tytul:
            if duplikat.tytul == glowny_autor.tytul:
                analiza["powody_podobienstwa"].append("identyczny tytuł naukowy")
                analiza["pewnosc"] += 10
            else:
                analiza["powody_podobienstwa"].append(
                    "różny tytuł naukowy - mniej prawdopodobny duplikat"
                )
                analiza["pewnosc"] -= 15

        # Analiza ORCID
        if not duplikat.orcid and glowny_autor.orcid:
            analiza["powody_podobienstwa"].append("brak ORCID - prawdopodobny duplikat")
            analiza["pewnosc"] += 15
        elif duplikat.orcid and glowny_autor.orcid:
            if duplikat.orcid == glowny_autor.orcid:
                analiza["powody_podobienstwa"].append(
                    "identyczny ORCID - to ten sam autor"
                )
                analiza["pewnosc"] += 50  # bardzo wysoka pewność
            else:
                analiza["powody_podobienstwa"].append("różny ORCID - to różni autorzy")
                analiza["pewnosc"] -= 50  # bardzo zmniejsz pewność

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

        # Analiza zamiany imienia z nazwiskiem (name-surname swap detection)
        # Wykrywamy tylko dokładne zamiany, bez podobieństwa opartego na pierwszych znakach
        if (
            duplikat.nazwisko
            and duplikat.imiona
            and glowny_autor.nazwisko
            and glowny_autor.imiona
        ):
            imiona_glowny = glowny_autor.imiona.split()
            imiona_duplikat = duplikat.imiona.split()

            # Sprawdź czy nazwisko duplikatu = imię głównego (dokładnie)
            dokladna_zamiana_nazwisko_duplikat = any(
                duplikat.nazwisko.lower() == imie_g.lower() for imie_g in imiona_glowny
            )

            # Sprawdź czy nazwisko głównego = imię duplikatu (dokładnie)
            dokladna_zamiana_nazwisko_glowny = any(
                glowny_autor.nazwisko.lower() == imie_d.lower()
                for imie_d in imiona_duplikat
            )

            # Punktacja za zamianę - tylko dokładne dopasowania
            if dokladna_zamiana_nazwisko_duplikat and dokladna_zamiana_nazwisko_glowny:
                analiza["powody_podobienstwa"].append(
                    f"wykryto pełną zamianę imienia z nazwiskiem "
                    f"('{glowny_autor.nazwisko} {glowny_autor.imiona}' ↔ "
                    f"'{duplikat.nazwisko} {duplikat.imiona}')"
                )
                analiza["pewnosc"] += 50
            elif dokladna_zamiana_nazwisko_duplikat or dokladna_zamiana_nazwisko_glowny:
                analiza["powody_podobienstwa"].append(
                    f"wykryto częściową zamianę imienia z nazwiskiem "
                    f"('{glowny_autor.nazwisko} {glowny_autor.imiona}' ~ "
                    f"'{duplikat.nazwisko} {duplikat.imiona}')"
                )
                analiza["pewnosc"] += 5

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

        # Analiza temporalna - porównanie lat publikacji
        lata_glowny = set(
            Rekord.objects.prace_autora(glowny_autor)
            .filter(rok__isnull=False)
            .values_list("rok", flat=True)
        )
        lata_duplikat = set(
            Rekord.objects.prace_autora(duplikat)
            .filter(rok__isnull=False)
            .values_list("rok", flat=True)
        )

        if lata_glowny and lata_duplikat:
            # Sprawdź czy są wspólne lata lub bliskie lata (+/- 2)
            wspolne_lata = lata_glowny & lata_duplikat

            if wspolne_lata:
                analiza["powody_podobienstwa"].append(
                    f"wspólne lata publikacji: {sorted(wspolne_lata)}"
                )
                analiza["pewnosc"] += 20  # wysokie prawdopodobieństwo duplikatu
            else:
                # Sprawdź bliskie lata (+/- 2 lata)
                min_odleglosc = float("inf")
                for rok_glowny in lata_glowny:
                    for rok_duplikat in lata_duplikat:
                        odleglosc = abs(rok_glowny - rok_duplikat)
                        min_odleglosc = min(min_odleglosc, odleglosc)

                if min_odleglosc <= 2:
                    analiza["powody_podobienstwa"].append(
                        f"bliskie lata publikacji (różnica {min_odleglosc} lat) "
                        "- prawdopodobny duplikat"
                    )
                    analiza["pewnosc"] += 15
                elif min_odleglosc <= 7:
                    analiza["powody_podobienstwa"].append(
                        f"średnia odległość lat publikacji ({min_odleglosc} lat) "
                        "- możliwy duplikat"
                    )
                    analiza["pewnosc"] -= 5
                else:
                    analiza["powody_podobienstwa"].append(
                        f"duża odległość lat publikacji ({min_odleglosc} lat) "
                        "- mało prawdopodobny duplikat"
                    )
                    analiza["pewnosc"] -= 20

        analiza_duplikatow_lista.append(analiza)

    # Sortuj duplikaty według pewności
    analiza_duplikatow_lista.sort(key=lambda x: x["pewnosc"], reverse=True)

    return {
        "glowny_autor": glowny_autor,
        "duplikaty": duplikaty,
        "analiza": analiza_duplikatow_lista,
        "ilosc_duplikatow": duplikaty.count(),
    }


def autor_ma_publikacje_z_lat(
    autor: Autor, lata_od: int = 2022, lata_do: int = 2025
) -> bool:
    """
    Sprawdza czy autor ma publikacje z określonego zakresu lat.

    Args:
        autor: Obiekt Autor do sprawdzenia
        lata_od: Rok początkowy (domyślnie 2022)
        lata_do: Rok końcowy (domyślnie 2025)

    Returns:
        bool: True jeśli autor ma publikacje z tego okresu, False w przeciwnym przypadku
    """
    return (
        Rekord.objects.prace_autora(autor)
        .filter(rok__gte=lata_od, rok__lte=lata_do)
        .exists()
    )
