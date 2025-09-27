"""
Moduł do wyszukiwania zdublowanych autorów w systemie BPP.
"""

from typing import List, Optional

from django.db.models import Q, QuerySet

from deduplikator_autorow.models import IgnoredAuthor, NotADuplicate
from pbn_api.models import OsobaZInstytucji, Scientist

from django.contrib.contenttypes.models import ContentType

from bpp.models import Autor
from bpp.models.cache import Rekord

# Stałe reprezentujące maksymalną i minimalną możliwą pewność duplikatu
# Obliczone na podstawie wszystkich kryteriów oceny w analiza_duplikatow()

# Maksymalna teoretyczna pewność (optymalne warunki):
# +10 (≤5 publikacji) +15 (brak tytułu) +50 (identyczny ORCID) +40 (identyczne nazwisko)
# +90 (3 identyczne imiona: 30*3) +45 (3 podobne imiona: 15*3) +15 (3 inicjały: 5*3)
# +10 (brak imion) +20 (wspólne lata publikacji)
# = +295 (w praktyce rzadko przekracza 200 ze względu na wzajemne wykluczanie się warunków)
MAX_PEWNOSC = 200

# Minimalna teoretyczna pewność (najgorsze warunki):
# -30 (więcej publikacji niż główny) -15 (różny tytuł) -50 (różny ORCID)
# -20 (duża odległość lat publikacji)
# = -115
MIN_PEWNOSC = -115


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

    # # Wyklucz autorów oznaczonych jako nie-duplikaty
    # # Importuj lokalnie aby uniknąć circular imports
    # from .models import NotADuplicate
    #
    # # Pobierz listę wszystkich scientist_pk oznaczonych jako nie-duplikaty
    # not_duplicate_scientist_pks = set(
    #     NotADuplicate.objects.values_list("scientist_pk", flat=True)
    # )
    #
    # # Filtruj kandydatów - wyklucz tych, którzy są oznaczeni jako nie-duplikaty
    # if not_duplicate_scientist_pks:
    #     # # Znajdź Scientists którzy mają kandydatów jako rekord_w_bpp
    #     # scientists_to_exclude = Scientist.objects.filter(
    #     #     pk__in=not_duplicate_scientist_pks
    #     # ).values_list("rekord_w_bpp", flat=True)
    #     #
    #     # Wyklucz tych kandydatów

    kandydaci = kandydaci.exclude(
        pk__in=NotADuplicate.objects.values_list("autor_id", flat=True)
    )
    #
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
            analiza[
                "pewnosc"
            ] += 10  # zwiększ pewność dla autorów z małą liczbą publikacji

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
                        f"bliskie lata publikacji (różnica {min_odleglosc} lat) - prawdopodobny duplikat"
                    )
                    analiza["pewnosc"] += 15
                elif min_odleglosc <= 7:
                    analiza["powody_podobienstwa"].append(
                        f"średnia odległość lat publikacji ({min_odleglosc} lat) - możliwy duplikat"
                    )
                    analiza["pewnosc"] -= 5
                else:
                    analiza["powody_podobienstwa"].append(
                        f"duża odległość lat publikacji ({min_odleglosc} lat) - mało prawdopodobny duplikat"
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


def znajdz_pierwszego_autora_z_duplikatami(
    excluded_authors: Optional[List[Scientist]] = None,
) -> Optional[Scientist]:
    """
    Znajduje pierwszego autora (Scientist), który ma możliwe duplikaty w systemie BPP.

    Funkcja iteruje przez wszystkie rekordy OsobaZInstytucji i dla każdego sprawdza,
    czy istnieją potencjalne duplikaty używając funkcji szukaj_kopii().

    Args:
        excluded_authors: Lista autorów (Scientist), którzy mają być wykluczeni
                         z wyszukiwania duplikatów. Domyślnie None.

    Returns:
        Optional[Scientist]: Pierwszy znaleziony autor z duplikatami lub None,
                            jeśli nie znaleziono żadnego autora z duplikatami.
    """
    if excluded_authors is None:
        excluded_authors = []

    # Pobierz IDs wykluczonych autorów
    excluded_scientist_ids = [author.pk for author in excluded_authors]

    # Pobierz IDs ignorowanych autorów
    ignored_scientist_ids = list(
        IgnoredAuthor.objects.values_list("scientist_id", flat=True)
    )

    # Przeszukaj wszystkie rekordy OsobaZInstytucji, wykluczając określonych autorów
    osoby_query = (
        OsobaZInstytucji.objects.select_related("personId").all().order_by("lastName")
    )

    # Exclude both explicitly excluded and ignored authors
    all_excluded_ids = excluded_scientist_ids + ignored_scientist_ids
    if all_excluded_ids:
        osoby_query = osoby_query.exclude(personId__pk__in=all_excluded_ids)

    for osoba_z_instytucji in osoby_query:
        # Sprawdź czy istnieje Scientist dla tej osoby
        if not osoba_z_instytucji.personId:
            continue

        scientist = osoba_z_instytucji.personId

        # Sprawdź czy Scientist ma odpowiednik w BPP
        if not hasattr(scientist, "rekord_w_bpp") or not scientist.rekord_w_bpp:
            continue

        # Wyszukaj duplikaty dla tego autora
        duplikaty = szukaj_kopii(osoba_z_instytucji)

        # Jeśli znaleziono duplikaty, zwróć tego Scientist
        if duplikaty.exists():
            return scientist

    # Jeśli nie znaleziono żadnego autora z duplikatami
    return None


def scal_autora(glowny_autor, autor_duplikat, user, skip_pbn=False):
    """
    Scala duplikat autora na głównego autora.

    Args:
        glowny_autor: Obiekt Autor głównego autora
        autor_duplikat: Obiekt Autor duplikatu
        skip_pbn: Jeśli True, nie dodawaj publikacji do kolejki PBN

    Returns:
        dict: Wynik operacji scalania zawierający szczegóły przemapowań
    """
    from django.db import transaction

    from pbn_export_queue.models import PBN_Export_Queue

    from bpp.models import (
        Autor_Dyscyplina,
        Patent_Autor,
        Praca_Doktorska,
        Praca_Habilitacyjna,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte_Autor,
    )

    results = {
        "success": True,
        "warnings": [],
        "updated_records": [],
        "total_updated": 0,
        "publications_queued_for_pbn": [],
        "disciplines_transferred": [],
    }

    try:
        with transaction.atomic():
            # Import logging model
            from deduplikator_autorow.models import LogScalania

            # Store duplicate info before deletion
            duplicate_autor_str = str(autor_duplikat)
            duplicate_autor_id = autor_duplikat.pk

            # Get Scientist references if available
            main_scientist = (
                glowny_autor.pbn_uid if hasattr(glowny_autor, "pbn_uid") else None
            )
            duplicate_scientist = (
                autor_duplikat.pbn_uid if hasattr(autor_duplikat, "pbn_uid") else None
            )

            # 0. Transfer disciplines from duplicate to main author
            duplicate_disciplines = Autor_Dyscyplina.objects.filter(
                autor=autor_duplikat
            )

            for dup_disc in duplicate_disciplines:
                # Check if main author already has this discipline for this year
                existing = Autor_Dyscyplina.objects.filter(
                    autor=glowny_autor,
                    rok=dup_disc.rok,
                    dyscyplina_naukowa=dup_disc.dyscyplina_naukowa,
                ).exists()

                if not existing:
                    # Create new discipline record for main author
                    new_disc = Autor_Dyscyplina.objects.create(
                        autor=glowny_autor,
                        rok=dup_disc.rok,
                        rodzaj_autora=dup_disc.rodzaj_autora,
                        wymiar_etatu=dup_disc.wymiar_etatu,
                        dyscyplina_naukowa=dup_disc.dyscyplina_naukowa,
                        procent_dyscypliny=dup_disc.procent_dyscypliny,
                        subdyscyplina_naukowa=dup_disc.subdyscyplina_naukowa,
                        procent_subdyscypliny=dup_disc.procent_subdyscypliny,
                    )
                    results["disciplines_transferred"].append(
                        f"{dup_disc.dyscyplina_naukowa} ({dup_disc.rok})"
                    )

                    # Log discipline transfer
                    LogScalania.objects.create(
                        main_autor=glowny_autor,
                        duplicate_autor_str=duplicate_autor_str,
                        duplicate_autor_id=duplicate_autor_id,
                        main_scientist=main_scientist,
                        duplicate_scientist=duplicate_scientist,
                        content_type=ContentType.objects.get_for_model(
                            Autor_Dyscyplina
                        ),
                        object_id=new_disc.pk,
                        modified_record=new_disc,
                        dyscyplina_after=dup_disc.dyscyplina_naukowa,
                        operation_type="DISCIPLINE_TRANSFER",
                        operation_details=f"Przeniesiono dyscyplinę {dup_disc.dyscyplina_naukowa} "
                        f"za rok {dup_disc.rok}",
                        created_by=user,
                        disciplines_transferred=1,
                    )

            # 1. Wydawnictwo_Ciagle_Autor
            wc_autorzy = Wydawnictwo_Ciagle_Autor.objects.filter(autor=autor_duplikat)
            for wc_autor in wc_autorzy:
                # Store old discipline before any changes
                old_discipline = wc_autor.dyscyplina_naukowa

                # Sprawdź dyscypliny
                if wc_autor.dyscyplina_naukowa:
                    rok = wc_autor.rekord.rok if wc_autor.rekord else None
                    if (
                        rok
                        and not Autor_Dyscyplina.objects.filter(
                            autor=glowny_autor,
                            rok=rok,
                            dyscyplina_naukowa=wc_autor.dyscyplina_naukowa,
                        ).exists()
                    ):
                        results["warnings"].append(
                            f"Autor główny nie ma dyscypliny {wc_autor.dyscyplina_naukowa} "
                            f"za rok {rok}. Dyscyplina została usunięta z publikacji: {wc_autor.rekord}"
                        )
                        wc_autor.dyscyplina_naukowa = None

                # Przemapuj autora
                wc_autor.autor = glowny_autor
                wc_autor.save()

                # Log publication transfer
                LogScalania.objects.create(
                    main_autor=glowny_autor,
                    duplicate_autor_str=duplicate_autor_str,
                    duplicate_autor_id=duplicate_autor_id,
                    main_scientist=main_scientist,
                    duplicate_scientist=duplicate_scientist,
                    content_type=ContentType.objects.get_for_model(wc_autor.rekord),
                    object_id=wc_autor.rekord.pk,
                    modified_record=wc_autor.rekord,
                    dyscyplina_before=old_discipline,
                    dyscyplina_after=wc_autor.dyscyplina_naukowa,
                    operation_type="PUBLICATION_TRANSFER",
                    operation_details=f"Przeniesiono publikację: {wc_autor.rekord}",
                    created_by=user,
                    publications_transferred=1,
                    warnings=(
                        results["warnings"][-1]
                        if old_discipline and not wc_autor.dyscyplina_naukowa
                        else ""
                    ),
                )

                # Dodaj do kolejki PBN
                if not skip_pbn and wc_autor.rekord:
                    content_type = ContentType.objects.get_for_model(wc_autor.rekord)
                    PBN_Export_Queue.objects.create(
                        content_type=content_type,
                        object_id=wc_autor.rekord.pk,
                        zamowil=user,
                    )
                    results["publications_queued_for_pbn"].append(str(wc_autor.rekord))

                results["updated_records"].append(
                    f"Wydawnictwo_Ciagle_Autor: {wc_autor.rekord}"
                )
                results["total_updated"] += 1

            # 2. Wydawnictwo_Zwarte_Autor
            wz_autorzy = Wydawnictwo_Zwarte_Autor.objects.filter(autor=autor_duplikat)
            for wz_autor in wz_autorzy:
                # Sprawdź dyscypliny
                if wz_autor.dyscyplina_naukowa:
                    rok = wz_autor.rekord.rok if wz_autor.rekord else None
                    if (
                        rok
                        and not Autor_Dyscyplina.objects.filter(
                            autor=glowny_autor,
                            rok=rok,
                            dyscyplina_naukowa=wz_autor.dyscyplina_naukowa,
                        ).exists()
                    ):
                        results["warnings"].append(
                            f"Autor główny nie ma dyscypliny {wz_autor.dyscyplina_naukowa} "
                            f"za rok {rok}. Dyscyplina została usunięta z publikacji: {wz_autor.rekord}"
                        )
                        wz_autor.dyscyplina_naukowa = None

                # Przemapuj autora
                wz_autor.autor = glowny_autor
                wz_autor.save()

                # Dodaj do kolejki PBN
                if not skip_pbn and wz_autor.rekord:
                    PBN_Export_Queue.objects.get_or_create(
                        rekord=wz_autor.rekord, defaults={"created_by": None}
                    )
                    results["publications_queued_for_pbn"].append(str(wz_autor.rekord))

                results["updated_records"].append(
                    f"Wydawnictwo_Zwarte_Autor: {wz_autor.rekord}"
                )
                results["total_updated"] += 1

            # 3. Patent_Autor
            patent_autorzy = Patent_Autor.objects.filter(autor=autor_duplikat)
            for patent_autor in patent_autorzy:
                # Sprawdź dyscypliny
                if patent_autor.dyscyplina_naukowa:
                    rok = patent_autor.rekord.rok if patent_autor.rekord else None
                    if (
                        rok
                        and not Autor_Dyscyplina.objects.filter(
                            autor=glowny_autor,
                            rok=rok,
                            dyscyplina_naukowa=patent_autor.dyscyplina_naukowa,
                        ).exists()
                    ):
                        results["warnings"].append(
                            f"Autor główny nie ma dyscypliny {patent_autor.dyscyplina_naukowa} "
                            f"za rok {rok}. Dyscyplina została usunięta z publikacji: {patent_autor.rekord}"
                        )
                        patent_autor.dyscyplina_naukowa = None

                # Przemapuj autora
                patent_autor.autor = glowny_autor
                patent_autor.save()

                # Dodaj do kolejki PBN
                if not skip_pbn and patent_autor.rekord:
                    PBN_Export_Queue.objects.get_or_create(
                        rekord=patent_autor.rekord, defaults={"created_by": None}
                    )
                    results["publications_queued_for_pbn"].append(
                        str(patent_autor.rekord)
                    )

                results["updated_records"].append(
                    f"Patent_Autor: {patent_autor.rekord}"
                )
                results["total_updated"] += 1

            # 4. Praca_Habilitacyjna
            prace_hab = Praca_Habilitacyjna.objects.filter(autor=autor_duplikat)
            for praca_hab in prace_hab:
                # Przemapuj autora
                praca_hab.autor = glowny_autor
                praca_hab.save()

                # Dodaj do kolejki PBN
                if not skip_pbn:
                    PBN_Export_Queue.objects.get_or_create(
                        rekord=praca_hab, defaults={"created_by": None}
                    )
                    results["publications_queued_for_pbn"].append(str(praca_hab))

                results["updated_records"].append(f"Praca_Habilitacyjna: {praca_hab}")
                results["total_updated"] += 1

            # 5. Praca_Doktorska
            prace_dokt = Praca_Doktorska.objects.filter(autor=autor_duplikat)
            for praca_dokt in prace_dokt:
                # Przemapuj autora
                praca_dokt.autor = glowny_autor
                praca_dokt.save()

                # Dodaj do kolejki PBN
                if not skip_pbn:
                    PBN_Export_Queue.objects.get_or_create(
                        rekord=praca_dokt, defaults={"created_by": None}
                    )
                    results["publications_queued_for_pbn"].append(str(praca_dokt))

                results["updated_records"].append(f"Praca_Doktorska: {praca_dokt}")
                results["total_updated"] += 1

            autor_duplikat.delete()

            return results

    except Exception as e:
        results["success"] = False
        results["error"] = str(e)
        return results


def scal_autorow(
    main_scientist_id: str, duplicate_scientist_id: str, user, skip_pbn: bool = False
) -> dict:
    """
    Scala automatycznie duplikaty autorów.

    Args:
        main_scientist_id: ID głównego autora (Scientist)
        duplicate_scientist_id: ID duplikatu autora (Scientist)
        user: Użytkownik zlecający operację
        skip_pbn: Jeśli True, nie dodawaj publikacji do kolejki PBN

    Returns:
        dict: Wynik operacji scalania

    Raises:
        ValueError: Gdy autorzy nie są na liście duplikatów lub nie istnieją
    """
    from pbn_api.models import Scientist

    try:
        # Pobierz głównego Scientist
        glowny_autor = Autor.objects.get(pk=main_scientist_id)
        autor_duplikat = Autor.objects.get(pk=duplicate_scientist_id)

        if not glowny_autor or not autor_duplikat:
            return {
                "success": False,
                "error": "Jeden z autorów nie ma odpowiednika w BPP",
            }

        # Sprawdź czy duplikat jest na liście duplikatów głównego autora
        if not glowny_autor.pbn_uid.osobazinstytucji:
            return {
                "success": False,
                "error": "Główny autor nie ma związanej osoby z instytucji",
            }

        analiza_result = analiza_duplikatow(glowny_autor.pbn_uid.osobazinstytucji)

        if "error" in analiza_result:
            return {
                "success": False,
                "error": f'Błąd analizy duplikatów: {analiza_result["error"]}',
            }

        # Sprawdź czy autor_duplikat jest w liście duplikatów
        duplikaty_ids = [d["autor"].pk for d in analiza_result["analiza"]]
        if autor_duplikat.pk not in duplikaty_ids:
            return {
                "success": False,
                "error": "Autor duplikat nie znajduje się na liście duplikatów głównego autora",
            }

        # Store duplicate info before deletion
        duplicate_autor_str = str(autor_duplikat)
        duplicate_autor_pk = autor_duplikat.pk

        # Wykonaj scalanie
        result = scal_autora(glowny_autor, autor_duplikat, user, skip_pbn=skip_pbn)

        # Dodaj informacje o autorach do wyniku
        result["main_author"] = str(glowny_autor)
        result["duplicate_author"] = duplicate_autor_str

        # Create summary log entry if successful
        if result.get("success", False):
            from deduplikator_autorow.models import LogScalania

            # Create a summary log entry for the entire merge operation
            LogScalania.objects.create(
                main_autor=glowny_autor,
                duplicate_autor_str=duplicate_autor_str,
                duplicate_autor_id=duplicate_autor_pk,  # Use the stored PK from before deletion
                main_scientist=Scientist.objects.filter(pk=main_scientist_id).first(),
                duplicate_scientist=Scientist.objects.filter(
                    pk=duplicate_scientist_id
                ).first(),
                operation_type="AUTHOR_DELETED",
                operation_details=f"Scalono autora: przeniesiono {result.get('total_updated', 0)} "
                f"publikacji i {len(result.get('disciplines_transferred', []))} dyscyplin",
                created_by=user,
                publications_transferred=result.get("total_updated", 0),
                disciplines_transferred=len(result.get("disciplines_transferred", [])),
                warnings="\n".join(result.get("warnings", [])),
            )

        return result

    except Scientist.DoesNotExist as e:
        return {"success": False, "error": f"Nie znaleziono Scientist o ID: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"Nieoczekiwany błąd: {str(e)}"}


from cacheops import cached


@cached(timeout=5 * 60)
def count_authors_with_duplicates() -> int:
    """
    Zlicza wszystkich autorów (Scientist), którzy mają potencjalne duplikaty w systemie BPP.

    Returns:
        int: Liczba autorów z duplikatami
    """
    count = 0

    # Przeszukaj wszystkie rekordy OsobaZInstytucji
    for osoba_z_instytucji in OsobaZInstytucji.objects.select_related("personId").all():
        # Sprawdź czy istnieje Scientist dla tej osoby
        if not osoba_z_instytucji.personId:
            continue

        scientist = osoba_z_instytucji.personId

        # Sprawdź czy Scientist ma odpowiednik w BPP
        if not hasattr(scientist, "rekord_w_bpp") or not scientist.rekord_w_bpp:
            continue

        # Wyszukaj duplikaty dla tego autora
        duplikaty = szukaj_kopii(osoba_z_instytucji)

        # Jeśli znaleziono duplikaty, zwiększ licznik
        if duplikaty.exists():
            count += 1

    return count


def search_author_by_lastname(search_term, excluded_authors=None):
    """
    Wyszukuje pierwszego autora z duplikatami według części nazwiska.

    Args:
        search_term: część nazwiska do wyszukania
        excluded_authors: lista autorów do wykluczenia

    Returns:
        Scientist object lub None jeśli nie znaleziono
    """
    if not search_term:
        return None

    if excluded_authors is None:
        excluded_authors = []

    excluded_ids = [author.pk for author in excluded_authors if hasattr(author, "pk")]

    # Wyszukaj autorów z BPP o nazwisku zawierającym wyszukiwany termin
    matching_authors = (
        Autor.objects.filter(nazwisko__icontains=search_term)
        .exclude(pbn_uid_id__in=excluded_ids)
        .select_related("pbn_uid", "pbn_uid__osobazinstytucji")
    )

    # Znajdź pierwszego z duplikatami
    for autor in matching_authors[:100]:
        # Sprawdź czy autor ma odpowiednik w Scientist
        if autor.pbn_uid_id:
            try:
                if autor.pbn_uid.osobazinstytucji:
                    duplikaty = szukaj_kopii(autor.pbn_uid.osobazinstytucji)
                    if duplikaty.exists():
                        return autor.pbn_uid
            except Scientist.osobazinstytucji.RelatedObjectDoesNotExist:
                continue

    return None


def count_authors_with_lastname(search_term):
    """
    Zlicza autorów o nazwisku zawierającym wyszukiwany termin, którzy mają duplikaty.

    Args:
        search_term: część nazwiska do wyszukania

    Returns:
        liczba autorów z duplikatami pasujących do wyszukiwania
    """
    if not search_term:
        return 0

    count = 0

    # Wyszukaj autorów z BPP o nazwisku zawierającym wyszukiwany termin
    matching_authors = Autor.objects.filter(
        nazwisko__icontains=search_term
    ).select_related("pbn_uid", "pbn_uid__osobazinstytucji")

    for autor in matching_authors[:100]:
        scientist = autor.pbn_uid
        if scientist is None:
            continue

        # Sprawdź czy ma duplikaty
        try:
            if scientist.osobazinstytucji:
                duplikaty = szukaj_kopii(scientist.osobazinstytucji)
                if duplikaty.exists():
                    count += 1
        except Scientist.osobazinstytucji.RelatedObjectDoesNotExist:
            continue

    return count


def export_duplicates_to_xlsx():
    """
    Eksportuje wszystkich autorów z duplikatami do formatu XLSX.

    Struktura pliku XLSX:
    - Kolumna A: Główny autor (NAZWISKO IMIĘ)
    - Kolumna B: BPP ID głównego autora
    - Kolumna C: BPP URL głównego autora (kliknij link)
    - Kolumna D: PBN UID głównego autora
    - Kolumna E: PBN URL głównego autora (kliknij link)
    - Kolumna F: Duplikat (NAZWISKO IMIĘ)
    - Kolumna G: BPP ID duplikatu
    - Kolumna H: BPP URL duplikatu (kliknij link)
    - Kolumna I: PBN UID duplikatu
    - Kolumna J: PBN URL duplikatu (kliknij link)
    - Kolumna K: Pewność podobieństwa (0.0-1.0)
    - Kolumna L: Ilość duplikatów

    Returns:
        bytes: Zawartość pliku XLSX
    """
    from io import BytesIO

    from openpyxl.styles import Font
    from openpyxl.workbook import Workbook

    from django.contrib.sites.models import Site

    from bpp.util import worksheet_columns_autosize, worksheet_create_table

    # Pobierz domenę serwisu do konstrukcji pełnych URLi
    try:
        current_site = Site.objects.get_current()
        site_domain = f"https://{current_site.domain}"
    except BaseException:
        # Fallback jeśli Site nie jest skonfigurowany
        site_domain = "https://bpp.iplweb.pl"

    def create_pbn_url(pbn_uid):
        """Helper function to create PBN author URL"""
        if pbn_uid:
            return f"https://pbn.nauka.gov.pl/sedno-webapp/persons/details/{pbn_uid}"
        return ""

    # Pobierz wszystkich autorów z duplikatami
    # Najpierw pobierz IDs autorów oznaczonych jako nie-duplikat
    excluded_author_ids = list(NotADuplicate.objects.values_list("autor", flat=True))

    # Następnie znajdź Scientists, którzy mają związanych autorów BPP z duplikatami
    scientists_with_authors = Scientist.objects.filter(
        osobazinstytucji__isnull=False,
        autor__isnull=False,  # Scientist musi mieć związanego autora BPP
    ).exclude(autor__in=excluded_author_ids)

    # Przygotuj dane do eksportu
    data_rows = []
    processed_scientists = set()

    for scientist in scientists_with_authors:
        if scientist.pk in processed_scientists:
            continue

        try:
            # Pobierz analizę duplikatów
            analiza_result = analiza_duplikatow(scientist.osobazinstytucji)

            if "error" in analiza_result or not analiza_result.get("analiza"):
                continue

            glowny_autor = analiza_result["glowny_autor"]
            duplikaty = analiza_result["analiza"]

            if not duplikaty:
                continue

            # Dodaj głównego autora do przetworzonych
            processed_scientists.add(scientist.pk)

            # Przygotuj dane głównego autora
            # Format: NAZWISKO IMIĘ
            glowny_autor_name = (
                f"{glowny_autor.nazwisko or ''} {glowny_autor.imiona or ''}".strip()
            )
            glowny_bpp_id = glowny_autor.pk
            glowny_bpp_url = f"{site_domain}/bpp/autor/{glowny_autor.pk}/"
            glowny_pbn_uid = glowny_autor.pbn_uid_id if glowny_autor.pbn_uid_id else ""
            glowny_pbn_url = create_pbn_url(glowny_pbn_uid)

            # Liczba duplikatów dla tego autora
            duplicate_count = len(duplikaty)

            # Dodaj każdy duplikat jako osobny wiersz
            for duplikat_info in duplikaty:
                autor_duplikat = duplikat_info["autor"]
                pewnosc = duplikat_info["pewnosc"]

                # Oznacz duplikat jako przetworzony
                if hasattr(autor_duplikat, "pbn_uid") and autor_duplikat.pbn_uid:
                    processed_scientists.add(autor_duplikat.pbn_uid.pk)

                # Przygotuj dane duplikatu
                # Format: NAZWISKO IMIĘ
                duplikat_name = f"{autor_duplikat.nazwisko or ''} {autor_duplikat.imiona or ''}".strip()
                duplikat_bpp_id = autor_duplikat.pk
                duplikat_bpp_url = f"{site_domain}/bpp/autor/{autor_duplikat.pk}/"
                duplikat_pbn_uid = (
                    autor_duplikat.pbn_uid_id if autor_duplikat.pbn_uid_id else ""
                )
                duplikat_pbn_url = create_pbn_url(duplikat_pbn_uid)

                data_rows.append(
                    [
                        glowny_autor_name,
                        glowny_bpp_id,
                        glowny_bpp_url,
                        glowny_pbn_uid,
                        glowny_pbn_url,
                        duplikat_name,
                        duplikat_bpp_id,
                        duplikat_bpp_url,
                        duplikat_pbn_uid,
                        duplikat_pbn_url,
                        round(pewnosc / 100, 2),  # Convert percentage to decimal
                        duplicate_count,  # Number of duplicates for this main author
                    ]
                )

        except Exception:
            # Pomiń autorów z błędami w analizie
            continue

    # Stwórz plik XLSX
    wb = Workbook()
    ws = wb.active
    ws.title = "Duplikaty autorów"

    # Sortuj dane alfabetycznie po głównym autorze
    data_rows.sort(key=lambda x: x[0])  # Sort by main author name

    # Nagłówki
    headers = [
        "Główny autor",
        "BPP ID głównego autora",
        "BPP URL głównego autora",
        "PBN UID głównego autora",
        "PBN URL głównego autora",
        "Duplikat",
        "BPP ID duplikatu",
        "BPP URL duplikatu",
        "PBN UID duplikatu",
        "PBN URL duplikatu",
        "Pewność podobieństwa",
        "Ilość duplikatów",
    ]

    ws.append(headers)

    # Dodaj dane
    for row in data_rows:
        ws.append(row)

    # Sformatuj URL-e jako klikalne linki
    if len(data_rows) > 0:
        # Kolumny z URL-ami: C (BPP główny), E (PBN główny), H (BPP duplikat), J (PBN duplikat)
        url_columns = [3, 5, 8, 10]  # 0-indexed: C=2, E=4, H=7, J=9

        for row_idx in range(2, len(data_rows) + 2):  # Start from row 2 (after header)
            for col_idx in url_columns:
                cell = ws.cell(row=row_idx, column=col_idx + 1)  # Excel is 1-indexed
                if cell.value and str(cell.value).startswith("https://"):
                    # Make it a hyperlink
                    cell.hyperlink = cell.value
                    cell.style = "Hyperlink"
                    cell.font = Font(color="0000FF", underline="single")

    # Sformatuj arkusz
    worksheet_columns_autosize(ws)
    if len(data_rows) > 0:
        worksheet_create_table(ws)

    # Zapisz do BytesIO
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()
