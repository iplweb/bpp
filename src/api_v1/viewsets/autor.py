import django_filters
from rest_framework import viewsets

from api_v1.serializers.autor import (
    AutorSerializer,
    Funkcja_AutoraSerializer,
    TytulSerializer,
    Autor_JednostkaSerializer,
)
from bpp.models import Autor, Funkcja_Autora, Tytul, Autor_Jednostka


class AutorFilterSet(django_filters.rest_framework.FilterSet):
    ostatnio_zmieniony = django_filters.DateTimeFromToRangeFilter("ostatnio_zmieniony")

    class Meta:
        fields = ["ostatnio_zmieniony"]
        model = Autor


class AutorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Autor.objects.all()
    serializer_class = AutorSerializer
    filterset_class = AutorFilterSet


class Funkcja_AutoraViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Funkcja_Autora.objects.all()
    serializer_class = Funkcja_AutoraSerializer


class Autor_JednostkaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Autor_Jednostka.objects.all()
    serializer_class = Autor_JednostkaSerializer


class TytulViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tytul.objects.all()
    serializer_class = TytulSerializer
