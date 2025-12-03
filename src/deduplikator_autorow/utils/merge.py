"""
Funkcje scalania duplikatów autorów.
"""

import sys
import traceback

import rollbar
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from bpp.models import Autor

from .analysis import analiza_duplikatow


def _assign_discipline_if_missing(
    autor_record, glowny_autor, rok, auto_assign_discipline, use_subdiscipline, warnings
):
    """
    Przypisuje dyscyplinę do rekordu autora publikacji jeśli brakuje.

    Args:
        autor_record: Rekord autor-publikacja (np. Wydawnictwo_Ciagle_Autor)
        glowny_autor: Główny autor
        rok: Rok publikacji
        auto_assign_discipline: Czy przypisać główną dyscyplinę
        use_subdiscipline: Czy użyć subdyscypliny jako dyscypliny
        warnings: Lista ostrzeżeń do uzupełnienia

    Returns:
        bool: True jeśli przypisano dyscyplinę, False w przeciwnym razie
    """
    from bpp.models import Autor_Dyscyplina

    if autor_record.dyscyplina_naukowa or not rok:
        return False

    if auto_assign_discipline:
        autor_dyscyplina = Autor_Dyscyplina.objects.filter(
            autor=glowny_autor, rok=rok
        ).first()
        if autor_dyscyplina and autor_dyscyplina.dyscyplina_naukowa:
            autor_record.dyscyplina_naukowa = autor_dyscyplina.dyscyplina_naukowa
            return True
        else:
            warnings.append(f"Brak dyscypliny głównego autora dla roku {rok}")

    elif use_subdiscipline:
        autor_dyscyplina = Autor_Dyscyplina.objects.filter(
            autor=glowny_autor, rok=rok, subdyscyplina_naukowa__isnull=False
        ).first()
        if autor_dyscyplina and autor_dyscyplina.subdyscyplina_naukowa:
            autor_record.dyscyplina_naukowa = autor_dyscyplina.subdyscyplina_naukowa
            return True
        else:
            warnings.append(f"Brak subdyscypliny głównego autora dla roku {rok}")

    return False


