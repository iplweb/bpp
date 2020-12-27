import django_filters
from api_v1.serializers.praca_doktorska import Praca_DoktorskaSerializer
from rest_framework import viewsets

from api_v1.viewsets.common import UkryjStatusyKorektyMixin
from bpp.models import Praca_Doktorska


class Praca_DoktorskaFilterSet(django_filters.rest_framework.FilterSet):
    ostatnio_zmieniony = django_filters.DateTimeFromToRangeFilter("ostatnio_zmieniony")
    rok = django_filters.RangeFilter("rok")

    class Meta:
        fields = ["ostatnio_zmieniony", "rok"]
        model = Praca_Doktorska


class Praca_DoktorskaViewSet(UkryjStatusyKorektyMixin, viewsets.ReadOnlyModelViewSet):
    # Lista musi być posortowana po PK aby nie było duplikatów
    queryset = Praca_Doktorska.objects.exclude(nie_eksportuj_przez_api=True).order_by(
        "pk"
    )
    serializer_class = Praca_DoktorskaSerializer
    filterset_class = Praca_DoktorskaFilterSet
