from pbn_api.admin import MaMNISWIDFilter
from pbn_api.admin.base import BaseMongoDBAdmin
from pbn_api.admin.filters import OdpowiednikWydawcyWBPPFilter
from pbn_api.models import Publisher

from django.contrib import admin
from django.contrib.postgres.search import TrigramSimilarity

from bpp.models.const import PBN_UID_LEN


@admin.register(Publisher)
class PublisherAdmin(BaseMongoDBAdmin):
    list_display = ["publisherName", "mniswId", "mongoId", "rekord_w_bpp"]
    search_fields = ["mongoId", "publisherName", "mniswId"]
    list_filter = [
        OdpowiednikWydawcyWBPPFilter,
        MaMNISWIDFilter,
    ] + BaseMongoDBAdmin.list_filter

    MIN_TRIGRAM_MATCH = 0.05

    def get_search_results(self, request, queryset, search_term):
        if not search_term or len(search_term) == PBN_UID_LEN:
            return super().get_search_results(request, queryset, search_term)

        queryset = (
            queryset.annotate(
                similarity=TrigramSimilarity("publisherName", search_term)
            )
            .filter(similarity__gte=self.MIN_TRIGRAM_MATCH)
            .order_by("-similarity")
        )
        return queryset, False
