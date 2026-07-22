import django_filters
from rest_framework import viewsets

from api_v1.serializers.wydawnictwo_ciagle import (
    Wydawnictwo_Ciagle_AutorSerializer,
    Wydawnictwo_Ciagle_StreszczenieSerializer,
    Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychSerializer,
    Wydawnictwo_CiagleSerializer,
)
from api_v1.viewsets.common import (
    StreszczeniaPagination,
    UkryjNieEksportowaneMixin,
    UkryjStatusyKorektyMixin,
    UkryjStatusyKorektyRekorduMixin,
)
from bpp.models import (
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Ciagle_Streszczenie,
    Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych,
)


class Wydawnictwo_Ciagle_AutorFilterSet(django_filters.rest_framework.FilterSet):
    class Meta:
        fields = ["autor"]
        model = Wydawnictwo_Ciagle_Autor


class Wydawnictwo_Ciagle_AutorViewSet(
    UkryjNieEksportowaneMixin,
    UkryjStatusyKorektyRekorduMixin,
    viewsets.ReadOnlyModelViewSet,
):
    # typ_odpowiedzialnosci to StringRelatedField (Wydawnictwo_AutorSerializerMixin)
    # — bez select_related jedno zapytanie NA WIERSZ. Pozostałe relacje
    # serializera są hyperlinkowane (DRF czyta same FK id z wiersza).
    queryset = Wydawnictwo_Ciagle_Autor.objects.all().select_related(
        "typ_odpowiedzialnosci"
    )
    serializer_class = Wydawnictwo_Ciagle_AutorSerializer
    filterset_class = Wydawnictwo_Ciagle_AutorFilterSet


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
        # Wszystkie StringRelatedField serializera (status_korekty + trójka
        # openaccess) — każde pominięte pole to jedno zapytanie na wiersz.
        .select_related(
            "status_korekty",
            "openaccess_tryb_dostepu",
            "openaccess_wersja_tekstu",
            "openaccess_licencja",
        )
        .prefetch_related(
            "autorzy_set",
            "zewnetrzna_baza_danych",
            "slowa_kluczowe",
            "streszczenia",
        )
    )

    serializer_class = Wydawnictwo_CiagleSerializer
    filterset_class = Wydawnictwo_CiagleFilterSet


class Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychViewSet(
    UkryjNieEksportowaneMixin,
    UkryjStatusyKorektyRekorduMixin,
    viewsets.ReadOnlyModelViewSet,
):
    queryset = Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych.objects.all()
    serializer_class = Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychSerializer


class Wydawnictwo_Ciagle_StreszczenieViewSet(
    UkryjNieEksportowaneMixin,
    UkryjStatusyKorektyRekorduMixin,
    viewsets.ReadOnlyModelViewSet,
):
    queryset = Wydawnictwo_Ciagle_Streszczenie.objects.all()
    serializer_class = Wydawnictwo_Ciagle_StreszczenieSerializer
    pagination_class = StreszczeniaPagination
