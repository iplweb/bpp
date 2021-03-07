import django_filters
from rest_framework import viewsets

from api_v1.serializers.wydawnictwo_ciagle import (
    Wydawnictwo_Ciagle_AutorSerializer,
    Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychSerializer,
    Wydawnictwo_CiagleSerializer,
)
from api_v1.viewsets.common import UkryjStatusyKorektyMixin
from bpp.models import (
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych,
)


class Wydawnictwo_Ciagle_AutorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Wydawnictwo_Ciagle_Autor.objects.all()
    serializer_class = Wydawnictwo_Ciagle_AutorSerializer


class Wydawnictwo_CiagleFilterSet(django_filters.rest_framework.FilterSet):
    ostatnio_zmieniony = django_filters.DateTimeFromToRangeFilter("ostatnio_zmieniony")
    rok = django_filters.RangeFilter("rok")

    class Meta:
        fields = ["ostatnio_zmieniony", "charakter_formalny", "rok"]
        model = Wydawnictwo_Ciagle


class Wydawnictwo_CiagleViewSet(
    UkryjStatusyKorektyMixin, viewsets.ReadOnlyModelViewSet
):
    # Lista musi być posortowana po PK aby nie było duplikatów
    queryset = (
        Wydawnictwo_Ciagle.objects.exclude(nie_eksportuj_przez_api=True)
        .order_by("pk")
        .select_related("status_korekty")
        .prefetch_related("autorzy_set", "zewnetrzna_baza_danych", "slowa_kluczowe")
    )

    serializer_class = Wydawnictwo_CiagleSerializer
    filterset_class = Wydawnictwo_CiagleFilterSet


class Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych.objects.all()
    serializer_class = Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychSerializer
