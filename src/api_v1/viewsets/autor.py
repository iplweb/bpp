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
    # Bazowy queryset BEZ filtra widoczności — zawężenie do pokazuj=True robi
    # get_queryset() TYLKO dla anonima. Autor z pokazuj=False jest świadomie
    # ukryty ze stron publicznych, ale zalogowany (redaktor) musi go widzieć.
    # ``jednostki`` to M2M serializowane many=True — bez prefetcha jedno
    # zapytanie NA AUTORA. Pozostałe relacje serializera są hyperlinkowane
    # (DRF czyta samo FK id z wiersza, ``use_pk_only_optimization``).
    queryset = Autor.objects.all().prefetch_related("jednostki")
    serializer_class = AutorSerializer
    filterset_class = AutorFilterSet
    # Filtr nazwisko__icontains skanuje bez indeksu prefiksu — opt-in
    # throttling kosztownego endpointu wyszukiwania (globalny wyłączony).
    throttle_classes = [SearchAnonThrottle, SearchUserThrottle]

    def get_queryset(self):
        # Anonim nie może zobaczyć autorów oznaczonych jako ukryci
        # (pokazuj=False) — ani na liście, ani (dzięki temu) w detalu (404).
        # Zalogowany widzi wszystkich.
        qs = super().get_queryset()
        if self.request.user.is_authenticated:
            return qs
        return qs.filter(pokazuj=True)


class Funkcja_AutoraViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Funkcja_Autora.objects.all()
    serializer_class = Funkcja_AutoraSerializer


class Autor_JednostkaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Autor_Jednostka.objects.all()
    serializer_class = Autor_JednostkaSerializer


class TytulViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tytul.objects.all()
    serializer_class = TytulSerializer
