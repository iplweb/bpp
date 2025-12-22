from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from bpp.models import OplatyPublikacjiLog, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte


@admin.register(OplatyPublikacjiLog)
class OplatyPublikacjiLogAdmin(admin.ModelAdmin):
    list_display = [
        "get_publikacja",
        "rok",
        "changed_at",
        "changed_by",
        "prev_opl_pub_cost_free",
        "new_opl_pub_cost_free",
        "source_file",
    ]

    list_filter = [
        "rok",
        "changed_by",
        "changed_at",
        "content_type",
        "prev_opl_pub_cost_free",
        "new_opl_pub_cost_free",
        "prev_opl_pub_research_potential",
        "new_opl_pub_research_potential",
        "prev_opl_pub_research_or_development_projects",
        "new_opl_pub_research_or_development_projects",
        "prev_opl_pub_other",
        "new_opl_pub_other",
    ]
    search_fields = ["source_file", "rok"]
    search_help_text = "Wyszukaj po pliku źródłowym, roku lub tytule publikacji"
    readonly_fields = [
        "content_type",
        "object_id",
        "publikacja",
        "rok",
        "changed_at",
        "changed_by",
        "prev_opl_pub_cost_free",
        "prev_opl_pub_research_potential",
        "prev_opl_pub_research_or_development_projects",
        "prev_opl_pub_other",
        "prev_opl_pub_amount",
        "new_opl_pub_cost_free",
        "new_opl_pub_research_potential",
        "new_opl_pub_research_or_development_projects",
        "new_opl_pub_other",
        "new_opl_pub_amount",
        "source_file",
        "source_row",
    ]
    date_hierarchy = "changed_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Publikacja")
    def get_publikacja(self, obj):
        return obj.publikacja

    def get_search_results(self, request, queryset, search_term):
        """Custom search to allow searching by publication title."""
        queryset, use_distinct = super().get_search_results(
            request, queryset, search_term
        )

        if search_term:
            # Search for publications by title
            ct_ciagle = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
            ct_zwarte = ContentType.objects.get_for_model(Wydawnictwo_Zwarte)

            # Find matching Wydawnictwo_Ciagle IDs
            ciagle_ids = list(
                Wydawnictwo_Ciagle.objects.filter(
                    tytul_oryginalny__icontains=search_term
                ).values_list("pk", flat=True)
            )

            # Find matching Wydawnictwo_Zwarte IDs
            zwarte_ids = list(
                Wydawnictwo_Zwarte.objects.filter(
                    tytul_oryginalny__icontains=search_term
                ).values_list("pk", flat=True)
            )

            # Add matching logs to queryset
            title_filter = Q(content_type=ct_ciagle, object_id__in=ciagle_ids) | Q(
                content_type=ct_zwarte, object_id__in=zwarte_ids
            )
            queryset = queryset | self.model.objects.filter(title_filter)
            use_distinct = True

        return queryset, use_distinct
