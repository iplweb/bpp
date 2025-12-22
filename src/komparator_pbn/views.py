from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.utils.decorators import method_decorator
from django.views.generic import ListView
from django.views.generic.base import TemplateView

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Autor
from pbn_api.models import OswiadczenieInstytucji, Publication, Scientist

# Evaluation period constants
EVALUATION_START_YEAR = 2022
EVALUATION_END_YEAR = 2025


@method_decorator(staff_member_required, name="dispatch")
class KomparatorMainView(TemplateView):
    """Main dashboard for PBN comparisons."""

    template_name = "komparator_pbn/main.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Filter by evaluation period (2022-2025)
        evaluation_filter = Q(
            rok__gte=EVALUATION_START_YEAR, rok__lte=EVALUATION_END_YEAR
        )

        # Stats for publications not sent to PBN
        not_sent_filter = Q(pbn_uid_id__isnull=True)

        # Check if university has disabled export for PK=0 records
        from bpp.models.system import Charakter_Formalny
        from bpp.models.uczelnia import Uczelnia

        uczelnia = Uczelnia.objects.get_default()

        # Get charaktery formalne that should be exported to PBN
        charaktery_wysylane_do_pbn = list(
            Charakter_Formalny.objects.filter(rodzaj_pbn__isnull=False)
        )
        if uczelnia and uczelnia.pbn_api_nie_wysylaj_prac_bez_pk:
            # Exclude PK=0 records from "not sent" statistics
            not_sent_filter = not_sent_filter & ~Q(punkty_kbn=0)

        # Exclude records without DOI and without WWW (both public_www and www are empty)
        not_sent_filter = not_sent_filter & (
            Q(doi__isnull=False, doi__gt="")
            | Q(public_www__isnull=False, public_www__gt="")
            | Q(www__isnull=False, www__gt="")
        )

        # Exclude records with charakter_formalny that should not be exported to PBN (rodzaj_pbn = None)
        not_sent_filter = not_sent_filter & Q(
            charakter_formalny__rodzaj_pbn__isnull=False
        )

        ciagle_not_sent = Wydawnictwo_Ciagle.objects.filter(
            evaluation_filter, not_sent_filter
        ).count()
        zwarte_not_sent = Wydawnictwo_Zwarte.objects.filter(
            evaluation_filter, not_sent_filter
        ).count()

        # Stats for publications sent to PBN
        ciagle_sent = Wydawnictwo_Ciagle.objects.filter(
            evaluation_filter, pbn_uid_id__isnull=False
        ).count()
        zwarte_sent = Wydawnictwo_Zwarte.objects.filter(
            evaluation_filter, pbn_uid_id__isnull=False
        ).count()

        # Stats for author statements (oświadczenia)
        # BPP statements: author records with przypieta=True, afiliuje=True, dyscyplina_naukowa not null
        bpp_statements_filter = Q(
            przypieta=True,
            afiliuje=True,
            dyscyplina_naukowa__isnull=False,
            rekord__rok__gte=EVALUATION_START_YEAR,
            rekord__rok__lte=EVALUATION_END_YEAR,
        )

        bpp_ciagle_statements = Wydawnictwo_Ciagle_Autor.objects.filter(
            bpp_statements_filter
        ).count()

        bpp_zwarte_statements = Wydawnictwo_Zwarte_Autor.objects.filter(
            bpp_statements_filter
        ).count()

        # PBN statements count - only for publications from evaluation period
        # Filter PBN statements by publication year in the evaluation period
        pbn_statements = OswiadczenieInstytucji.objects.filter(
            publicationId__year__gte=EVALUATION_START_YEAR,
            publicationId__year__lte=EVALUATION_END_YEAR,
        ).count()

        # Count PBN publications never downloaded (not in BPP)
        # Use subquery instead of materializing all pbn_uid_ids into Python memory
        from bpp.models.cache import Rekord

        bpp_pbn_uids_subquery = Rekord.objects.exclude(pbn_uid_id__isnull=True).values(
            "pbn_uid_id"
        )

        # Count PBN publications in 2022-2025 that are not in BPP
        pbn_publications_not_in_bpp = (
            Publication.objects.filter(
                year__gte=EVALUATION_START_YEAR,
                year__lte=EVALUATION_END_YEAR,
                status="ACTIVE",
            )
            .exclude(mongoId__in=bpp_pbn_uids_subquery)
            .count()
        )

        # Count PBN scientists without BPP equivalents
        # Use subqueries instead of materializing all IDs into Python memory
        from bpp.models import Autor
        from importer_autorow_pbn.models import DoNotRemind

        bpp_autor_pbn_uids_subquery = Autor.objects.exclude(
            pbn_uid_id__isnull=True
        ).values("pbn_uid_id")

        ignored_scientist_ids_subquery = DoNotRemind.objects.values("scientist_id")

        # Count PBN scientists from institution API that are not in BPP and not ignored
        pbn_scientists_not_in_bpp = (
            Scientist.objects.filter(from_institution_api=True)
            .exclude(mongoId__in=bpp_autor_pbn_uids_subquery)
            .exclude(mongoId__in=ignored_scientist_ids_subquery)
            .count()
        )

        # Count authors with potential duplicates
        from deduplikator_autorow.utils import count_authors_with_duplicates

        duplicate_authors_count = count_authors_with_duplicates()

        # Count deleted PBN publications that still exist in BPP
        # Get all pbn_uid_ids from BPP that point to DELETED Publications
        deleted_pbn_in_bpp = (
            Rekord.objects.exclude(pbn_uid_id__isnull=True)
            .filter(pbn_uid__status="DELETED")
            .count()
        )

        # Count deleted PBN scientists that still exist in BPP
        # Get all authors in BPP that have pbn_uid pointing to DELETED Scientists
        deleted_pbn_scientists_in_bpp = (
            Autor.objects.exclude(pbn_uid_id__isnull=True)
            .filter(pbn_uid__status="DELETED")
            .count()
        )

        # Count deleted PBN journals (sources) that still have publications in BPP
        # Get all sources in BPP that have pbn_uid pointing to DELETED Journals
        from bpp.models import Zrodlo

        deleted_pbn_journals_in_bpp = (
            Zrodlo.objects.filter(pbn_uid__status="DELETED")
            .annotate(liczba_publikacji=Count("wydawnictwo_ciagle"))
            .filter(liczba_publikacji__gt=0)
            .count()
        )

        # Add discipline discrepancy statistics for 2022-2025
        from komparator_pbn_udzialy.models import RozbieznoscDyscyplinPBN

        # Get discrepancy statistics filtered by year
        discipline_discrepancies_qs = RozbieznoscDyscyplinPBN.objects.select_related(
            "oswiadczenie_instytucji__publicationId"
        ).filter(
            oswiadczenie_instytucji__publicationId__year__gte=EVALUATION_START_YEAR,
            oswiadczenie_instytucji__publicationId__year__lte=EVALUATION_END_YEAR,
        )

        # Use conditional aggregation to get all counts in a single query
        discipline_stats = discipline_discrepancies_qs.aggregate(
            total=Count("id"),
            bpp_empty=Count("id", filter=Q(dyscyplina_bpp__isnull=True)),
            pbn_empty=Count("id", filter=Q(dyscyplina_pbn__isnull=True)),
            both_different=Count(
                "id",
                filter=Q(dyscyplina_bpp__isnull=False, dyscyplina_pbn__isnull=False),
            ),
        )

        total_discipline_discrepancies = discipline_stats["total"]
        bpp_empty_disciplines = discipline_stats["bpp_empty"]
        pbn_empty_disciplines = discipline_stats["pbn_empty"]
        both_present_different = discipline_stats["both_different"]

        context.update(
            {
                "ciagle_not_sent": ciagle_not_sent,
                "zwarte_not_sent": zwarte_not_sent,
                "ciagle_sent": ciagle_sent,
                "zwarte_sent": zwarte_sent,
                "total_not_sent": ciagle_not_sent + zwarte_not_sent,
                "total_sent": ciagle_sent + zwarte_sent,
                "bpp_ciagle_statements": bpp_ciagle_statements,
                "bpp_zwarte_statements": bpp_zwarte_statements,
                "bpp_total_statements": bpp_ciagle_statements + bpp_zwarte_statements,
                "pbn_statements": pbn_statements,
                "pbn_publications_not_in_bpp": pbn_publications_not_in_bpp,
                "pbn_scientists_not_in_bpp": pbn_scientists_not_in_bpp,
                "duplicate_authors_count": duplicate_authors_count,
                "deleted_pbn_in_bpp": deleted_pbn_in_bpp,
                "deleted_pbn_scientists_in_bpp": deleted_pbn_scientists_in_bpp,
                "deleted_pbn_journals_in_bpp": deleted_pbn_journals_in_bpp,
                "evaluation_start_year": EVALUATION_START_YEAR,
                "evaluation_end_year": EVALUATION_END_YEAR,
                "uczelnia": uczelnia,
                "charaktery_wysylane_do_pbn": charaktery_wysylane_do_pbn,
                # Discipline discrepancy statistics
                "total_discipline_discrepancies": total_discipline_discrepancies,
                "bpp_empty_disciplines": bpp_empty_disciplines,
                "pbn_empty_disciplines": pbn_empty_disciplines,
                "both_present_different": both_present_different,
            }
        )

        # Add latest task information
        from pbn_downloader_app.models import PbnDownloadTask

        latest_task = PbnDownloadTask.get_latest_task()
        context["latest_task"] = latest_task

        # Add PBN data freshness checks
        from pbn_downloader_app.freshness import is_all_pbn_data_fresh

        is_fresh, stale_messages, last_downloads = is_all_pbn_data_fresh()
        context["pbn_data_fresh"] = is_fresh
        context["pbn_stale_messages"] = stale_messages
        context["pbn_last_downloads"] = last_downloads

        return context


