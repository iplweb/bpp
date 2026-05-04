"""Merge & delete-author views.

``scal_autorow_view`` performs the actual merge of two authors;
``delete_author`` removes an author when they have no publications.
"""

import sys
import traceback

import rollbar
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor
from bpp.models.cache import Rekord

from ..models import DuplicateCandidate
from ..utils import scal_autora
from .helpers import _read_param, _resolve_autor_id, group_required


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["GET", "POST"])
def scal_autorow_view(request):
    """
    Widok do scalania autorów automatycznie.

    Przyjmuje parametry (warianty):
    - main_autor_id / duplicate_autor_id: ID autorów BPP (preferowane)
    - main_scientist_id / duplicate_scientist_id: ID Scientist z PBN
      (mapowane do Autor przez rekord_w_bpp; backwards-compat)
    - skip_pbn: Opcjonalnie, jeśli true nie wysyła publikacji do PBN
    - candidate_id: Opcjonalnie, ID DuplicateCandidate do oznaczenia jako scalony
    - auto_assign_discipline: Opcjonalnie, jeśli true przypisuje główną dyscyplinę
    - use_subdiscipline: Opcjonalnie, jeśli true używa subdyscypliny jako dyscypliny

    Zwraca wynik operacji w formacie JSON.
    """
    from django.utils import timezone

    skip_pbn = (_read_param(request, "skip_pbn") or "false").lower() == "true"
    candidate_id = _read_param(request, "candidate_id")
    auto_assign_discipline = (
        _read_param(request, "auto_assign_discipline") or "false"
    ).lower() == "true"
    use_subdiscipline = (
        _read_param(request, "use_subdiscipline") or "false"
    ).lower() == "true"

    main_autor_id = _resolve_autor_id(request, "main_autor_id", "main_scientist_id")
    duplicate_autor_id = _resolve_autor_id(
        request, "duplicate_autor_id", "duplicate_scientist_id"
    )

    if not main_autor_id or not duplicate_autor_id:
        # Sygnalizujemy do Rollbar — to nie powinno się zdarzać przy poprawnym
        # wywołaniu z UI; raczej oznacza błąd JS-a lub niespójne dane (np.
        # scientist_id wskazujący na rekord, którego rekord_w_bpp == None).
        try:
            raise ValueError(
                "scal_autorow_view: missing required params after resolution. "
                f"GET={dict(request.GET)} POST_keys={list(request.POST.keys())} "
                f"resolved main={main_autor_id} duplicate={duplicate_autor_id}"
            )
        except ValueError:
            traceback.print_exc()
            rollbar.report_exc_info(sys.exc_info())
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Brak wymaganych parametrów: main_autor_id i duplicate_autor_id"
                ),
            },
            status=400,
        )

    try:
        try:
            main_autor = Autor.objects.get(pk=main_autor_id)
            duplicate_autor = Autor.objects.get(pk=duplicate_autor_id)
        except Autor.DoesNotExist as e:
            rollbar.report_exc_info(sys.exc_info())
            return JsonResponse(
                {"success": False, "error": "Nie znaleziono autora."},
                status=404,
            )

        result = scal_autora(
            main_autor,
            duplicate_autor,
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
                # Candidate may have been deleted in the meantime
                pass  # not an error - merge already succeeded

        return JsonResponse({"success": result.get("success", False), "result": result})
    except NotImplementedError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=501)
    except Exception as e:
        traceback.print_exc()
        rollbar.report_exc_info(sys.exc_info())
        return JsonResponse(
            {
                "success": False,
                "error": "Wystąpił wewnętrzny błąd podczas scalania autorów.",
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
