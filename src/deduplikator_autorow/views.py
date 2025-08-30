from functools import wraps

from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from pbn_api.models import Scientist
from pbn_downloader_app.models import PbnDownloadTask
from .models import NotADuplicate
from .utils import (
    analiza_duplikatow,
    count_authors_with_duplicates,
    count_authors_with_lastname,
    export_duplicates_to_xlsx,
    scal_autorow,
    search_author_by_lastname,
    znajdz_pierwszego_autora_z_duplikatami,
)

from django.contrib import messages
from django.contrib.auth.decorators import login_required

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor
from bpp.models.cache import Rekord


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


@group_required(GR_WPROWADZANIE_DANYCH)
def duplicate_authors_view(request):
    """
    Widok pokazujący główny rekord autora wraz z możliwymi duplikatami
    i ich publikacjami (do 50 na duplikat).
    """
    # Pobierz parametr wyszukiwania
    search_lastname = request.GET.get("search_lastname", "").strip()

    # Pobierz pominiętych autorów z sesji
    skipped_authors_ids = request.session.get("skipped_authors", [])
    # Pobierz historię nawigacji
    navigation_history = request.session.get("navigation_history", [])

    # Konwertuj ID na obiekty Scientist dla wykluczenia
    excluded_authors = []
    if skipped_authors_ids:
        excluded_authors = list(Scientist.objects.filter(pk__in=skipped_authors_ids))

    # Jeśli podano wyszukiwanie, szukaj konkretnego autora
    if search_lastname:
        scientist = search_author_by_lastname(search_lastname, excluded_authors)
        search_results_count = count_authors_with_lastname(search_lastname)
    else:
        # Znajdź pierwszego autora z duplikatami, wykluczając pominiętych
        scientist = znajdz_pierwszego_autora_z_duplikatami(excluded_authors)
        search_results_count = None

    # Obsługa nawigacji wstecz
    if request.GET.get("go_previous") and navigation_history:
        # Usuń ostatni element z historii i wróć do niego
        previous_scientist_id = navigation_history.pop()
        request.session["navigation_history"] = navigation_history
        request.session.modified = True
        try:
            scientist = Scientist.objects.get(pk=previous_scientist_id)
        except Scientist.DoesNotExist:
            # Jeśli autor nie istnieje, znajdź następnego
            scientist = znajdz_pierwszego_autora_z_duplikatami(excluded_authors)

    # Jeśli pominięto poprzedniego autora, zapisz go w sesji
    elif request.GET.get("skip_current") and scientist:
        # Zapisz obecnego autora w historii nawigacji
        if "navigation_history" not in request.session:
            request.session["navigation_history"] = []
        request.session["navigation_history"].append(scientist.pk)

        # Dodaj do pominiętych
        if "skipped_authors" not in request.session:
            request.session["skipped_authors"] = []
        if scientist.pk not in request.session["skipped_authors"]:
            request.session["skipped_authors"].append(scientist.pk)
        request.session.modified = True
        # Znajdź następnego autora
        excluded_authors.append(scientist)
        scientist = znajdz_pierwszego_autora_z_duplikatami(excluded_authors)

    # Policz całkowitą liczbę autorów z duplikatami
    total_authors_with_duplicates = count_authors_with_duplicates()

    # Policz liczbę autorów oznaczonych jako nie-duplikat
    not_duplicate_count = NotADuplicate.objects.count()

    # Get latest PBN download task
    latest_pbn_download = PbnDownloadTask.get_latest_task()

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
        "search_lastname": search_lastname,
        "search_results_count": search_results_count,
    }

    if scientist:
        # Pobierz szczegółową analizę duplikatów
        analiza_result = analiza_duplikatow(scientist.osobazinstytucji)

        if "error" not in analiza_result:
            context["glowny_autor"] = analiza_result["glowny_autor"]
            context["analiza"] = analiza_result["analiza"]

            # Dla każdego duplikatu pobierz publikacje (do 50)
            duplikaty_z_publikacjami = []
            for duplikat_info in analiza_result["analiza"]:
                autor_duplikat = duplikat_info["autor"]

                # # Sprawdź czy autor nie jest oznaczony jako nie-duplikat
                # # Znajdź odpowiadający Scientist przez rekord BPP
                # scientist_for_author = None
                # try:
                #     # Znajdź Scientist który ma ten autor jako rekord_w_bpp
                #     scientist_for_author = Scientist.objects.filter(
                #         rekord_w_bpp=autor_duplikat
                #     ).first()
                # except:
                #     pass
                #
                # Pobierz publikacje tego autora (ograniczenie do 500)
                publikacje = Rekord.objects.prace_autora(autor_duplikat)[:500]

                # Oblicz zakres lat publikacji duplikatu
                duplikat_lata = (
                    Rekord.objects.prace_autora(autor_duplikat)
                    .filter(rok__isnull=False)
                    .values_list("rok", flat=True)
                )

                duplikat_year_range = None
                if duplikat_lata:
                    min_rok = min(duplikat_lata)
                    max_rok = max(duplikat_lata)
                    if min_rok == max_rok:
                        duplikat_year_range = str(min_rok)
                    else:
                        duplikat_year_range = f"{min_rok}-{max_rok}"

                duplikaty_z_publikacjami.append(
                    {
                        "autor": autor_duplikat,
                        "analiza": duplikat_info,
                        "publikacje": publikacje,
                        "publikacje_count": Rekord.objects.prace_autora(
                            autor_duplikat
                        ).count(),
                        "publikacje_year_range": duplikat_year_range,
                    }
                )

            context["duplikaty_z_publikacjami"] = duplikaty_z_publikacjami

            # Pobierz publikacje głównego autora (do 500)
            if context["glowny_autor"]:
                glowne_publikacje = Rekord.objects.prace_autora(
                    context["glowny_autor"]
                )[:500]
                context["glowne_publikacje"] = glowne_publikacje
                context["glowne_publikacje_count"] = Rekord.objects.prace_autora(
                    context["glowny_autor"]
                ).count()

                # Oblicz zakres lat publikacji głównego autora
                glowne_lata = (
                    Rekord.objects.prace_autora(context["glowny_autor"])
                    .filter(rok__isnull=False)
                    .values_list("rok", flat=True)
                )

                if glowne_lata:
                    min_rok = min(glowne_lata)
                    max_rok = max(glowne_lata)
                    if min_rok == max_rok:
                        context["glowne_publikacje_year_range"] = str(min_rok)
                    else:
                        context["glowne_publikacje_year_range"] = f"{min_rok}-{max_rok}"
                else:
                    context["glowne_publikacje_year_range"] = None

    return render(request, "deduplikator_autorow/duplicate_authors.html", context)


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["GET", "POST"])
def scal_autorow_view(request):
    """
    Widok do scalania autorów automatycznie.

    Przyjmuje parametry:
    - main_scientist_id: ID głównego autora (Scientist)
    - duplicate_scientist_id: ID duplikatu autora (Scientist)

    Zwraca wynik operacji w formacie JSON.
    """
    if request.method == "GET":
        main_scientist_id = request.GET.get("main_scientist_id")
        duplicate_scientist_id = request.GET.get("duplicate_scientist_id")
    else:
        main_scientist_id = request.POST.get("main_scientist_id")
        duplicate_scientist_id = request.POST.get("duplicate_scientist_id")

    if not main_scientist_id or not duplicate_scientist_id:
        return JsonResponse(
            {
                "success": False,
                "error": "Brak wymaganych parametrów: main_scientist_id i duplicate_scientist_id",
            },
            status=400,
        )

    try:
        result = scal_autorow(main_scientist_id, duplicate_scientist_id, request.user)
        return JsonResponse({"success": result.get("success", False), "result": result})
    except NotImplementedError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=501)
    except Exception as e:
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

    except Scientist.DoesNotExist:
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
        messages.error(request, f"Błąd podczas generowania pliku XLSX: {str(e)}")
        return redirect("deduplikator_autorow:duplicate_authors")
