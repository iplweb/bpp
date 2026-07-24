import django_filters
from rest_framework import viewsets

from api_v1.serializers.patent import Patent_AutorSerializer, PatentSerializer
from api_v1.viewsets.common import (
    UkryjNieEksportowaneMixin,
    UkryjStatusyKorektyMixin,
    UkryjStatusyKorektyRekorduMixin,
)
from bpp.models import Patent, Patent_Autor


class Patent_AutorFilterSet(django_filters.rest_framework.FilterSet):
    class Meta:
        fields = ["autor"]
        model = Patent_Autor


class Patent_AutorViewSet(
    UkryjNieEksportowaneMixin,
    UkryjStatusyKorektyRekorduMixin,
    viewsets.ReadOnlyModelViewSet,
):
    # typ_odpowiedzialnosci to StringRelatedField (Wydawnictwo_AutorSerializerMixin)
    # — bez select_related jedno zapytanie NA WIERSZ.
    queryset = Patent_Autor.objects.all().select_related("typ_odpowiedzialnosci")
    serializer_class = Patent_AutorSerializer
    filterset_class = Patent_AutorFilterSet


class PatentFilterSet(django_filters.rest_framework.FilterSet):
    ostatnio_zmieniony = django_filters.DateTimeFromToRangeFilter("ostatnio_zmieniony")
    rok = django_filters.RangeFilter("rok")

    class Meta:
        fields = ["ostatnio_zmieniony", "rok"]
        model = Patent


class PatentViewSet(UkryjStatusyKorektyMixin, viewsets.ReadOnlyModelViewSet):
    # Lista musi być posortowana po PK aby nie było duplikatów
    queryset = (
        Patent.objects.exclude(nie_eksportuj_przez_api=True)
        .order_by("pk")
        # Gołe select_related() joinowało wszystkie non-null FK, a i tak GUBIŁO
        # nullowalne rodzaj_prawa (Django pomija nullable FK przy select_related
        # bez argumentów) — czyli dokładnie to pole, które serializer czyta jako
        # StringRelatedField. Jawna lista: oba StringRelatedField Patentu.
        .select_related("status_korekty", "rodzaj_prawa")
        .prefetch_related("autorzy_set", "slowa_kluczowe")
    )
    serializer_class = PatentSerializer
    filterset_class = PatentFilterSet
