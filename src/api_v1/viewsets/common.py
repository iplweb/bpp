from rest_framework.pagination import PageNumberPagination

from django.utils.functional import cached_property

from bpp.models import Uczelnia


class UkryjStatusyKorektyMixin:
    @cached_property
    def ukryte_statusy(self):
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia:
            ukryte_statusy = uczelnia.ukryte_statusy("api")
            return ukryte_statusy

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.ukryte_statusy:
            queryset = queryset.exclude(status_korekty_id__in=self.ukryte_statusy)

        return queryset


class StreszczeniaPagination(PageNumberPagination):
    page_size = 1
    page_size_query_param = "page_size"
    max_page_size = 5
