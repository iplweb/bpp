from datetime import datetime

from django.db import models, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from import_common.core import matchuj_autora
from pbn_api.models import Scientist
from .models import DoNotRemind

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required

from django.utils.decorators import method_decorator
from django.utils.http import urlencode

from bpp.models import Autor, Tytul


@method_decorator(staff_member_required, name="dispatch")
class ImporterAutorowPBNView(ListView):
    """Main view for matching PBN Scientists to BPP Autors"""

    template_name = "importer_autorow_pbn/main.html"
    context_object_name = "scientists"
    paginate_by = 50

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

        # Add match suggestions for each scientist
        matches_count = 0
        for scientist in context["scientists"]:
            scientist.match_suggestion = self._find_match(scientist)
            scientist.create_url = self._get_create_url(scientist)
            if scientist.match_suggestion:
                matches_count += 1

        # Get total matches across ALL pages (not just current page)
        all_scientists = self.get_queryset()
        total_with_matches = 0
        for scientist in all_scientists:
            if self._find_match(scientist):
                total_with_matches += 1

        # Statistics
        total_unmatched = self.get_queryset().count()
        total_ignored = DoNotRemind.objects.count()

        context.update(
            {
                "total_unmatched": total_unmatched,
                "total_ignored": total_ignored,
                "matches_count": matches_count,  # Matches on current page
                "total_with_matches": total_with_matches,  # Total matches across all pages
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
        employment_data = self._get_employment_data(scientist)
        if employment_data:
            if employment_data.get("jednostka_id"):
                # Prepare inline for Autor_Jednostka
                params["autor_jednostka_set-0-jednostka"] = employment_data[
                    "jednostka_id"
                ]
                if employment_data.get("od"):
                    # Convert date to YYYY-MM-DD format
                    try:
                        date_obj = datetime.strptime(employment_data["od"], "%Y-%m-%d")
                        params["autor_jednostka_set-0-rozpoczal_prace"] = (
                            date_obj.strftime("%Y-%m-%d")
                        )
                    except BaseException:
                        pass
                if employment_data.get("do"):
                    try:
                        date_obj = datetime.strptime(employment_data["do"], "%Y-%m-%d")
                        params["autor_jednostka_set-0-zakonczyl_prace"] = (
                            date_obj.strftime("%Y-%m-%d")
                        )
                    except BaseException:
                        pass

                # Set management form data for inline
                params["autor_jednostka_set-TOTAL_FORMS"] = "1"
                params["autor_jednostka_set-INITIAL_FORMS"] = "0"

        return params

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
        from pbn_api.models import Institution

        from bpp.models import Jednostka

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

    linked_count = 0
    errors = []

    with transaction.atomic():
        for scientist in scientists:
            # Try to find a match
            autor = view._find_match(scientist)
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


@login_required
@staff_member_required
@require_POST
def create_all_unmatched_scientists(request):
    """AJAX endpoint to create all scientists without matches as new Autors"""

    view = ImporterAutorowPBNView()
    view.request = request

    # Get all unmatched scientists
    scientists = view.get_queryset()

    created_count = 0
    errors = []

    with transaction.atomic():
        for scientist in scientists:
            # Skip if has a match
            if view._find_match(scientist):
                continue

            try:
                # Prepare data for creating an Autor
                autor_data = {
                    "imiona": scientist.name or "",
                    "nazwisko": scientist.lastName or "",
                    "pbn_uid_id": scientist.pk,
                }

                if scientist.orcid:
                    autor_data["orcid"] = scientist.orcid

                # Get academic title
                if scientist.qualifications:
                    tytul_id = view._get_tytul_id(scientist.qualifications)
                    if tytul_id:
                        autor_data["tytul_id"] = tytul_id

                # Create the Autor
                autor = Autor.objects.create(**autor_data)

                # Add employment if available
                employment_data = view._get_employment_data(scientist)
                if employment_data and employment_data.get("jednostka_id"):
                    from bpp.models import Autor_Jednostka

                    aj_data = {
                        "autor": autor,
                        "jednostka_id": employment_data["jednostka_id"],
                    }

                    if employment_data.get("od"):
                        try:
                            aj_data["rozpoczal_prace"] = datetime.strptime(
                                employment_data["od"], "%Y-%m-%d"
                            ).date()
                        except BaseException:
                            pass

                    if employment_data.get("do"):
                        try:
                            aj_data["zakonczyl_prace"] = datetime.strptime(
                                employment_data["do"], "%Y-%m-%d"
                            ).date()
                        except BaseException:
                            pass

                    Autor_Jednostka.objects.create(**aj_data)

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
