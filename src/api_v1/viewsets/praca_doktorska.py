import django_filters
from rest_framework import viewsets

from api_v1.serializers.praca_doktorska import Praca_DoktorskaSerializer
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
    queryset = (
        Praca_Doktorska.objects.exclude(nie_eksportuj_przez_api=True)
        .order_by("pk")
        # status_korekty to jedyny StringRelatedField, który Praca_Doktorska
        # faktycznie ma: pola openaccess_* są zadeklarowane w
        # WydawnictwoSerializerMixin, ale model ich nie posiada (DRF pomija je
        # przez SkipField), więc nie ma tu czego dojoinowywać.
        .select_related("status_korekty")
        .prefetch_related("slowa_kluczowe")
    )
    serializer_class = Praca_DoktorskaSerializer
    filterset_class = Praca_DoktorskaFilterSet
