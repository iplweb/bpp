import django_filters
from rest_framework import viewsets

from api_v1.serializers.wydawnictwo_zwarte import (
    Wydawnictwo_Zwarte_AutorSerializer,
    Wydawnictwo_ZwarteSerializer,
)
from api_v1.viewsets.common import UkryjStatusyKorektyMixin
from bpp.models import Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor


class Wydawnictwo_Zwarte_AutorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Wydawnictwo_Zwarte_Autor.objects.all().select_related()
    serializer_class = Wydawnictwo_Zwarte_AutorSerializer


class Wydawnictwo_ZwarteFilterSet(django_filters.rest_framework.FilterSet):
    ostatnio_zmieniony = django_filters.DateTimeFromToRangeFilter("ostatnio_zmieniony")
    rok = django_filters.RangeFilter("rok")

    class Meta:
        fields = ["ostatnio_zmieniony", "charakter_formalny", "rok"]
        model = Wydawnictwo_Zwarte


class Wydawnictwo_ZwarteViewSet(
    UkryjStatusyKorektyMixin, viewsets.ReadOnlyModelViewSet
):
    # Lista musi być posortowana po PK aby nie było duplikatów
    queryset = (
        Wydawnictwo_Zwarte.objects.exclude(nie_eksportuj_przez_api=True)
        .order_by("pk")
        .select_related("status_korekty")
        .prefetch_related("autorzy_set", "nagrody")
    )
    serializer_class = Wydawnictwo_ZwarteSerializer
    filterset_class = Wydawnictwo_ZwarteFilterSet
