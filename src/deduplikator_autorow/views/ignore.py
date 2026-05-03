"""Views for managing the ignored-authors list.

Includes adding a Scientist to the ignore list (``ignore_author``) and
clearing it entirely (``reset_ignored_authors``).
"""

from django.contrib import messages
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods

from bpp.const import GR_WPROWADZANIE_DANYCH
from pbn_api.models import Scientist

from ..models import IgnoredAuthor
from .helpers import group_required


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def ignore_author(request):
    """
    Mark a scientist as ignored in the deduplication process.

    Parameters:
    - scientist_id: ID of the Scientist to ignore
    - reason: Optional reason for ignoring (from POST)
    """
    scientist_id = request.POST.get("scientist_id")
    reason = request.POST.get("reason", "")

    if not scientist_id:
        messages.error(request, "Brak wymaganego parametru: scientist_id")
        return redirect("deduplikator_autorow:duplicate_authors")

    try:
        scientist = Scientist.objects.get(pk=scientist_id)

        # Check if already ignored
        if IgnoredAuthor.objects.filter(scientist=scientist).exists():
            messages.warning(
                request,
                f"Autor {scientist} jest już oznaczony jako ignorowany.",
            )
        else:
            # Get the BPP author if available
            autor = None
            if hasattr(scientist, "rekord_w_bpp"):
                autor = scientist.rekord_w_bpp

            IgnoredAuthor.objects.create(
                scientist=scientist,
                autor=autor,
                reason=reason,
                created_by=request.user,
            )
            messages.success(
                request,
                f"Autor {scientist} został oznaczony jako ignorowany.",
            )

        return redirect("deduplikator_autorow:duplicate_authors")

    except Scientist.DoesNotExist:
        messages.error(request, f"Nie znaleziono Scientist o ID: {scientist_id}")
        return redirect("deduplikator_autorow:duplicate_authors")
    except Exception as e:
        messages.error(request, f"Błąd podczas ignorowania autora: {str(e)}")
        return redirect("deduplikator_autorow:duplicate_authors")


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def reset_ignored_authors(request):
    """
    Remove all ignored author markings.
    """
    count = IgnoredAuthor.objects.count()
    IgnoredAuthor.objects.all().delete()
    messages.success(request, f"Zresetowano {count} ignorowanych autorów.")
    return redirect("deduplikator_autorow:duplicate_authors")
