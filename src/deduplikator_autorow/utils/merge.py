"""
Funkcje scalania duplikatów autorów.
"""

import logging
import sys
import traceback

import rollbar
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from bpp.models import Autor
from bpp.util import zaloguj_polkniety_wyjatek

from .analysis import analiza_duplikatow

logger = logging.getLogger(__name__)


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


def _transfer_disciplines(glowny_autor, autor_duplikat, user, log_ctx, results):
    """
    Kopiuje przypisania dyscyplin (Autor_Dyscyplina) z duplikatu na głównego
    autora — tylko te, których główny autor jeszcze nie posiada dla danego roku
    i dyscypliny. Każdy transfer jest logowany w LogScalania.
    """
    from bpp.models import Autor_Dyscyplina
    from deduplikator_autorow.models import LogScalania

    for dup_disc in Autor_Dyscyplina.objects.filter(autor=autor_duplikat):
        # Check if main author already has this discipline for this year
        existing = Autor_Dyscyplina.objects.filter(
            autor=glowny_autor,
            rok=dup_disc.rok,
            dyscyplina_naukowa=dup_disc.dyscyplina_naukowa,
        ).exists()

        if existing:
            continue

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
            content_type=ContentType.objects.get_for_model(Autor_Dyscyplina),
            object_id=new_disc.pk,
            modified_record=new_disc,
            dyscyplina_after=dup_disc.dyscyplina_naukowa,
            operation_type="DISCIPLINE_TRANSFER",
            operation_details=f"Przeniesiono dyscyplinę {dup_disc.dyscyplina_naukowa} "
            f"za rok {dup_disc.rok}",
            created_by=user,
            disciplines_transferred=1,
            **log_ctx,
        )


def _transfer_authorship_record(
    record,
    glowny_autor,
    user,
    skip_pbn,
    auto_assign_discipline,
    use_subdiscipline,
    model_label,
    log_publication,
    log_ctx,
    results,
):
    """
    Przenosi pojedynczy rekord autorstwa (Wydawnictwo_*_Autor / Patent_Autor)
    z duplikatu na głównego autora.

    Zwraca True jeśli rekord został przemapowany, False jeśli był kolizją z
    istniejącą publikacją głównego autora i został usunięty.
    """
    from bpp.models import Autor_Dyscyplina
    from deduplikator_autorow.models import LogScalania
    from pbn_export_queue.models import PBN_Export_Queue

    model = type(record)

    # Store old discipline before any changes
    old_discipline = record.dyscyplina_naukowa

    # CHECK IF MAIN AUTHOR ALREADY HAS THIS PUBLICATION
    existing = model.objects.filter(
        rekord=record.rekord,
        autor=glowny_autor,
        typ_odpowiedzialnosci=record.typ_odpowiedzialnosci,
    ).exists()

    if existing:
        # Main author already has this publication - delete duplicate's record
        results["warnings"].append(
            f"Autor główny już ma publikację {record.rekord} "
            f"z typem odpowiedzialności {record.typ_odpowiedzialnosci}. "
            f"Usunięto duplikat."
        )
        record.delete()
        return False

    # Sprawdź dyscypliny
    rok = record.rekord.rok if record.rekord else None
    if record.dyscyplina_naukowa:
        if (
            rok
            and not Autor_Dyscyplina.objects.filter(
                autor=glowny_autor,
                rok=rok,
                dyscyplina_naukowa=record.dyscyplina_naukowa,
            ).exists()
        ):
            results["warnings"].append(
                f"Autor główny nie ma dyscypliny {record.dyscyplina_naukowa} "
                f"za rok {rok}. Dyscyplina została usunięta z publikacji: "
                f"{record.rekord}"
            )
            record.dyscyplina_naukowa = None

    # Przypisz dyscyplinę jeśli brak i włączona opcja
    _assign_discipline_if_missing(
        record,
        glowny_autor,
        rok,
        auto_assign_discipline,
        use_subdiscipline,
        results["warnings"],
    )

    # Przemapuj autora
    record.autor = glowny_autor
    record.save()

    # Log publication transfer (tylko dla Wydawnictwo_Ciagle_Autor)
    if log_publication:
        LogScalania.objects.create(
            main_autor=glowny_autor,
            content_type=ContentType.objects.get_for_model(record.rekord),
            object_id=record.rekord.pk,
            modified_record=record.rekord,
            dyscyplina_before=old_discipline,
            dyscyplina_after=record.dyscyplina_naukowa,
            operation_type="PUBLICATION_TRANSFER",
            operation_details=f"Przeniesiono publikację: {record.rekord}",
            created_by=user,
            publications_transferred=1,
            warnings=(
                results["warnings"][-1]
                if old_discipline and not record.dyscyplina_naukowa
                else ""
            ),
            **log_ctx,
        )

    # Dodaj do kolejki PBN
    if not skip_pbn and record.rekord:
        content_type = ContentType.objects.get_for_model(record.rekord)
        PBN_Export_Queue.objects.create(
            content_type=content_type,
            object_id=record.rekord.pk,
            zamowil=user,
        )
        results["publications_queued_for_pbn"].append(str(record.rekord))

    results["updated_records"].append(f"{model_label}: {record.rekord}")
    results["total_updated"] += 1
    return True