@method_decorator(staff_member_required, name="dispatch")
class BPPMissingInPBNView(ListView):
    """View showing BPP statements that don't exist in PBN yet."""

    template_name = "komparator_pbn/bpp_missing_in_pbn.html"
    context_object_name = "statements"
    paginate_by = 50

    def get_queryset(self):
        publication_type = self.request.GET.get("type", "ciagle")
        query = self.request.GET.get("q", "")

        # Base filter for BPP statements
        bpp_statements_filter = Q(
            przypieta=True,
            afiliuje=True,
            dyscyplina_naukowa__isnull=False,
            rekord__rok__gte=EVALUATION_START_YEAR,
            rekord__rok__lte=EVALUATION_END_YEAR,
        )

        if publication_type == "ciagle":
            # Get BPP statements that don't have PBN statements
            queryset = Wydawnictwo_Ciagle_Autor.objects.filter(
                bpp_statements_filter
            ).select_related("rekord", "autor", "jednostka", "dyscyplina_naukowa")

            # Apply the same filtering logic as in main view for "not sent" records
            from bpp.models.uczelnia import Uczelnia

            uczelnia = Uczelnia.objects.get_default()

            # Exclude PK=0 records if university setting is enabled
            if uczelnia and uczelnia.pbn_api_nie_wysylaj_prac_bez_pk:
                queryset = queryset.exclude(rekord__pk=0)

            # Only include records with DOI or WWW
            queryset = queryset.filter(
                Q(rekord__doi__isnull=False, rekord__doi__gt="")
                | Q(rekord__public_www__isnull=False, rekord__public_www__gt="")
                | Q(rekord__www__isnull=False, rekord__www__gt="")
            )

            # Only include records with charakter_formalny that should be exported to PBN
            queryset = queryset.filter(
                rekord__charakter_formalny__rodzaj_pbn__isnull=False
            )

            # Filter out those that have PBN statements
            pbn_publication_ids = OswiadczenieInstytucji.objects.filter(
                publicationId__year__gte=EVALUATION_START_YEAR,
                publicationId__year__lte=EVALUATION_END_YEAR,
            ).values_list("publicationId_id", flat=True)

            queryset = queryset.exclude(rekord__pbn_uid_id__in=pbn_publication_ids)

        else:  # zwarte
            queryset = Wydawnictwo_Zwarte_Autor.objects.filter(
                bpp_statements_filter
            ).select_related("rekord", "autor", "jednostka", "dyscyplina_naukowa")

            # Apply the same filtering logic as in main view for "not sent" records
            from bpp.models.uczelnia import Uczelnia

            uczelnia = Uczelnia.objects.get_default()

            # Exclude PK=0 records if university setting is enabled
            if uczelnia and uczelnia.pbn_api_nie_wysylaj_prac_bez_pk:
                queryset = queryset.exclude(rekord__pk=0)

            # Only include records with DOI or WWW
            queryset = queryset.filter(
                Q(rekord__doi__isnull=False, rekord__doi__gt="")
                | Q(rekord__public_www__isnull=False, rekord__public_www__gt="")
                | Q(rekord__www__isnull=False, rekord__www__gt="")
            )

            # Only include records with charakter_formalny that should be exported to PBN
            queryset = queryset.filter(
                rekord__charakter_formalny__rodzaj_pbn__isnull=False
            )

            # Filter out those that have PBN statements
            pbn_publication_ids = OswiadczenieInstytucji.objects.filter(
                publicationId__year__gte=EVALUATION_START_YEAR,
                publicationId__year__lte=EVALUATION_END_YEAR,
            ).values_list("publicationId_id", flat=True)

            queryset = queryset.exclude(rekord__pbn_uid_id__in=pbn_publication_ids)

        if query:
            queryset = queryset.filter(
                Q(rekord__tytul_oryginalny__icontains=query)
                | Q(autor__nazwisko__icontains=query)
                | Q(autor__imiona__icontains=query)
                | Q(jednostka__nazwa__icontains=query)
            )

        return queryset.order_by("-id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["publication_type"] = self.request.GET.get("type", "ciagle")
        context["query"] = self.request.GET.get("q", "")
        context["evaluation_start_year"] = EVALUATION_START_YEAR
        context["evaluation_end_year"] = EVALUATION_END_YEAR
        return context


@method_decorator(staff_member_required, name="dispatch")
class PBNMissingInBPPView(ListView):
    """View showing PBN statements that don't exist in BPP yet."""

    template_name = "komparator_pbn/pbn_missing_in_bpp.html"
    context_object_name = "statements"
    paginate_by = 50

    def get_queryset(self):
        query = self.request.GET.get("q", "")

        # Get PBN statements from evaluation period
        queryset = OswiadczenieInstytucji.objects.filter(
            publicationId__year__gte=EVALUATION_START_YEAR,
            publicationId__year__lte=EVALUATION_END_YEAR,
        ).select_related("publicationId", "personId", "institutionId")

        # Filter out those that have BPP records
        # Get all publication IDs that exist in BPP
        from bpp.models.cache import Rekord

        bpp_publication_ids = Rekord.objects.filter(
            pbn_uid_id__isnull=False
        ).values_list("pbn_uid_id", flat=True)

        queryset = queryset.exclude(publicationId_id__in=bpp_publication_ids)

        if query:
            queryset = queryset.filter(
                Q(publicationId__title__icontains=query)
                | Q(personId__name__icontains=query)
                | Q(personId__lastName__icontains=query)
                | Q(institutionId__name__icontains=query)
            )

        return queryset.order_by("-addedTimestamp", "pk")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["evaluation_start_year"] = EVALUATION_START_YEAR
        context["evaluation_end_year"] = EVALUATION_END_YEAR
        return context
