from django.utils.functional import cached_property
from rest_framework.pagination import PageNumberPagination

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


class UkryjNieEksportowaneMixin:
    """Ukrywa child-rekordy, których rekord nadrzędny ma ustawioną flagę
    ``nie_eksportuj_przez_api``.

    Główne viewsety publikacji filtrują to na poziomie rekordu, ale endpointy
    podrzędne (streszczenia, autorstwa, identyfikatory zewnętrznych baz) jadą
    na globalnym querysecie modelu-dziecka — bez tego mixina anonimowy
    użytkownik mógłby enumerować ich PK i wyciągać dane rekordu chronionego.

    ``parent_lookup`` to nazwa relacji prowadzącej do rekordu nadrzędnego
    (domyślnie ``rekord``); nadpisz na podklasie, jeśli child używa innej.
    """

    parent_lookup = "rekord"

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.exclude(
            **{f"{self.parent_lookup}__nie_eksportuj_przez_api": True}
        )


class StreszczeniaPagination(PageNumberPagination):
    page_size = 1
    page_size_query_param = "page_size"
    max_page_size = 5
