from datetime import datetime

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.http import urlencode
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView, TemplateView, View

from bpp.models import Autor, Tytul, Uczelnia
from import_common.core import matchuj_autora
from pbn_api.models import Scientist
from pbn_downloader_app.freshness import is_pbn_people_data_fresh

from .core import get_cache_status
from .models import CachedScientistMatch, DoNotRemind, MatchCacheRebuildOperation


@method_decorator(staff_member_required, name="dispatch")
class ImporterAutorowPBNView(ListView):
    """Main view for matching PBN Scientists to BPP Autors"""

    template_name = "importer_autorow_pbn/main.html"
    context_object_name = "scientists"
    paginate_by = 50

    def dispatch(self, request, *args, **kwargs):
        """Check cache validity before processing the request"""
        is_valid, _, message = get_cache_status()
        if not is_valid:
            messages.warning(
                request,
                f"Cache dopasowań jest nieaktualny: {message}. "
                "Proszę przebudować cache przed kontynuowaniem.",
            )
            return HttpResponseRedirect(reverse("importer_autorow_pbn:rebuild"))
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        """Get Scientists without BPP equivalents, excluding ignored ones"""
        # Get all mongoIds from Autor table where pbn_uid_id is not null
        bpp_autor_pbn_uids = set(
            Autor.objects.exclude(pbn_uid_id__isnull=True).values_list(
                "pbn_uid_id", flat=True
            )
        )

        # Get ignored scientist IDs
        ignored_scientist_ids = DoNotRemind.objects.values_list(
            "scientist_id", flat=True
        )

        # Get Scientists from institution API that are not in BPP and not ignored
        queryset = (
            Scientist.objects.filter(from_institution_api=True)
            .exclude(mongoId__in=bpp_autor_pbn_uids)
            .exclude(mongoId__in=ignored_scientist_ids)
        )

        # Filter: only scientists from our institution (DEFAULT: ON)
        # When "pokaz_wszystkich" param is set to "1", show all
        pokaz_wszystkich = self.request.GET.get("pokaz_wszystkich", "0")
        if pokaz_wszystkich != "1":
            uczelnia = Uczelnia.objects.default
            if uczelnia and uczelnia.pbn_uid_id:
                # Filter by institution ID in currentEmployments JSON
                queryset = queryset.filter(
                    versions__0__object__currentEmployments__contains=[
                        {"institutionId": str(uczelnia.pbn_uid_id)}
                    ]
                )

        # Search functionality
        query = self.request.GET.get("q", "")
        if query:
            queryset = queryset.filter(
                models.Q(lastName__icontains=query)
                | models.Q(name__icontains=query)
                | models.Q(orcid__icontains=query)
            )

        return queryset.order_by("lastName", "name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["pokaz_wszystkich"] = self.request.GET.get("pokaz_wszystkich", "0")

        # Get scientist IDs on current page for batch cache lookup
        scientist_ids = [s.pk for s in context["scientists"]]

        # Fetch cached matches for current page in one query
        cached_matches = {
            cm.scientist_id: cm.matched_autor
            for cm in CachedScientistMatch.objects.filter(
                scientist_id__in=scientist_ids
            ).select_related("matched_autor")
        }

        # Add match suggestions for each scientist from cache
        matches_count = 0
        for scientist in context["scientists"]:
            scientist.match_suggestion = cached_matches.get(scientist.pk)
            scientist.create_url = self._get_create_url(scientist)
            if scientist.match_suggestion:
                matches_count += 1

        # Get total matches using cache (fast COUNT query)
        queryset = self.get_queryset()
        total_unmatched = queryset.count()

        # Count matches from cache for scientists in our queryset
        total_with_matches = CachedScientistMatch.objects.filter(
            scientist_id__in=queryset.values_list("mongoId", flat=True),
            matched_autor__isnull=False,
        ).count()

        total_ignored = DoNotRemind.objects.count()

        # Check PBN people data freshness
        pbn_data_fresh, pbn_stale_message, pbn_last_download = (
            is_pbn_people_data_fresh()
        )

        # Get cache status for display
        cache_is_valid, cache_last_computed, _ = get_cache_status()

        context.update(
            {
                "total_unmatched": total_unmatched,
                "total_ignored": total_ignored,
                "matches_count": matches_count,  # Matches on current page
                "total_with_matches": total_with_matches,  # Total matches across all pages
                "pbn_data_fresh": pbn_data_fresh,
                "pbn_stale_message": pbn_stale_message,
                "pbn_last_download": pbn_last_download,
                "cache_is_valid": cache_is_valid,
                "cache_last_computed": cache_last_computed,
            }
        )

        return context

    def _find_match(self, scientist):
        """Try to find a matching Autor using matchuj_autora"""
        # Extract data from scientist - these are direct model fields
        imiona = scientist.name
        nazwisko = scientist.lastName
        orcid = scientist.orcid

        # Get legacy identifiers from object field if available
        pbn_id = None
        legacy_ids = scientist.value("object", "legacyIdentifiers", return_none=True)
        if legacy_ids:
            pbn_id = legacy_ids[0] if legacy_ids else None

        # Try to match
        autor = matchuj_autora(
            imiona=imiona,
            nazwisko=nazwisko,
            orcid=orcid,
            pbn_id=pbn_id,
            pbn_uid_id=scientist.pk,
        )

        return autor

    def _get_create_url(self, scientist):
        """Generate URL for creating an Autor in BPP admin"""
        params = self._prepare_autor_params(scientist)
        return reverse("admin:bpp_autor_add") + "?" + urlencode(params)

    def _prepare_autor_params(self, scientist):
        """Prepare parameters for creating an Autor in BPP"""
        params = {}

        # Basic data - these are direct model fields
        if scientist.name:
            params["imiona"] = scientist.name

        if scientist.lastName:
            params["nazwisko"] = scientist.lastName

        if scientist.orcid:
            params["orcid"] = scientist.orcid

        # PBN UID
        params["pbn_uid"] = scientist.pk

        # Academic title
        if scientist.qualifications:
            tytul_id = self._get_tytul_id(scientist.qualifications)
            if tytul_id:
                params["tytul"] = tytul_id

        # Employment data
        self._add_employment_params(scientist, params)

        return params

    def _add_employment_params(self, scientist, params):
        """Add employment-related params if available."""
        employment_data = self._get_employment_data(scientist)
        if not employment_data or not employment_data.get("jednostka_id"):
            return

        params["autor_jednostka_set-0-jednostka"] = employment_data["jednostka_id"]
        self._add_date_param(params, employment_data, "od", "rozpoczal_prace")
        self._add_date_param(params, employment_data, "do", "zakonczyl_prace")

        # Set management form data for inline
        params["autor_jednostka_set-TOTAL_FORMS"] = "1"
        params["autor_jednostka_set-INITIAL_FORMS"] = "0"

    def _add_date_param(self, params, employment_data, date_key, param_suffix):
        """Add a date parameter to params if available."""
        if not employment_data.get(date_key):
            return
        try:
            date_obj = datetime.strptime(employment_data[date_key], "%Y-%m-%d")
            params[f"autor_jednostka_set-0-{param_suffix}"] = date_obj.strftime(
                "%Y-%m-%d"
            )
        except BaseException:
            pass

    def _get_tytul_id(self, qualifications):
        """Get or create Tytul based on qualifications"""
        if not qualifications:
            return None

        try:
            tytul = Tytul.objects.get(skrot=qualifications)
            return tytul.pk
        except Tytul.DoesNotExist:
            # Try to find by name
            try:
                tytul = Tytul.objects.get(nazwa__iexact=qualifications)
                return tytul.pk
            except Tytul.DoesNotExist:
                return None

    def _get_employment_data(self, scientist):
        """Extract employment data from scientist"""
        from bpp.models import Jednostka
        from pbn_api.models import Institution

        current_employments = scientist.value(
            "object", "currentEmployments", return_none=True
        )
        if not current_employments:
            return None

        # Get first employment
        employment = current_employments[0] if current_employments else None
        if not employment:
            return None

        result = {}

        # Try to find the unit
        institution_id = employment.get("institutionId")
        if institution_id:
            try:
                institution = Institution.objects.get(pk=institution_id)  # noqa
                # Try to find corresponding Jednostka
                jednostka = Jednostka.objects.filter(pbn_uid_id=institution_id).first()
                if jednostka:
                    result["jednostka_id"] = jednostka.pk
            except Institution.DoesNotExist:
                pass

        # Dates
        if employment.get("startDate"):
            result["od"] = employment["startDate"]
        if employment.get("endDate"):
            result["do"] = employment["endDate"]

        return result if result else None


@login_required
@staff_member_required
@require_POST
def ignore_scientist(request, scientist_id):
    """AJAX endpoint to ignore a scientist permanently"""
    scientist = get_object_or_404(Scientist, pk=scientist_id)

    # Check if already ignored
    if DoNotRemind.objects.filter(scientist=scientist).exists():
        return JsonResponse({"status": "already_ignored"})

    # Create DoNotRemind entry
    reason = request.POST.get("reason", "")
    DoNotRemind.objects.create(
        scientist=scientist, ignored_by=request.user, reason=reason
    )

    return JsonResponse({"status": "success"})


@login_required
@staff_member_required
@require_POST
def link_scientist(request, scientist_id):
    """AJAX endpoint to link a scientist to an existing Autor"""
    scientist = get_object_or_404(Scientist, pk=scientist_id)
    autor_id = request.POST.get("autor_id")

    if not autor_id:
        return JsonResponse({"status": "error", "message": "No autor_id provided"})

    try:
        autor = Autor.objects.get(pk=autor_id)
    except Autor.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Autor not found"})

    # Check if autor already has a different PBN UID
    if autor.pbn_uid_id and autor.pbn_uid_id != scientist_id:
        return JsonResponse(
            {
                "status": "error",
                "message": f"Autor already linked to different PBN UID: {autor.pbn_uid_id}",
            }
        )

    # Link the scientist to autor
    with transaction.atomic():
        autor.pbn_uid_id = scientist_id
        autor.save()

    messages.success(
        request, f"Pomyślnie powiązano naukowca PBN {scientist} z autorem {autor}"
    )

    return JsonResponse({"status": "success"})


@login_required
@staff_member_required
@require_POST
def link_all_scientists(request):
    """AJAX endpoint to link all scientists with matches to their Autors"""
    view = ImporterAutorowPBNView()
    view.request = request

    # Get all unmatched scientists
    scientists = view.get_queryset()
    scientist_ids = list(scientists.values_list("mongoId", flat=True))

    # Get cached matches in one query
    cached_matches = {
        cm.scientist_id: cm.matched_autor
        for cm in CachedScientistMatch.objects.filter(
            scientist_id__in=scientist_ids, matched_autor__isnull=False
        ).select_related("matched_autor")
    }

    linked_count = 0
    errors = []

    with transaction.atomic():
        for scientist in scientists:
            # Get match from cache
            autor = cached_matches.get(scientist.pk)
            if autor:
                # Check if autor already has a different PBN UID
                if autor.pbn_uid_id and autor.pbn_uid_id != scientist.pk:
                    errors.append(f"{scientist} - autor już powiązany z innym PBN UID")
                    continue

                # Link the scientist to autor
                autor.pbn_uid_id = scientist.pk
                autor.save()
                linked_count += 1

    if linked_count > 0:
        messages.success(
            request, f"Pomyślnie powiązano {linked_count} naukowców PBN z autorami BPP"
        )

    return JsonResponse(
        {"status": "success", "linked_count": linked_count, "errors": errors}
    )


def _prepare_autor_data(scientist, view):
    """Prepare base data dict for creating an Autor."""
    autor_data = {
        "imiona": scientist.name or "",
        "nazwisko": scientist.lastName or "",
        "pbn_uid_id": scientist.pk,
    }

    if scientist.orcid:
        autor_data["orcid"] = scientist.orcid

    if scientist.qualifications:
        tytul_id = view._get_tytul_id(scientist.qualifications)
        if tytul_id:
            autor_data["tytul_id"] = tytul_id

    return autor_data


def _create_autor_jednostka(autor, employment_data):
    """Create Autor_Jednostka if employment data is available."""
    if not employment_data or not employment_data.get("jednostka_id"):
        return

    from bpp.models import Autor_Jednostka

    aj_data = {
        "autor": autor,
        "jednostka_id": employment_data["jednostka_id"],
    }

    for date_key, field_name in [("od", "rozpoczal_prace"), ("do", "zakonczyl_prace")]:
        if employment_data.get(date_key):
            try:
                aj_data[field_name] = datetime.strptime(
                    employment_data[date_key], "%Y-%m-%d"
                ).date()
            except BaseException:
                pass

    Autor_Jednostka.objects.create(**aj_data)


@login_required
@staff_member_required
@require_POST
def create_all_unmatched_scientists(request):
    """AJAX endpoint to create all scientists without matches as new Autors"""

    view = ImporterAutorowPBNView()
    view.request = request

    scientists = view.get_queryset()
    scientist_ids = list(scientists.values_list("mongoId", flat=True))

    # Get cached matches - we only want to create authors for those WITHOUT matches
    scientists_with_matches = set(
        CachedScientistMatch.objects.filter(
            scientist_id__in=scientist_ids, matched_autor__isnull=False
        ).values_list("scientist_id", flat=True)
    )

    created_count = 0
    errors = []

    with transaction.atomic():
        for scientist in scientists:
            # Skip if has a match in cache
            if scientist.pk in scientists_with_matches:
                continue

            try:
                autor_data = _prepare_autor_data(scientist, view)
                autor = Autor.objects.create(**autor_data)
                employment_data = view._get_employment_data(scientist)
                _create_autor_jednostka(autor, employment_data)
                created_count += 1
            except Exception as e:
                errors.append(f"{scientist} - błąd: {str(e)}")

    if created_count > 0:
        messages.success(
            request, f"Pomyślnie utworzono {created_count} nowych autorów w BPP"
        )

    return JsonResponse(
        {"status": "success", "created_count": created_count, "errors": errors}
    )


# ============================================================================
# Cache Rebuild Views
# ============================================================================


@method_decorator(staff_member_required, name="dispatch")
class CacheRebuildView(TemplateView):
    """View for the cache rebuild page with progress tracking"""

    template_name = "importer_autorow_pbn/rebuild_cache.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Check cache status
        is_valid, last_computed, message = get_cache_status()
        context["cache_is_valid"] = is_valid
        context["cache_last_computed"] = last_computed
        context["cache_message"] = message

        # Check for running operation
        running_operation = MatchCacheRebuildOperation.objects.filter(
            started_on__isnull=False, finished_on__isnull=True
        ).first()
        context["running_operation"] = running_operation

        # Get last completed operation
        last_operation = (
            MatchCacheRebuildOperation.objects.filter(finished_on__isnull=False)
            .order_by("-finished_on")
            .first()
        )
        context["last_operation"] = last_operation

        return context


@method_decorator(staff_member_required, name="dispatch")
class StartCacheRebuildView(View):
    """View to start a cache rebuild operation"""

    def post(self, request):
        # Check if there's already a running operation
        running = MatchCacheRebuildOperation.objects.filter(
            started_on__isnull=False, finished_on__isnull=True
        ).exists()

        if running:
            messages.warning(request, "Przebudowa cache jest już w toku.")
            return HttpResponseRedirect(reverse("importer_autorow_pbn:rebuild"))

        # Create new operation
        operation = MatchCacheRebuildOperation.objects.create(owner=request.user)

        # Schedule the task
        from django.db import transaction as db_transaction

        from .tasks import rebuild_match_cache_task

        db_transaction.on_commit(
            lambda: rebuild_match_cache_task.delay(str(operation.pk))
        )

        messages.info(request, "Rozpoczęto przebudowę cache'u dopasowań.")
        return HttpResponseRedirect(
            reverse("importer_autorow_pbn:rebuild_status", args=[operation.pk])
        )


@method_decorator(staff_member_required, name="dispatch")
class CacheRebuildStatusView(DetailView):
    """View showing the status of a cache rebuild operation"""

    model = MatchCacheRebuildOperation
    template_name = "importer_autorow_pbn/rebuild_cache_status.html"
    context_object_name = "operation"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["progress_percent"] = self.object.get_progress_percent()
        return context


@method_decorator(staff_member_required, name="dispatch")
class CacheRebuildProgressView(DetailView):
    """
    HTMX partial view returning only the progress section.
    Used for polling updates during cache rebuild.
    """

    model = MatchCacheRebuildOperation
    template_name = "importer_autorow_pbn/_cache_progress.html"
    context_object_name = "operation"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["progress_percent"] = self.object.get_progress_percent()
        return context
