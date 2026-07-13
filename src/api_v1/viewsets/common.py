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


class FiltrujPoWidocznosciRekorduMixin:
    """Dla viewsetów pod-zasobów (autorzy, streszczenia, zewnętrzne bazy
    danych) powiązanych FK ``rekord`` z rekordem-rodzicem.

    Ukrywa wiersze należące do rekordów wykluczonych z eksportu API
    (``nie_eksportuj_przez_api=True``) lub o ukrytym statusie korekty —
    spójnie z filtrem widoczności rekordu-rodzica. Bez tego anonimowy
    klient mógłby przez pod-zasób odczytać powiązania autorów oraz
    abstrakty rekordów świadomie ukrytych.
    """

    def get_queryset(self):
        queryset = super().get_queryset().exclude(rekord__nie_eksportuj_przez_api=True)

        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia:
            ukryte_statusy = uczelnia.ukryte_statusy("api")
            if ukryte_statusy:
                queryset = queryset.exclude(
                    rekord__status_korekty_id__in=ukryte_statusy
                )

        return queryset


class StreszczeniaPagination(PageNumberPagination):
    page_size = 1
    page_size_query_param = "page_size"
    max_page_size = 5
