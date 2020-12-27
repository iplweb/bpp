import django_filters
from rest_framework import viewsets

from api_v1.serializers.patent import (
    Patent_AutorSerializer,
    PatentSerializer,
)
from api_v1.viewsets.common import UkryjStatusyKorektyMixin

from bpp.models import Patent, Patent_Autor


class Patent_AutorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Patent_Autor.objects.all()
    serializer_class = Patent_AutorSerializer


class PatentFilterSet(django_filters.rest_framework.FilterSet):
    ostatnio_zmieniony = django_filters.DateTimeFromToRangeFilter("ostatnio_zmieniony")
    rok = django_filters.RangeFilter("rok")

    class Meta:
        fields = ["ostatnio_zmieniony", "rok"]
        model = Patent


class PatentViewSet(UkryjStatusyKorektyMixin, viewsets.ReadOnlyModelViewSet):
    # Lista musi być posortowana po PK aby nie było duplikatów
    queryset = Patent.objects.exclude(nie_eksportuj_przez_api=True).order_by("pk")
    serializer_class = PatentSerializer
    filterset_class = PatentFilterSet