def _transfer_simple_authorship(
    model, model_label, glowny_autor, autor_duplikat, user, skip_pbn, results
):
    """
    Przenosi proste rekordy autorstwa (Praca_Habilitacyjna / Praca_Doktorska),
    gdzie sam obiekt jest publikacją — przemapowuje autora i kolejkuje do PBN.
    """
    from pbn_export_queue.models import PBN_Export_Queue

    for praca in model.objects.filter(autor=autor_duplikat):
        # Przemapuj autora
        praca.autor = glowny_autor
        praca.save()

        # Dodaj do kolejki PBN
        if not skip_pbn:
            content_type = ContentType.objects.get_for_model(praca)
            PBN_Export_Queue.objects.create(
                content_type=content_type,
                object_id=praca.pk,
                zamowil=user,
            )
            results["publications_queued_for_pbn"].append(str(praca))

        results["updated_records"].append(f"{model_label}: {praca}")
        results["total_updated"] += 1


def scal_autora(
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

    # Modele rekordów autorstwa: (model, etykieta, czy logować transfer publikacji).
    # Tylko Wydawnictwo_Ciagle_Autor loguje PUBLICATION_TRANSFER w LogScalania —
    # zachowane jako historyczny quirk oryginalnego kodu.
    authorship_models = [
        ("Wydawnictwo_Ciagle_Autor", Wydawnictwo_Ciagle_Autor, True),
        ("Wydawnictwo_Zwarte_Autor", Wydawnictwo_Zwarte_Autor, False),
        ("Patent_Autor", Patent_Autor, False),
    ]
    # Proste publikacje (sam obiekt jest publikacją).
    simple_models = [
        ("Praca_Habilitacyjna", Praca_Habilitacyjna),
        ("Praca_Doktorska", Praca_Doktorska),
    ]

    try:
        with transaction.atomic():
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

            # Wspólny kontekst dla wpisów LogScalania.
            log_ctx = {
                "duplicate_autor_str": duplicate_autor_str,
                "duplicate_autor_id": duplicate_autor_id,
                "main_scientist": main_scientist,
                "duplicate_scientist": duplicate_scientist,
            }

            # 0. Transfer disciplines from duplicate to main author
            _transfer_disciplines(glowny_autor, autor_duplikat, user, log_ctx, results)

            # 1-3. Rekordy autorstwa (ciągłe, zwarte, patenty)
            for model_label, model, log_publication in authorship_models:
                for record in model.objects.filter(autor=autor_duplikat):
                    _transfer_authorship_record(
                        record,
                        glowny_autor,
                        user,
                        skip_pbn,
                        auto_assign_discipline,
                        use_subdiscipline,
                        model_label,
                        log_publication,
                        log_ctx,
                        results,
                    )

            # 4-5. Prace doktorskie / habilitacyjne
            for model_label, model in simple_models:
                _transfer_simple_authorship(
                    model,
                    model_label,
                    glowny_autor,
                    autor_duplikat,
                    user,
                    skip_pbn,
                    results,
                )

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
        zaloguj_polkniety_wyjatek(
            "Scalanie duplikatu autora — nieoczekiwany błąd operacji scalania",
            logger=logger,
            do_rollbar=True,
        )
        return {"success": False, "error": f"Nieoczekiwany błąd: {str(e)}"}
