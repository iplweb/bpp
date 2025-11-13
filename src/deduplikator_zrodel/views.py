from cacheops import invalidate_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Zrodlo
from django_bpp.version import VERSION

from .models import IgnoredSource, NotADuplicate
from .utils import (
    analiza_duplikatow,
    policz_zrodla_z_duplikatami,
    znajdz_pierwszego_zrodlo_z_duplikatami,
)


def group_required(*group_names):
    """Decorator sprawdzający czy użytkownik należy do wymaganych grup"""

    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(
                    request, "Musisz być zalogowany, aby uzyskać dostęp do tej strony."
                )
                return redirect("login")

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            user_groups = request.user.groups.values_list("name", flat=True)
            if any(group in user_groups for group in group_names):
                return view_func(request, *args, **kwargs)

            messages.error(request, "Nie masz uprawnień do tej strony.")
            return redirect("bpp:index")

        return wrapper

    return decorator


@login_required
@group_required(GR_WPROWADZANIE_DANYCH)
def duplicate_sources_view(request):
    """Główny widok deduplikatora źródeł"""

    # Pobierz listę pominiętych źródeł z sesji
    skipped_sources = request.session.get("skipped_sources", [])

    # Znajdź pierwsze źródło z duplikatami
    zrodlo = znajdz_pierwszego_zrodlo_z_duplikatami(excluded_ids=skipped_sources)

    if not zrodlo:
        # Brak źródeł do deduplikacji
        return render(
            request,
            "deduplikator_zrodel/duplicate_sources.html",
            {
                "zrodlo": None,
                "duplikaty": [],
                "total_sources_with_duplicates": 0,
                "bpp_version": VERSION,
            },
        )

    # Analizuj duplikaty
    duplikaty = analiza_duplikatow(zrodlo)

    # Jeśli lista duplikatów jest pusta, przejdź automatycznie do następnego źródła
    if not duplikaty:
        # Dodaj do pominiętych
        if "skipped_sources" not in request.session:
            request.session["skipped_sources"] = []
        if zrodlo.pk not in request.session["skipped_sources"]:
            request.session["skipped_sources"].append(zrodlo.pk)
        request.session.modified = True

        # Komunikat
        messages.info(
            request,
            f"Źródło {zrodlo.nazwa} nie ma już duplikatów do sprawdzenia. "
            f"Przechodzę do następnego źródła.",
        )

        # Redirect do siebie - znajdzie kolejne źródło
        return redirect("deduplikator_zrodel:duplicate_sources")

    # Przygotuj dane dla szablonu
    duplikaty_z_danymi = []
    for kandydat, score in duplikaty:
        # Pobierz dane PBN jeśli istnieją
        pbn_data = None
        mnisw_id = None
        if kandydat.pbn_uid:
            pbn_data = {
                "issn": kandydat.pbn_uid.issn,
                "e_issn": kandydat.pbn_uid.eissn,
                "title": kandydat.pbn_uid.title,
            }
            mnisw_id = kandydat.pbn_uid.mniswId

        # Zbuduj URL przemapowania z parametrem GET źródła docelowego
        przemapuj_base_url = reverse(
            "przemapuj_zrodlo:przemapuj", kwargs={"slug": kandydat.slug}
        )
        przemapuj_url = f"{przemapuj_base_url}?zrodlo_docelowe={zrodlo.pk}"

        duplikaty_z_danymi.append(
            {
                "zrodlo": kandydat,
                "score": score,
                "pbn_data": pbn_data,
                "mnisw_id": mnisw_id,
                "przemapuj_url": przemapuj_url,
            }
        )

    # Dane PBN dla głównego źródła
    main_pbn_data = None
    main_mnisw_id = None
    if zrodlo.pbn_uid:
        main_pbn_data = {
            "issn": zrodlo.pbn_uid.issn,
            "e_issn": zrodlo.pbn_uid.eissn,
            "title": zrodlo.pbn_uid.title,
        }
        main_mnisw_id = zrodlo.pbn_uid.mniswId

    # Policz przybliżoną liczbę źródeł z duplikatami
    total_with_duplicates = policz_zrodla_z_duplikatami()

    context = {
        "zrodlo": zrodlo,
        "duplikaty": duplikaty_z_danymi,
        "main_pbn_data": main_pbn_data,
        "main_mnisw_id": main_mnisw_id,
        "total_sources_with_duplicates": total_with_duplicates,
        "skipped_count": len(skipped_sources),
        "bpp_version": VERSION,
    }

    return render(request, "deduplikator_zrodel/duplicate_sources.html", context)