def scal_autora(  # noqa: C901
    glowny_autor,
    autor_duplikat,
    user,
    skip_pbn=False,
    auto_assign_discipline=False,
    use_subdiscipline=False,
):
    """
    Scala duplikat autora na głównego autora.

    Args:
        glowny_autor: Obiekt Autor głównego autora
        autor_duplikat: Obiekt Autor duplikatu
        user: Użytkownik zlecający operację
        skip_pbn: Jeśli True, nie dodawaj publikacji do kolejki PBN
        auto_assign_discipline: Jeśli True, przypisz główną dyscyplinę autora
            do prac bez dyscypliny
        use_subdiscipline: Jeśli True, użyj subdyscypliny autora jako
            dyscypliny dla prac bez dyscypliny

    Returns:
        dict: Wynik operacji scalania zawierający szczegóły przemapowań
    """
    from bpp.models import (
        Autor_Dyscyplina,
        Patent_Autor,
        Praca_Doktorska,
        Praca_Habilitacyjna,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte_Autor,
    )
    from pbn_export_queue.models import PBN_Export_Queue

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

                # CHECK IF MAIN AUTHOR ALREADY HAS THIS PUBLICATION
                existing = Wydawnictwo_Ciagle_Autor.objects.filter(
                    rekord=wc_autor.rekord,
                    autor=glowny_autor,
                    typ_odpowiedzialnosci=wc_autor.typ_odpowiedzialnosci,
                ).exists()

                if existing:
                    # Main author already has this publication - delete duplicate's record
                    results["warnings"].append(
                        f"Autor główny już ma publikację {wc_autor.rekord} "
                        f"z typem odpowiedzialności {wc_autor.typ_odpowiedzialnosci}. "
                        f"Usunięto duplikat."
                    )
                    wc_autor.delete()
                    continue

                # Sprawdź dyscypliny
                rok = wc_autor.rekord.rok if wc_autor.rekord else None
                if wc_autor.dyscyplina_naukowa:
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
                            f"za rok {rok}. Dyscyplina została usunięta z publikacji: "
                            f"{wc_autor.rekord}"
                        )
                        wc_autor.dyscyplina_naukowa = None

                # Przypisz dyscyplinę jeśli brak i włączona opcja
                _assign_discipline_if_missing(
                    wc_autor,
                    glowny_autor,
                    rok,
                    auto_assign_discipline,
                    use_subdiscipline,
                    results["warnings"],
                )

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
                # Store old discipline before any changes
                old_discipline = wz_autor.dyscyplina_naukowa

                # CHECK IF MAIN AUTHOR ALREADY HAS THIS PUBLICATION
                existing = Wydawnictwo_Zwarte_Autor.objects.filter(
                    rekord=wz_autor.rekord,
                    autor=glowny_autor,
                    typ_odpowiedzialnosci=wz_autor.typ_odpowiedzialnosci,
                ).exists()

                if existing:
                    # Main author already has this publication - delete duplicate's record
                    results["warnings"].append(
                        f"Autor główny już ma publikację {wz_autor.rekord} "
                        f"z typem odpowiedzialności {wz_autor.typ_odpowiedzialnosci}. "
                        f"Usunięto duplikat."
                    )
                    wz_autor.delete()
                    continue

                # Sprawdź dyscypliny
                rok = wz_autor.rekord.rok if wz_autor.rekord else None
                if wz_autor.dyscyplina_naukowa:
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
                            f"za rok {rok}. Dyscyplina została usunięta z publikacji: "
                            f"{wz_autor.rekord}"
                        )
                        wz_autor.dyscyplina_naukowa = None

                # Przypisz dyscyplinę jeśli brak i włączona opcja
                _assign_discipline_if_missing(
                    wz_autor,
                    glowny_autor,
                    rok,
                    auto_assign_discipline,
                    use_subdiscipline,
                    results["warnings"],
                )

                # Przemapuj autora
                wz_autor.autor = glowny_autor
                wz_autor.save()

                # Dodaj do kolejki PBN
                if not skip_pbn and wz_autor.rekord:
                    content_type = ContentType.objects.get_for_model(wz_autor.rekord)
                    PBN_Export_Queue.objects.create(
                        content_type=content_type,
                        object_id=wz_autor.rekord.pk,
                        zamowil=user,
                    )
                    results["publications_queued_for_pbn"].append(str(wz_autor.rekord))

                results["updated_records"].append(
                    f"Wydawnictwo_Zwarte_Autor: {wz_autor.rekord}"
                )
                results["total_updated"] += 1

            # 3. Patent_Autor
            patent_autorzy = Patent_Autor.objects.filter(autor=autor_duplikat)
            for patent_autor in patent_autorzy:
                # Store old discipline before any changes
                old_discipline = patent_autor.dyscyplina_naukowa

                # CHECK IF MAIN AUTHOR ALREADY HAS THIS PUBLICATION
                existing = Patent_Autor.objects.filter(
                    rekord=patent_autor.rekord,
                    autor=glowny_autor,
                    typ_odpowiedzialnosci=patent_autor.typ_odpowiedzialnosci,
                ).exists()

                if existing:
                    # Main author already has this publication - delete duplicate's record
                    results["warnings"].append(
                        f"Autor główny już ma publikację {patent_autor.rekord} "
                        f"z typem odpowiedzialności {patent_autor.typ_odpowiedzialnosci}. "
                        f"Usunięto duplikat."
                    )
                    patent_autor.delete()
                    continue

                # Sprawdź dyscypliny
                rok = patent_autor.rekord.rok if patent_autor.rekord else None
                if patent_autor.dyscyplina_naukowa:
                    if (
                        rok
                        and not Autor_Dyscyplina.objects.filter(
                            autor=glowny_autor,
                            rok=rok,
                            dyscyplina_naukowa=patent_autor.dyscyplina_naukowa,
                        ).exists()
                    ):
                        results["warnings"].append(
                            f"Autor główny nie ma dyscypliny "
                            f"{patent_autor.dyscyplina_naukowa} "
                            f"za rok {rok}. Dyscyplina została usunięta z publikacji: "
                            f"{patent_autor.rekord}"
                        )
                        patent_autor.dyscyplina_naukowa = None

                # Przypisz dyscyplinę jeśli brak i włączona opcja
                _assign_discipline_if_missing(
                    patent_autor,
                    glowny_autor,
                    rok,
                    auto_assign_discipline,
                    use_subdiscipline,
                    results["warnings"],
                )

                # Przemapuj autora
                patent_autor.autor = glowny_autor
                patent_autor.save()

                # Dodaj do kolejki PBN
                if not skip_pbn and patent_autor.rekord:
                    content_type = ContentType.objects.get_for_model(
                        patent_autor.rekord
                    )
                    PBN_Export_Queue.objects.create(
                        content_type=content_type,
                        object_id=patent_autor.rekord.pk,
                        zamowil=user,
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
                    content_type = ContentType.objects.get_for_model(praca_hab)
                    PBN_Export_Queue.objects.create(
                        content_type=content_type,
                        object_id=praca_hab.pk,
                        zamowil=user,
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
                    content_type = ContentType.objects.get_for_model(praca_dokt)
                    PBN_Export_Queue.objects.create(
                        content_type=content_type,
                        object_id=praca_dokt.pk,
                        zamowil=user,
                    )
                    results["publications_queued_for_pbn"].append(str(praca_dokt))

                results["updated_records"].append(f"Praca_Doktorska: {praca_dokt}")
                results["total_updated"] += 1

            autor_duplikat.delete()

            return results

    except Exception as e:
        traceback.print_exc()
        rollbar.report_exc_info(sys.exc_info())
        results["success"] = False
        results["error"] = str(e)
        return results


def scal_autorow(
    main_scientist_id: str,
    duplicate_scientist_id: str,
    user,
    skip_pbn: bool = False,
    auto_assign_discipline: bool = False,
    use_subdiscipline: bool = False,
) -> dict:
    """
    Scala automatycznie duplikaty autorów.

    Args:
        main_scientist_id: ID głównego autora (Scientist)
        duplicate_scientist_id: ID duplikatu autora (Scientist)
        user: Użytkownik zlecający operację
        skip_pbn: Jeśli True, nie dodawaj publikacji do kolejki PBN
        auto_assign_discipline: Jeśli True, przypisz główną dyscyplinę autora
            do prac bez dyscypliny
        use_subdiscipline: Jeśli True, użyj subdyscypliny autora jako
            dyscypliny dla prac bez dyscypliny

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
                "error": f"Błąd analizy duplikatów: {analiza_result['error']}",
            }

        # Sprawdź czy autor_duplikat jest w liście duplikatów
        duplikaty_ids = [d["autor"].pk for d in analiza_result["analiza"]]
        if autor_duplikat.pk not in duplikaty_ids:
            return {
                "success": False,
                "error": "Autor duplikat nie znajduje się na liście duplikatów "
                "głównego autora",
            }

        # Store duplicate info before deletion
        duplicate_autor_str = str(autor_duplikat)
        duplicate_autor_pk = autor_duplikat.pk

        # Wykonaj scalanie
        result = scal_autora(
            glowny_autor,
            autor_duplikat,
            user,
            skip_pbn=skip_pbn,
            auto_assign_discipline=auto_assign_discipline,
            use_subdiscipline=use_subdiscipline,
        )

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
                operation_details=f"Scalono autora: przeniesiono "
                f"{result.get('total_updated', 0)} "
                f"publikacji i {len(result.get('disciplines_transferred', []))} dyscyplin",
                created_by=user,
                publications_transferred=result.get("total_updated", 0),
                disciplines_transferred=len(result.get("disciplines_transferred", [])),
                warnings="\n".join(result.get("warnings", [])),
            )

        return result

    except Autor.DoesNotExist as e:
        return {"success": False, "error": f"Nie znaleziono autora o ID: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"Nieoczekiwany błąd: {str(e)}"}
