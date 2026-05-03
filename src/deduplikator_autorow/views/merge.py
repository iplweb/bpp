"""Views handling author merging and deletion.

- ``scal_autorow_view`` — JSON endpoint that performs an automatic merge
  between two Scientist records and (optionally) marks the originating
  ``DuplicateCandidate`` as resolved.
- ``delete_author`` — removes an author that has no publications.
"""

import sys
import traceback

import rollbar
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor
from bpp.models.cache import Rekord

from ..models import DuplicateCandidate
from ..utils import scal_autorow
from .helpers import group_required


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["GET", "POST"])
def scal_autorow_view(request):
    """
    Widok do scalania autorów automatycznie.

    Przyjmuje parametry:
    - main_scientist_id: ID głównego autora (Scientist)
    - duplicate_scientist_id: ID duplikatu autora (Scientist)
    - skip_pbn: Opcjonalnie, jeśli true nie wysyła publikacji do PBN
    - candidate_id: Opcjonalnie, ID DuplicateCandidate do oznaczenia jako scalony
    - auto_assign_discipline: Opcjonalnie, jeśli true przypisuje główną dyscyplinę
    - use_subdiscipline: Opcjonalnie, jeśli true używa subdyscypliny jako dyscypliny

    Zwraca wynik operacji w formacie JSON.
    """
    if request.method == "GET":
        main_scientist_id = request.GET.get("main_scientist_id")
        duplicate_scientist_id = request.GET.get("duplicate_scientist_id")
        skip_pbn = request.GET.get("skip_pbn", "false").lower() == "true"
        candidate_id = request.GET.get("candidate_id")
        auto_assign_discipline = (
            request.GET.get("auto_assign_discipline", "false").lower() == "true"
        )
        use_subdiscipline = (
            request.GET.get("use_subdiscipline", "false").lower() == "true"
        )
    else:
        main_scientist_id = request.POST.get("main_scientist_id")
        duplicate_scientist_id = request.POST.get("duplicate_scientist_id")
        skip_pbn = request.POST.get("skip_pbn", "false").lower() == "true"
        candidate_id = request.POST.get("candidate_id")
        auto_assign_discipline = (
            request.POST.get("auto_assign_discipline", "false").lower() == "true"
        )
        use_subdiscipline = (
            request.POST.get("use_subdiscipline", "false").lower() == "true"
        )

    if not main_scientist_id or not duplicate_scientist_id:
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Brak wymaganych parametrów: "
                    "main_scientist_id i duplicate_scientist_id"
                ),
            },
            status=400,
        )

    try:
        result = scal_autorow(
            main_scientist_id,
            duplicate_scientist_id,
            request.user,
            skip_pbn=skip_pbn,
            auto_assign_discipline=auto_assign_discipline,
            use_subdiscipline=use_subdiscipline,
        )

        # Mark candidate as merged if provided
        if candidate_id and result.get("success"):
            try:
                candidate = DuplicateCandidate.objects.get(pk=candidate_id)
                candidate.status = DuplicateCandidate.Status.MERGED
                candidate.reviewed_at = timezone.now()
                candidate.reviewed_by = request.user
                candidate.save()
            except DuplicateCandidate.DoesNotExist:
                # Candidate may have been deleted between the merge call and
                # this update; that's not an error worth surfacing.
                pass

        return JsonResponse({"success": result.get("success", False), "result": result})
    except NotImplementedError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=501)
    except Exception as e:
        traceback.print_exc()
        rollbar.report_exc_info(sys.exc_info())
        return JsonResponse(
            {
                "success": False,
                "error": f"Błąd podczas scalania autorów: {str(e)}",
            },
            status=500,
        )


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def delete_author(request):
    """
    Widok do usuwania autora (tylko jeśli nie ma publikacji).
    """
    author_id = request.POST.get("author_id")

    if not author_id:
        messages.error(request, "Brak wymaganego parametru: author_id")
        return redirect("deduplikator_autorow:duplicate_authors")

    try:
        # Sprawdź czy autor istnieje
        autor = Autor.objects.get(pk=author_id)

        # Sprawdź czy autor ma publikacje
        publikacje_count = Rekord.objects.prace_autora(autor).count()

        if publikacje_count > 0:
            messages.error(
                request,
                f"Nie można usunąć autora {autor} - ma {publikacje_count} publikacji.",
            )
        else:
            # Usuń autora
            autor_name = str(autor)
            autor.delete()
            messages.success(
                request, f"Usunięto autora {autor_name} (brak publikacji)."
            )

    except Autor.DoesNotExist:
        messages.error(request, "Nie znaleziono autora o podanym ID.")
    except Exception as e:
        messages.error(request, f"Błąd podczas usuwania autora: {str(e)}")

    return redirect("deduplikator_autorow:duplicate_authors")
