import django_filters
from api_v1.serializers.praca_habilitacyjna import Praca_HabilitacyjnaSerializer
from rest_framework import viewsets

from api_v1.viewsets.common import UkryjStatusyKorektyMixin
from bpp.models import Praca_Habilitacyjna


class Praca_HabilitacyjnaFilterSet(django_filters.rest_framework.FilterSet):
    ostatnio_zmieniony = django_filters.DateTimeFromToRangeFilter("ostatnio_zmieniony")
    rok = django_filters.RangeFilter("rok")

    class Meta:
        fields = ["ostatnio_zmieniony", "rok"]
        model = Praca_Habilitacyjna


class Praca_HabilitacyjnaViewSet(
    UkryjStatusyKorektyMixin, viewsets.ReadOnlyModelViewSet
):
    # Lista musi być posortowana po PK aby nie było duplikatów
    queryset = Praca_Habilitacyjna.objects.exclude(
        nie_eksportuj_przez_api=True
    ).order_by("pk")
    serializer_class = Praca_HabilitacyjnaSerializer
    filterset_class = Praca_HabilitacyjnaFilterSet
