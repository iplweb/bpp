import sys
import traceback
from functools import wraps

import rollbar
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor
from bpp.models.cache import Rekord
from pbn_api.models import Scientist
from pbn_downloader_app.models import PbnDownloadTask

from .models import IgnoredAuthor, LogScalania, NotADuplicate
from .utils import (
    analiza_duplikatow,
    count_authors_with_duplicates,
    count_authors_with_lastname,
    export_duplicates_to_xlsx,
    scal_autorow,
    search_author_by_lastname,
    znajdz_pierwszego_autora_z_duplikatami,
)

# Minimalny próg pewności do wyświetlania duplikatów
# Duplikaty z pewnością poniżej tego progu nie będą pokazywane
MIN_PEWNOSC_DO_WYSWIETLENIA = 50


def group_required(group_name):
    """
    Decorator that requires user to be logged in and belong to a specific group.
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if (
                not request.user.is_superuser
                and not request.user.groups.filter(name=group_name).exists()
            ):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def _get_excluded_authors_from_session(request):
    """Get excluded authors from session as Scientist objects."""
    skipped_authors_ids = request.session.get("skipped_authors", [])
    if skipped_authors_ids:
        return list(Scientist.objects.filter(pk__in=skipped_authors_ids))
    return []


def _handle_search_request(search_lastname):
    """Handle search request and return scientist and count."""
    scientist = search_author_by_lastname(search_lastname, excluded_authors=None)
    search_results_count = count_authors_with_lastname(search_lastname)
    return scientist, search_results_count


def _clear_navigation_session(request):
    """Clear skipped authors and navigation history from session."""
    if "skipped_authors" in request.session:
        del request.session["skipped_authors"]
    if "navigation_history" in request.session:
        del request.session["navigation_history"]
    request.session.modified = True


def _handle_go_previous(request, navigation_history, excluded_authors):
    """Handle 'go previous' navigation action."""
    if not navigation_history:
        return znajdz_pierwszego_autora_z_duplikatami(excluded_authors)

    previous_scientist_id = navigation_history.pop()
    request.session["navigation_history"] = navigation_history
    request.session.modified = True

    try:
        return Scientist.objects.get(pk=previous_scientist_id)
    except Scientist.DoesNotExist:
        return znajdz_pierwszego_autora_z_duplikatami(excluded_authors)


def _handle_skip_current(request, scientist, excluded_authors):
    """Handle 'skip current' navigation action."""
    if not scientist:
        return scientist

    # Save to navigation history
    if "navigation_history" not in request.session:
        request.session["navigation_history"] = []
    request.session["navigation_history"].append(scientist.pk)

    # Add to skipped
    if "skipped_authors" not in request.session:
        request.session["skipped_authors"] = []
    if scientist.pk not in request.session["skipped_authors"]:
        request.session["skipped_authors"].append(scientist.pk)
    request.session.modified = True

    # Find next author
    excluded_authors.append(scientist)
    return znajdz_pierwszego_autora_z_duplikatami(excluded_authors)


def _calculate_year_range(queryset):
    """Calculate year range from a queryset with 'rok' field."""
    lata = queryset.filter(rok__isnull=False).values_list("rok", flat=True)
    if not lata:
        return None

    min_rok = min(lata)
    max_rok = max(lata)
    if min_rok == max_rok:
        return str(min_rok)
    return f"{min_rok}-{max_rok}"


def _build_duplicate_publication_data(autor, metryka):
    """Build publication data for a duplicate author."""
    publikacje = Rekord.objects.prace_autora(autor)[:500]
    publikacje_count = Rekord.objects.prace_autora(autor).count()
    year_range = _calculate_year_range(Rekord.objects.prace_autora(autor))

    return {
        "autor": autor,
        "publikacje": publikacje,
        "publikacje_count": publikacje_count,
        "publikacje_year_range": year_range,
    }


def _add_dyscypliny_to_duplicates(duplikaty_z_publikacjami):
    """Add discipline information to duplicate authors."""
    from bpp.models import Autor_Dyscyplina

    for duplikat_data in duplikaty_z_publikacjami:
        duplikat_data["dyscypliny"] = (
            Autor_Dyscyplina.objects.filter(
                autor=duplikat_data["autor"], rok__gte=2022, rok__lte=2025
            )
            .select_related("dyscyplina_naukowa", "subdyscyplina_naukowa")
            .order_by("rok")
        )


@group_required(GR_WPROWADZANIE_DANYCH)
def duplicate_authors_view(request):  # noqa: C901
    """
    Widok pokazujący główny rekord autora wraz z możliwymi duplikatami
    i ich publikacjami (do 50 na duplikat).
    """
    # Pobierz parametr wyszukiwania
    search_lastname = request.GET.get("search_lastname", "").strip()

    # Pobierz historię nawigacji i pominiętych autorów
    navigation_history = request.session.get("navigation_history", [])
    excluded_authors = _get_excluded_authors_from_session(request)

    # Jeśli podano wyszukiwanie, szukaj konkretnego autora
    if search_lastname:
        scientist, search_results_count = _handle_search_request(search_lastname)
        _clear_navigation_session(request)
        navigation_history = []
        excluded_authors = []
    else:
        scientist = znajdz_pierwszego_autora_z_duplikatami(excluded_authors)
        search_results_count = None

    # Obsługa nawigacji wstecz
    if request.GET.get("go_previous"):
        scientist = _handle_go_previous(request, navigation_history, excluded_authors)

    # Jeśli pominięto poprzedniego autora, zapisz go w sesji
    elif request.GET.get("skip_current"):
        scientist = _handle_skip_current(request, scientist, excluded_authors)

    # Policz całkowitą liczbę autorów z duplikatami
    total_authors_with_duplicates = count_authors_with_duplicates()

    # Policz liczbę autorów oznaczonych jako nie-duplikat
    not_duplicate_count = NotADuplicate.objects.count()

    # Policz liczbę ignorowanych autorów
    ignored_authors_count = IgnoredAuthor.objects.count()

    # Get latest PBN download task
    latest_pbn_download = PbnDownloadTask.get_latest_task()

    # Get recent merge logs for current user
    recent_merges = (
        LogScalania.objects.filter(created_by=request.user)
        .select_related("main_autor", "dyscyplina_before", "dyscyplina_after")
        .order_by("-created_on")[:10]
    )

    context = {
        "scientist": scientist,
        "glowny_autor": None,
        "latest_pbn_download": latest_pbn_download,
        "duplikaty_z_publikacjami": [],
        "analiza": None,
        "has_skipped_authors": len(request.session.get("skipped_authors", [])) > 0,
        "has_previous_authors": len(request.session.get("navigation_history", [])) > 0,
        "total_authors_with_duplicates": total_authors_with_duplicates,
        "not_duplicate_count": not_duplicate_count,
        "ignored_authors_count": ignored_authors_count,
        "search_lastname": search_lastname,
        "search_results_count": search_results_count,
        "recent_merges": recent_merges,
    }

    if scientist:
        # Pobierz szczegółową analizę duplikatów
        analiza_result = analiza_duplikatow(scientist.osobazinstytucji)

        if "error" not in analiza_result:
            context["glowny_autor"] = analiza_result["glowny_autor"]
            context["analiza"] = analiza_result["analiza"]

            # Dla każdego duplikatu pobierz publikacje (do 500)
            # Filtruj tylko duplikaty z pewnością >= MIN_PEWNOSC_DO_WYSWIETLENIA
            duplikaty_z_publikacjami = []
            for duplikat_info in analiza_result["analiza"]:
                # Pomiń duplikaty z niską pewnością
                if duplikat_info["pewnosc"] < MIN_PEWNOSC_DO_WYSWIETLENIA:
                    continue

                autor_duplikat = duplikat_info["autor"]
                pub_data = _build_duplicate_publication_data(
                    autor_duplikat, duplikat_info
                )
                pub_data["analiza"] = duplikat_info
                duplikaty_z_publikacjami.append(pub_data)

            context["duplikaty_z_publikacjami"] = duplikaty_z_publikacjami

            # Jeśli lista duplikatów jest pusta, przejdź automatycznie do następnego autora
            if not duplikaty_z_publikacjami:
                # Dodaj do pominiętych
                if "skipped_authors" not in request.session:
                    request.session["skipped_authors"] = []
                if scientist.pk not in request.session["skipped_authors"]:
                    request.session["skipped_authors"].append(scientist.pk)
                request.session.modified = True

                # Komunikat
                messages.info(
                    request,
                    f"Autor {context['glowny_autor']} nie ma już duplikatów do scalenia. "
                    f"Przechodzę do następnego autora.",
                )

                # Redirect do siebie - znajdzie kolejnego autora
                return redirect("deduplikator_autorow:duplicate_authors")

            # Pobierz publikacje głównego autora (do 500)
            if context["glowny_autor"]:
                from bpp.models import Autor_Dyscyplina

                # Pobierz dyscypliny głównego autora dla lat 2022-2025
                context["glowny_autor_dyscypliny"] = (
                    Autor_Dyscyplina.objects.filter(
                        autor=context["glowny_autor"], rok__gte=2022, rok__lte=2025
                    )
                    .select_related("dyscyplina_naukowa", "subdyscyplina_naukowa")
                    .order_by("rok")
                )

                # Pobierz dyscypliny dla każdego duplikatu
                _add_dyscypliny_to_duplicates(duplikaty_z_publikacjami)

                # Pobierz publikacje głównego autora
                glowny_autor_qs = Rekord.objects.prace_autora(context["glowny_autor"])
                context["glowne_publikacje"] = glowny_autor_qs[:500]
                context["glowne_publikacje_count"] = glowny_autor_qs.count()
                context["glowne_publikacje_year_range"] = _calculate_year_range(
                    glowny_autor_qs
                )

    return render(request, "deduplikator_autorow/duplicate_authors.html", context)


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["GET", "POST"])
def scal_autorow_view(request):
    """
    Widok do scalania autorów automatycznie.

    Przyjmuje parametry:
    - main_scientist_id: ID głównego autora (Scientist)
    - duplicate_scientist_id: ID duplikatu autora (Scientist)
    - skip_pbn: Opcjonalnie, jeśli true nie wysyła publikacji do PBN

    Zwraca wynik operacji w formacie JSON.
    """
    if request.method == "GET":
        main_scientist_id = request.GET.get("main_scientist_id")
        duplicate_scientist_id = request.GET.get("duplicate_scientist_id")
        skip_pbn = request.GET.get("skip_pbn", "false").lower() == "true"
    else:
        main_scientist_id = request.POST.get("main_scientist_id")
        duplicate_scientist_id = request.POST.get("duplicate_scientist_id")
        skip_pbn = request.POST.get("skip_pbn", "false").lower() == "true"

    if not main_scientist_id or not duplicate_scientist_id:
        return JsonResponse(
            {
                "success": False,
                "error": "Brak wymaganych parametrów: main_scientist_id i duplicate_scientist_id",
            },
            status=400,
        )

    try:
        result = scal_autorow(
            main_scientist_id, duplicate_scientist_id, request.user, skip_pbn=skip_pbn
        )
        return JsonResponse({"success": result.get("success", False), "result": result})
    except NotImplementedError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=501)
    except Exception as e:
        traceback.print_exc()
        rollbar.report_exc_info(sys.exc_info())
        return JsonResponse(
            {"success": False, "error": f"Błąd podczas scalania autorów: {str(e)}"},
            status=500,
        )


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def mark_non_duplicate(request):
    """
    Widok do oznaczania autora jako nie-duplikatu.

    Przyjmuje parametry:
    - scientist_pk: Primary key Scientist do zapisania jako nie-duplikat

    Zapisuje w modelu NotADuplicate i przekierowuje do następnego autora.
    """
    scientist_pk = request.POST.get("scientist_pk")

    if not scientist_pk:
        messages.error(request, "Brak wymaganego parametru: scientist_pk")
        return redirect("deduplikator_autorow:duplicate_authors")

    try:
        # Sprawdź czy Scientist istnieje
        autor = Autor.objects.get(pk=scientist_pk)

        # Zapisz jako nie-duplikat (get_or_create zapobiega duplikatom)
        not_duplicate, created = NotADuplicate.objects.update_or_create(
            autor=autor, defaults=dict(created_by=request.user)
        )

        if created:
            messages.success(request, f"Autor {autor} oznaczony jako nie-duplikat.")
        else:
            messages.info(
                request, f"Autor {autor} był już oznaczony jako nie-duplikat."
            )

    except Autor.DoesNotExist:
        messages.error(request, "Nie znaleziono autora o podanym ID.")
    except Exception as e:
        messages.error(request, f"Błąd podczas oznaczania autora: {str(e)}")

    # Przekieruj do następnego autora z duplikatami
    return redirect("deduplikator_autorow:duplicate_authors")


@group_required(GR_WPROWADZANIE_DANYCH)
def reset_skipped_authors(request):
    """
    Widok do resetowania listy pominiętych autorów i rozpoczęcia od początku.
    """
    # Wyczyść sesję z pominiętymi autorami i historią nawigacji
    session_keys_to_clear = ["skipped_authors", "navigation_history"]
    cleared_any = False

    for key in session_keys_to_clear:
        if key in request.session:
            del request.session[key]
            cleared_any = True

    if cleared_any:
        request.session.modified = True
        messages.success(
            request,
            "Lista pominiętych autorów i historia nawigacji zostały wyczyszczone. Rozpoczynasz od początku.",
        )

    return redirect("deduplikator_autorow:duplicate_authors")


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
                request, f"Autor {scientist} jest już oznaczony jako ignorowany."
            )
        else:
            # Get the BPP author if available
            autor = None
            if hasattr(scientist, "rekord_w_bpp"):
                autor = scientist.rekord_w_bpp

            IgnoredAuthor.objects.create(
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
def reset_ignored_authors(request):
    """
    Remove all ignored author markings.
    """
    count = IgnoredAuthor.objects.count()
    IgnoredAuthor.objects.all().delete()
    messages.success(request, f"Zresetowano {count} ignorowanych autorów.")
    return redirect("deduplikator_autorow:duplicate_authors")


@group_required(GR_WPROWADZANIE_DANYCH)
def reset_not_duplicates(request):
    """
    Widok do resetowania (usuwania) wszystkich rekordów NotADuplicate.
    """
    if request.method == "POST":
        count = NotADuplicate.objects.count()
        NotADuplicate.objects.all().delete()
        messages.success(
            request,
            f"Zresetowano {count} autorów oznaczonych jako nie-duplikat.",
        )
    return redirect("deduplikator_autorow:duplicate_authors")


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


@group_required(GR_WPROWADZANIE_DANYCH)
def download_duplicates_xlsx(request):
    """
    Widok do pobierania listy duplikatów w formacie XLSX.

    Generuje plik XLSX ze wszystkimi autorami z duplikatami,
    zawierający głównego autora, jego PBN UID, duplikat i jego PBN UID.
    """
    import datetime

    from django.http import HttpResponse

    try:
        # Generuj plik XLSX
        xlsx_content = export_duplicates_to_xlsx()

        # Stwórz odpowiedź HTTP z plikiem
        response = HttpResponse(
            xlsx_content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # Nazwa pliku z datą
        filename = (
            f"duplikaty_autorow_{datetime.date.today().strftime('%Y-%m-%d')}.xlsx"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        rollbar.report_exc_info(sys.exc_info())
        messages.error(request, f"Błąd podczas generowania pliku XLSX: {str(e)}")
        return redirect("deduplikator_autorow:duplicate_authors")
