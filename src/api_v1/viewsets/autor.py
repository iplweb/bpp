import django_filters
from rest_framework import viewsets

from api_v1.serializers.autor import (
    Autor_JednostkaSerializer,
    AutorSerializer,
    Funkcja_AutoraSerializer,
    TytulSerializer,
)
from api_v1.throttling import SearchAnonThrottle, SearchUserThrottle
from bpp.models import Autor, Autor_Jednostka, Funkcja_Autora, Tytul


class AutorFilterSet(django_filters.rest_framework.FilterSet):
    ostatnio_zmieniony = django_filters.DateTimeFromToRangeFilter("ostatnio_zmieniony")
    nazwisko = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        fields = ["ostatnio_zmieniony", "nazwisko"]
        model = Autor


class AutorViewSet(viewsets.ReadOnlyModelViewSet):
    # Tylko autorzy oznaczeni jako widoczni — autor z pokazuj=False jest
    # świadomie ukryty ze stron publicznych i nie może wyciekać przez API.
    queryset = Autor.objects.filter(pokazuj=True)
    serializer_class = AutorSerializer
    filterset_class = AutorFilterSet
    # Filtr nazwisko__icontains skanuje bez indeksu prefiksu — opt-in
    # throttling kosztownego endpointu wyszukiwania (globalny wyłączony).
    throttle_classes = [SearchAnonThrottle, SearchUserThrottle]


class Funkcja_AutoraViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Funkcja_Autora.objects.all()
    serializer_class = Funkcja_AutoraSerializer


class Autor_JednostkaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Autor_Jednostka.objects.all()
    serializer_class = Autor_JednostkaSerializer


class TytulViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tytul.objects.all()
    serializer_class = TytulSerializer
