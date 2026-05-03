"""Ignored-author management views.

- ``ignore_scientist`` — mark a PBN Scientist as ignored
- ``ignore_autor`` — mark a BPP Autor (no PBN link) as ignored
- ``reset_ignored_scientists`` / ``reset_ignored_autorzy`` — clear lists and
  re-trigger scan
- ``_trigger_rescan_after_reset`` — shared helper for reset endpoints
"""

from django.contrib import messages
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor
from pbn_api.models import Scientist
from pbn_downloader_app.freshness import is_pbn_people_data_fresh

from ..models import IgnoredAuthor, IgnoredScientist
from .helpers import get_running_scan, group_required


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def ignore_scientist(request):
    """
    Mark a Scientist (PBN) as ignored in the deduplication process.

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
        if IgnoredScientist.objects.filter(scientist=scientist).exists():
            messages.warning(
                request, f"Autor {scientist} jest już oznaczony jako ignorowany."
            )
        else:
            # Get the BPP author if available
            autor = None
            if hasattr(scientist, "rekord_w_bpp"):
                autor = scientist.rekord_w_bpp

            IgnoredScientist.objects.create(
                scientist=scientist, autor=autor, reason=reason, created_by=request.user
            )
            messages.success(
                request, f"Autor {scientist} został oznaczony jako ignorowany."
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
def ignore_autor(request):
    """
    Mark a BPP Autor (without PBN-Scientist link) as ignored.

    Parameters:
    - autor_id: ID of the Autor to ignore
    - reason: Optional reason for ignoring (from POST)
    """
    autor_id = request.POST.get("autor_id")
    reason = request.POST.get("reason", "")

    if not autor_id:
        messages.error(request, "Brak wymaganego parametru: autor_id")
        return redirect("deduplikator_autorow:duplicate_authors")

    try:
        autor = Autor.objects.get(pk=autor_id)

        if IgnoredAuthor.objects.filter(autor=autor).exists():
            messages.warning(
                request, f"Autor {autor} jest już oznaczony jako ignorowany."
            )
        else:
            IgnoredAuthor.objects.create(
                autor=autor, reason=reason, created_by=request.user
            )
            messages.success(
                request, f"Autor {autor} został oznaczony jako ignorowany."
            )

        return redirect("deduplikator_autorow:duplicate_authors")

    except Autor.DoesNotExist:
        messages.error(request, f"Nie znaleziono autora o ID: {autor_id}")
        return redirect("deduplikator_autorow:duplicate_authors")
    except Exception as e:
        messages.error(request, f"Błąd podczas ignorowania autora: {str(e)}")
        return redirect("deduplikator_autorow:duplicate_authors")


def _trigger_rescan_after_reset(request, reset_label):
    """Próbuje uruchomić nowe skanowanie po resecie list ignorowanych/nie-duplikatów.

    Reset zmienia zbiór wykluczeń, więc cache kandydatów (DuplicateCandidate)
    przestaje być spójny z tym, co użytkownik widzi w UI. Bez rescanu mogą
    pojawiać się duplikaty, które po reset-cie powinny zniknąć (lub odwrotnie:
    brakować takich, które wcześniej były ignorowane). Wywołujemy delay()
    w trybie best-effort — jeżeli scan już biegnie albo dane PBN są stare,
    informujemy użytkownika ale nie blokujemy operacji resetu.
    """
    from ..tasks import scan_for_duplicates

    if get_running_scan():
        messages.info(
            request,
            f"{reset_label}. Skanowanie duplikatów jest już w trakcie — "
            "wyniki uwzględnią reset po jego zakończeniu.",
        )
        return

    pbn_data_fresh, pbn_stale_message, _ = is_pbn_people_data_fresh()
    if not pbn_data_fresh:
        messages.warning(
            request,
            f"{reset_label}. Nie udało się automatycznie uruchomić skanowania "
            f"({pbn_stale_message}); uruchom je ręcznie po pobraniu danych PBN.",
        )
        return

    scan_for_duplicates.delay(user_id=request.user.pk)
    messages.success(
        request,
        f"{reset_label}. Uruchomiono nowe skanowanie duplikatów w tle — "
        "odśwież stronę za chwilę, aby zobaczyć postęp.",
    )


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def reset_ignored_scientists(request):
    """Remove all IgnoredScientist (PBN) markings and re-trigger scan."""
    count = IgnoredScientist.objects.count()
    IgnoredScientist.objects.all().delete()
    _trigger_rescan_after_reset(
        request, f"Zresetowano {count} ignorowanych autorów (PBN)"
    )
    return redirect("deduplikator_autorow:duplicate_authors")


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def reset_ignored_autorzy(request):
    """Remove all IgnoredAuthor (BPP) markings and re-trigger scan."""
    count = IgnoredAuthor.objects.count()
    IgnoredAuthor.objects.all().delete()
    _trigger_rescan_after_reset(
        request, f"Zresetowano {count} ignorowanych autorów (BPP)"
    )
    return redirect("deduplikator_autorow:duplicate_authors")