@login_required
@group_required(GR_WPROWADZANIE_DANYCH)
@require_POST
def mark_non_duplicate(request):
    """Oznacza parę źródeł jako 'to nie duplikat'"""

    zrodlo_id = request.POST.get("zrodlo_id")
    duplikat_id = request.POST.get("duplikat_id")

    if not zrodlo_id or not duplikat_id:
        messages.error(request, "Brak wymaganych parametrów.")
        return redirect("deduplikator_zrodel:duplicate_sources")

    try:
        zrodlo = get_object_or_404(Zrodlo, pk=zrodlo_id)
        duplikat = get_object_or_404(Zrodlo, pk=duplikat_id)

        with transaction.atomic():
            # Utwórz wpis NotADuplicate (w obie strony dla pewności)
            NotADuplicate.objects.get_or_create(
                zrodlo=zrodlo, duplikat=duplikat, defaults={"created_by": request.user}
            )
            NotADuplicate.objects.get_or_create(
                zrodlo=duplikat, duplikat=zrodlo, defaults={"created_by": request.user}
            )

        # Unieważnij cache aby natychmiast pokazać zmiany
        invalidate_model(Zrodlo)

        messages.success(
            request,
            f"Oznaczono że '{zrodlo.nazwa}' i '{duplikat.nazwa}' to nie są duplikaty.",
        )

    except Zrodlo.DoesNotExist:
        messages.error(request, "Nie znaleziono źródła o podanym ID.")

    return redirect("deduplikator_zrodel:duplicate_sources")


@login_required
@group_required(GR_WPROWADZANIE_DANYCH)
@require_POST
def ignore_source(request):
    """Dodaje źródło do listy ignorowanych w deduplikacji"""

    zrodlo_id = request.POST.get("zrodlo_id")
    reason = request.POST.get("reason", "")

    if not zrodlo_id:
        messages.error(request, "Brak ID źródła.")
        return redirect("deduplikator_zrodel:duplicate_sources")

    try:
        zrodlo = get_object_or_404(Zrodlo, pk=zrodlo_id)

        IgnoredSource.objects.get_or_create(
            zrodlo=zrodlo, defaults={"reason": reason, "created_by": request.user}
        )

        # Unieważnij cache aby natychmiast pokazać zmiany
        invalidate_model(Zrodlo)

        messages.success(
            request, f"Źródło '{zrodlo.nazwa}' zostało dodane do listy ignorowanych."
        )

        # Usuń z sesyjnej listy pominiętych jeśli tam jest
        if (
            "skipped_sources" in request.session
            and zrodlo.pk in request.session["skipped_sources"]
        ):
            request.session["skipped_sources"].remove(zrodlo.pk)
            request.session.modified = True

    except Zrodlo.DoesNotExist:
        messages.error(request, "Nie znaleziono źródła o podanym ID.")

    return redirect("deduplikator_zrodel:duplicate_sources")


@login_required
@group_required(GR_WPROWADZANIE_DANYCH)
def skip_current(request):
    """Pomija bieżące źródło i przechodzi do następnego"""

    zrodlo_id = request.GET.get("zrodlo_id")

    if zrodlo_id:
        if "skipped_sources" not in request.session:
            request.session["skipped_sources"] = []

        try:
            zrodlo_id = int(zrodlo_id)
            if zrodlo_id not in request.session["skipped_sources"]:
                request.session["skipped_sources"].append(zrodlo_id)
                request.session.modified = True
                messages.info(request, "Pominięto bieżące źródło.")
        except (ValueError, TypeError):
            messages.error(request, "Nieprawidłowy ID źródła.")

    return redirect("deduplikator_zrodel:duplicate_sources")


@login_required
@group_required(GR_WPROWADZANIE_DANYCH)
def go_previous(request):
    """Cofa się do poprzedniego źródła"""

    if "skipped_sources" in request.session and request.session["skipped_sources"]:
        # Usuń ostatnie źródło z listy pominiętych
        request.session["skipped_sources"].pop()
        request.session.modified = True
        messages.info(request, "Cofnięto do poprzedniego źródła.")
    else:
        messages.warning(request, "Brak poprzednich źródeł do cofnięcia.")

    return redirect("deduplikator_zrodel:duplicate_sources")


@login_required
@group_required(GR_WPROWADZANIE_DANYCH)
def reset_skipped(request):
    """Resetuje listę pominiętych źródeł"""

    if "skipped_sources" in request.session:
        del request.session["skipped_sources"]
        request.session.modified = True

    # Unieważnij cache aby pokazać świeże dane
    invalidate_model(Zrodlo)

    messages.success(request, "Zresetowano listę pominiętych źródeł.")
    return redirect("deduplikator_zrodel:duplicate_sources")


@login_required
@group_required(GR_WPROWADZANIE_DANYCH)
def download_duplicates_xlsx(request):
    """
    Widok do pobierania listy duplikatów źródeł w formacie XLSX.

    Generuje plik XLSX ze wszystkimi źródłami z duplikatami,
    zawierający główne źródło, jego ISSN/E-ISSN, PBN UID, duplikat i jego dane.
    """
    import datetime
    import sys

    import rollbar
    from django.http import HttpResponse

    from .utils import export_duplicates_to_xlsx

    try:
        # Generuj plik XLSX
        xlsx_content = export_duplicates_to_xlsx()

        # Stwórz odpowiedź HTTP z plikiem
        response = HttpResponse(
            xlsx_content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # Nazwa pliku z datą
        filename = f"duplikaty_zrodel_{datetime.date.today().strftime('%Y-%m-%d')}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        rollbar.report_exc_info(sys.exc_info())
        messages.error(request, f"Błąd podczas generowania pliku XLSX: {str(e)}")
        return redirect("deduplikator_zrodel:duplicate_sources")
